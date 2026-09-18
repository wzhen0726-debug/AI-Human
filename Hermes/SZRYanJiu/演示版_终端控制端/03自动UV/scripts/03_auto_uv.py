"""03 自动UV: Smart UV Project + 大面积浪费检测 + 自适应参数搜索 (2026-09-17 v3)

输入: 02_qr_150k_socket.blend (QR低模)
输出: 03_auto_uv.blend + 03_uv_layout_before/after.png

设计原则(换任何原始模型都成立, 无写死阈值):
  · 全部判据/约束都相对"本次基准展开"或布局自身计算, 不含模型相关常量;
  · 搜索有预算(MAX_ROUNDS=5), 跑完择优; 任何异常都回退到"最好一版"并明确告警, 不阻断管线;
  · 选中方案重跑一次定状态并复测, 复测不过依次退用次优(处理运行波动)。

检测指标(每次展开后测量):
  利用率U = Σ|UV面面积| / 1.0
  最大空方块 = 布局栅格化+膨胀封孔+最大空方块DP(归一化边长/面积)
  岛统计 = UV连通分量(共享边且两端UV相等) → 岛数/最大岛面积/中位岛边长
  纹素密度CV = 逐面(UV面积/3D面积)的变异系数

判据(自参照, 三项比值 ≤1 即通过; 比值即"控制住的阈值边距"):
  废料比 = 最大空方块面积 / 最大岛面积   (<1: 空块装不下最大的岛 = 无大面积浪费)
  密度比 = 候选CV / 基准CV               (≤1: 不破坏展开算法自身的纹素密度均匀度)
  岛数比 = 候选岛数 / 基准岛数           (≤1: 不新增接缝/碎岛)
  择优: 三项全过者中取利用率最高; 全不过则按(废料比, -U)取"最好一版"并告警

搜索(自适应二分, 5轮含基准):
  第1轮 66°(既有"少接缝"定案, 自带打包) = 基准
  第2轮 66°+光顺+重打包(验证打包增益)   第3轮 89°+…(探上界)
  第4轮 (66+89)/2 +…                    第5轮 依三点峰值侧再二分一探
历史: 旧版先应用RimBevel倒角修改器再UV(文件夹曾名03自动UV_rim_bevel);
2026-09-08实测该倒角链失效, 整套机制已删除, 眼睑缘锐利度由烘焙法线贴图获取;
本脚本主动剥离bevel/crease残留属性。"""
import bpy, os, math, time
import numpy as np

ROOT = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端"
QR_BLEND = os.path.join(ROOT, "02QR拓扑", "输出", "02_qr_150k_socket.blend")
OUT_03 = os.path.join(ROOT, "03自动UV", "输出")
os.makedirs(OUT_03, exist_ok=True)

MARGIN = 0.01          # 打包边距(烘焙岛间距需求, 沿用既有交付口径)
MAX_ROUNDS = 5         # 搜索预算: 含基准共5次展开; 达到即择优(不无限循环)
ANGLE_START = 66.0     # 既有"少接缝"定案角度 = 搜索下界(不低于它以免新增接缝)
ANGLE_LIMIT = 89.0     # 搜索上界(≥90°全平失去分岛意义)
GRID = 256             # 空块分析栅格(分析分辨率, 与模型无关)
EPS = 1e-6
t00 = time.time()

def P(*a): print(*a, flush=True)

# ================= 测量 =================
def uv_arrays(mesh):
    me = mesh.data
    uvl = me.uv_layers.active.data
    pts = np.empty(len(uvl) * 2); uvl.foreach_get("uv", pts); pts = pts.reshape(-1, 2)
    areas = np.empty(len(me.polygons))
    for i, p in enumerate(me.polygons):
        q = pts[np.array(p.loop_indices)]
        x, y = q[:, 0], q[:, 1]
        areas[i] = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    return pts, areas

def uv_islands(mesh, pts, areas):
    """UV连通分量(共享边且两端UV相等) → [(面数, 面积, bbox边长)] 按面积降序"""
    me = mesh.data
    parent = list(range(len(me.polygons)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    edge_map = {}
    for i, p in enumerate(me.polygons):
        idx = list(p.loop_indices)
        for k in range(len(idx)):
            l1, l2 = idx[k], idx[(k + 1) % len(idx)]
            v1, v2 = me.loops[l1].vertex_index, me.loops[l2].vertex_index
            key = (v1, v2) if v1 < v2 else (v2, v1)
            ua, ub = pts[l1].copy(), pts[l2].copy()
            if v1 > v2: ua, ub = ub, ua
            edge_map.setdefault(key, []).append((i, ua, ub))
    for lst in edge_map.values():
        if len(lst) == 2:
            (f1, a1, b1), (f2, a2, b2) = lst
            if abs(a1[0]-a2[0]) < EPS and abs(a1[1]-a2[1]) < EPS and abs(b1[0]-b2[0]) < EPS and abs(b1[1]-b2[1]) < EPS:
                r1, r2 = find(f1), find(f2)
                if r1 != r2: parent[r2] = r1
    groups = {}
    for i in range(len(me.polygons)):
        groups.setdefault(find(i), []).append(i)
    out = []
    for fs in groups.values():
        a = float(areas[np.array(fs)].sum())
        idxs = np.concatenate([me.polygons[f].loop_indices[:] for f in fs])
        q = pts[idxs]
        side = float(max(q[:, 0].max() - q[:, 0].min(), q[:, 1].max() - q[:, 1].min()))
        out.append((len(fs), a, side))
    out.sort(key=lambda x: -x[1])
    return out

def empty_square(pts):
    """最大空方块(栅格化占位+膨胀封孔+DP), 返回(归一化边长, 面积)"""
    gx = np.clip((pts[:, 0] * GRID).astype(int), 0, GRID - 1)
    gy = np.clip((pts[:, 1] * GRID).astype(int), 0, GRID - 1)
    grid = np.zeros((GRID, GRID), bool); grid[gy, gx] = True
    for _ in range(2):
        g2 = grid.copy()
        g2[1:, :] |= grid[:-1, :]; g2[:-1, :] |= grid[1:, :]
        g2[:, 1:] |= grid[:, :-1]; g2[:, :-1] |= grid[:, 1:]
        grid = g2
    empty = ~grid
    dp = np.zeros((GRID, GRID), np.int32); best = 0
    for y in range(GRID):
        for x in range(GRID):
            if empty[y, x]:
                v = 1 + min(dp[y-1, x] if y > 0 else 0,
                            dp[y, x-1] if x > 0 else 0,
                            dp[y-1, x-1] if (y > 0 and x > 0) else 0)
                dp[y, x] = v
                if v > best: best = v
    side = best / GRID
    return side, side * side

def density_cv(me, uva):
    rat = np.array([uva[i] / p.area for i, p in enumerate(me.polygons) if uva[i] > 1e-12 and p.area > 1e-12])
    return float(np.std(rat) / max(np.median(rat), 1e-12))

def measure(mesh):
    pts, areas = uv_arrays(mesh)
    U = float(areas.sum())
    isl = uv_islands(mesh, pts, areas)
    e_side, e_area = empty_square(pts)
    return dict(U=U, n=len(isl), big_area=isl[0][1], big_side=isl[0][2],
                empty_area=e_area, empty_side=e_side, cv=density_cv(mesh.data, areas))

def ratios(m, base):
    """三项比值(≤1通过): 废料比 / 密度比 / 岛数比"""
    return (m['empty_area'] / max(m['big_area'], 1e-9),
            m['cv'] / max(base['cv'], 1e-9),
            m['n'] / max(base['n'], 1))

def passes(m, base):
    # v2(2026-09-18): 数值容差1% —— 刀锋问题实测: 岛数比=471/470=1.002 曾把"三项全过"的好候选卡成不过,
    #   逼出fallback并选中密度比1.81的坏UV(烘焙出现脏块/拉伸的直接来源). 容差为相对量, 与模型无关.
    _TOL = 0.01
    wr, dr, sr = ratios(m, base)
    return (wr < 1.0) and (dr <= 1.0 + _TOL) and (sr <= 1.0 + _TOL)

def viol(m, base):
    """违约度 = 三项比值超出1的部分之和(0=无违约)。
    v2: 全不过时按【违约度最小】择优 —— 此前只按(废料比, -利用率), 曾选中密度比1.81的最差候选。"""
    wr, dr, sr = ratios(m, base)
    return max(0.0, wr - 1.0) + max(0.0, dr - 1.0) + max(0.0, sr - 1.0)

# ================= 展开/打包/绘图 =================
def do_unwrap(mesh, angle_deg, uniformize, repack):
    bpy.ops.object.select_all(action='DESELECT')
    mesh.select_set(True); bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle_deg), island_margin=MARGIN,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    if uniformize:
        bpy.ops.uv.select_all(action='SELECT'); bpy.ops.uv.average_islands_scale()
    if repack:
        bpy.ops.uv.select_all(action='SELECT')
        props = {p.identifier for p in bpy.ops.uv.pack_islands.get_rna_type().properties}
        kw = dict(rotate=True, scale=True, margin_method='SCALED', margin=MARGIN,
                  shape_method='CONCAVE', pin=False, merge_overlap=False)
        bpy.ops.uv.pack_islands(**{k: v for k, v in kw.items() if k in props})
    bpy.ops.object.mode_set(mode='OBJECT')

def draw_layout(mesh, path):
    me = mesh.data
    uvl = me.uv_layers.active.data
    pts = np.empty(len(uvl) * 2); uvl.foreach_get("uv", pts); pts = pts.reshape(-1, 2)
    S = 1024
    img = np.full((S, S, 4), 255, np.uint8)
    img[0, :, :3] = 190; img[-1, :, :3] = 190; img[:, 0, :3] = 190; img[:, -1, :3] = 190
    segs = []
    for p in me.polygons:
        idx = list(p.loop_indices)
        for k in range(len(idx)):
            a, b = pts[idx[k]], pts[idx[(k + 1) % len(idx)]]
            if a[0] != b[0] or a[1] != b[1]:
                segs.append((a, b))
    if segs:
        segs = np.array(segs)
        t = np.linspace(0.0, 1.0, 12)[None, :, None]
        Pm = (segs[:, 0:1, :] * (1 - t) + segs[:, 1:2, :] * t).reshape(-1, 2)
        x = np.clip((Pm[:, 0] * S).astype(int), 0, S - 1)
        y = np.clip(((1 - Pm[:, 1]) * S).astype(int), 0, S - 1)
        img[y, x] = (60, 100, 200, 255)
    im = bpy.data.images.new("uvlay", width=S, height=S, alpha=True)
    im.pixels[:] = (img[::-1].astype(np.float32) / 255.0).ravel()
    im.filepath_raw = path; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)

# ================= 主流程 =================
P("=== Step 3: Auto UV (v3: 浪费检测 + 自适应搜索[5轮预算] + 择优) ===")
bpy.ops.wm.open_mainfile(filepath=QR_BLEND)
mesh = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
P(f"低模: {mesh.name}, {len(mesh.data.vertices):,}顶点 {len(mesh.data.polygons):,}面")

removed_attr = []
for name in ("bevel_weight_edge", "bevel_weight_vert", "crease_edge", "crease_vert"):
    a = mesh.data.attributes.get(name)
    if a is not None:
        mesh.data.attributes.remove(a); removed_attr.append(name)
removed_mod = [m.name for m in mesh.modifiers if m.type == 'BEVEL']
for m in list(mesh.modifiers):
    if m.type == 'BEVEL':
        mesh.modifiers.remove(m)
P(f"剥离属性: {removed_attr if removed_attr else '无(输入已干净)'} 移除BEVEL修改器: {removed_mod if removed_mod else '无'}")

if any(abs(r) > 1e-9 for r in mesh.rotation_euler):
    bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    P(f"对象旋转已归零 -> {tuple(round(r,9) for r in mesh.rotation_euler)}")

rounds = []   # (round_no, angle, uniformize, repack, metrics)

# ---------- 第1轮: 基准 ----------
t0 = time.time()
do_unwrap(mesh, ANGLE_START, uniformize=False, repack=False)
base = measure(mesh)
rounds.append((1, ANGLE_START, False, False, base))
wr, dr, sr = ratios(base, base)
P(f"第1轮 基准 {ANGLE_START:.0f}°(自带打包): U={base['U']*100:.1f}% 岛数={base['n']} "
  f"最大空方块={base['empty_side']:.3f}({base['empty_area']*100:.2f}%) 最大岛={base['big_area']*100:.2f}% CV={base['cv']:.3f} [{time.time()-t0:.0f}s]")
P(f"      基准废料比={wr:.2f} → {'⚠ 大面积浪费(空块≥最大岛), 调整参数重跑' if wr >= 1 else '无大面积浪费, 仍寻优'}")
draw_layout(mesh, os.path.join(OUT_03, "03_uv_layout_before.png"))

# ---------- 第2..5轮: 自适应搜索 ----------
def probe(rno, ang):
    t = time.time()
    try:
        do_unwrap(mesh, ang, uniformize=True, repack=True)
        m = measure(mesh)
    except Exception as e:
        P(f"  第{rno}轮 {ang:.1f}° 展开失败({e}), 跳过"); return None
    rounds.append((rno, ang, True, True, m))
    wr_, dr_, sr_ = ratios(m, base)
    ok = passes(m, base)
    P(f"  第{rno}轮 {ang:.1f}°+光顺+重打包: U={m['U']*100:.1f}% 空块={m['empty_side']:.3f}({m['empty_area']*100:.2f}%) "
      f"岛数={m['n']} CV={m['cv']:.3f} | 废料比={wr_:.3f} 密度比={dr_:.3f} 岛数比={sr_:.3f} {'✓' if ok else '✗'} [{time.time()-t:.0f}s]")
    return m

m66 = probe(2, ANGLE_START)
m89 = probe(3, ANGLE_LIMIT)
mid = (ANGLE_START + ANGLE_LIMIT) / 2.0
mmid = probe(4, mid)
known = [(a, m) for a, m in ((ANGLE_START, m66), (mid, mmid), (ANGLE_LIMIT, m89)) if m is not None]
if known and len(rounds) < MAX_ROUNDS:
    # 朝"合法候选中的峰"方向探索(若无合法者再退用原始U峰) —— 换模型时避免整段探测落在非法区
    kvalid = [(a, m) for a, m in known if passes(m, base)]
    ba, bm = max(kvalid if kvalid else known, key=lambda x: x[1]['U'])
    if ba <= ANGLE_START + 1e-6:
        nxt = (ANGLE_START + mid) / 2.0
    elif ba >= ANGLE_LIMIT - 1e-6:
        nxt = (mid + ANGLE_LIMIT) / 2.0
    else:
        lo_u = next((m['U'] for a, m in known if a <= ANGLE_START + 1e-6), -1.0)
        hi_u = next((m['U'] for a, m in known if a >= ANGLE_LIMIT - 1e-6), -1.0)
        nxt = (ANGLE_START + ba) / 2.0 if lo_u >= hi_u else (ba + ANGLE_LIMIT) / 2.0
    if all(abs(nxt - a) > 0.5 for a, _ in known):
        probe(5, nxt)
P(f"搜索完成: 共{len(rounds)}轮 (预算{MAX_ROUNDS})")

# ---------- 择优 ----------
valid = [(r, m) for r, a, u, p, m in rounds if passes(m, base)]
if valid:
    pick_rno, pick_m = max(valid, key=lambda x: x[1]['U'])
else:
    pick_rno, pick_m = min([(r, m) for r, a, u, p, m in rounds],
                           key=lambda x: (viol(x[1], base), ratios(x[1], base)[0], -x[1]['U']))
    P("⚠ 无候选同时满足三项约束 → 按【违约度最小→废料比→利用率】取最好一版, 管线继续")
pick_cfg = next((a, u, p) for r, a, u, p, m in rounds if m is pick_m)
P(f"候选排名(第{pick_rno}轮最优): {pick_cfg[0]:.1f}°{' +光顺+重打包' if pick_cfg[2] else '(自带打包)'}, U={pick_m['U']*100:.1f}%")

# ---------- 定状态 + 复测(不过则退用次优) ----------
order = sorted(rounds, key=lambda x: (0 if passes(x[4], base) else 1, viol(x[4], base), ratios(x[4], base)[0], -x[4]['U']))
final = None; final_cfg = None; final_rno = None
for r, a, u, p, m in order:
    do_unwrap(mesh, a, uniformize=u, repack=p)
    fm = measure(mesh)
    wr2, dr2, sr2 = ratios(fm, base)
    okc = passes(fm, base)
    P(f"定状态复测 第{r}轮({a:.1f}°{' +光顺+重打包' if p else ''}): U={fm['U']*100:.1f}% "
      f"废料比={wr2:.2f} 密度比={dr2:.2f} 岛数比={sr2:.2f} {'✓通过' if okc else '✗不过, 退用次优'}")
    if okc:
        final, final_cfg, final_rno = fm, (a, u, p), r
        break
if final is None:
    r, a, u, p, m = order[0]
    do_unwrap(mesh, a, uniformize=u, repack=p)
    final, final_cfg, final_rno = measure(mesh), (a, u, p), r
    P("⚠ 复测均未通过(疑似运行波动): 保留最优一版并告警, 不阻断管线")

uvl = mesh.data.uv_layers.active.data
pts_f = np.empty(len(uvl) * 2); uvl.foreach_get("uv", pts_f); pts_f = pts_f.reshape(-1, 2)
fw = ratios(final, base)
P(f"选定: {final_cfg[0]:.1f}°{' +光顺+CONCAVE重打包' if final_cfg[2] else '(自带打包)'} → "
  f"利用率={final['U']*100:.1f}% (基准{base['U']*100:.1f}%, {(final['U']-base['U'])*100:+.1f}pp) "
  f"最大空方块={final['empty_side']:.3f}({final['empty_area']*100:.2f}%) 岛数={final['n']} CV={final['cv']:.3f}")
P(f"UV范围: U[{pts_f[:,0].min():.3f}, {pts_f[:,0].max():.3f}] V[{pts_f[:,1].min():.3f}, {pts_f[:,1].max():.3f}]")
draw_layout(mesh, os.path.join(OUT_03, "03_uv_layout_after.png"))

# ---------- 自查 ----------
assert mesh.data.attributes.get("bevel_weight_edge") is None, "bevel_weight_edge未清除!"
assert not [m for m in mesh.modifiers if m.type == 'BEVEL'], "BEVEL修改器未清除!"
okf = (fw[0] < 1.0) and (fw[1] <= 1.01) and (fw[2] <= 1.01)   # 与 passes() 同口径(1%数值容差)
P(f"自查: 无倒角残留 PASS | 最终 废料比={fw[0]:.3f}(<1) 密度比={fw[1]:.3f}(≤1) 岛数比={fw[2]:.3f}(≤1) "
  f"{'PASS' if okf else 'WARN(已取最好一版, 不阻断)'} | 用时{time.time()-t00:.0f}s")

out_blend = os.path.join(OUT_03, "03_auto_uv.blend")
bpy.ops.wm.save_mainfile(filepath=out_blend)
P(f"已保存: {out_blend}")
P("UV_DONE")
