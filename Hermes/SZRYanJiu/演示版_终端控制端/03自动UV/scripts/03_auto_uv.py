"""03 自动UV: Smart UV Project + 大面积浪费检测 + 参数自动寻优 (2026-09-17 v2)

输入: 02_qr_150k_socket.blend (QR低模)
输出: 03_auto_uv.blend + 03_uv_layout_before/after.png

算法(检测方案全部由数据算出, 无写死阈值):
  ① 基准展开(66° + 自带打包) → 测量: 利用率U / 最大空方块 / 最大岛 / 纹素密度CV
  ② 废料判据(自参照): 最大空方块面积 ≥ 最大岛面积 → "大面积浪费"(空块大到能装下最大的岛)
  ③ 若判定浪费(或基准非最优) → 参数阶梯自动重跑并测量:
       66° / 75° / 82° / 89° 各 + islands均匀化 + CONCAVE重打包(scale=True)
  ④ 密度约束: 候选纹素密度CV 不得差于基准展开(保护烘焙密度均匀性)
  ⑤ 选定: 通过①②者中利用率最高; 全不通过则取利用率最高并告警
  ⑥ 用选定参数重跑一次(确定状态) → 保存 + 输出前后布局PNG

历史: 旧版先应用RimBevel倒角修改器再UV(文件夹曾名03自动UV_rim_bevel);
2026-09-08实测该倒角链失效(权重被bm.to_mesh冲掉), 整套机制已删除,
眼睑缘锐利度由烘焙法线贴图从高模获取。本脚本主动剥离bevel/crease残留属性。
"""
import bpy, os, math, time
import numpy as np

ROOT = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端"
QR_BLEND = os.path.join(ROOT, "02QR拓扑", "输出", "02_qr_150k_socket.blend")
OUT_03 = os.path.join(ROOT, "03自动UV", "输出")
os.makedirs(OUT_03, exist_ok=True)

MARGIN = 0.01        # 打包边距(=烘焙贴图岛间距需求, 沿用既有交付口径)
# 候选阶梯: (角度, 是否均匀化纹素密度, 是否CONCAVE重打包) —— 首个为基准(既有66°定案)
CANDIDATES = ((66.0, False, False), (66.0, True, True), (75.0, True, True),
              (82.0, True, True), (89.0, True, True))
GRID = 256           # 空块分析栅格分辨率(256², 分析用, 与模型无关)
EPS = 1e-6
t00 = time.time()

def P(*a): print(*a, flush=True)

# ================= 测量工具 =================
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
    """UV连通分量(共享边且两端UV相等) → [(面数, 面积, bbox边长)]"""
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
    """最大空方块(栅格化占位+膨胀封孔+DP), 返回(边长, 面积) 均为归一化0~1量纲"""
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
                med_side=float(np.median([s for _, _, s in isl])),
                empty_area=e_area, empty_side=e_side, cv=density_cv(mesh.data, areas), pts=pts)

# ================= 展开/打包 =================
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

def draw_layout(mesh, path, title=""):
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
P("=== Step 3: Auto UV (v2: 浪费检测 + 参数寻优) ===")
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

# ---- ① 基准展开 ----
t0 = time.time()
do_unwrap(mesh, CANDIDATES[0][0], uniformize=CANDIDATES[0][1], repack=CANDIDATES[0][2])
base = measure(mesh)
P(f"① 基准展开 {CANDIDATES[0][0]:.0f}°(自带打包): 利用率={base['U']*100:.1f}% 岛数={base['n']} "
  f"最大空方块={base['empty_side']:.3f}(面积{base['empty_area']*100:.2f}%) 最大岛面积={base['big_area']*100:.2f}% "
  f"密度CV={base['cv']:.3f}  [{time.time()-t0:.0f}s]")
draw_layout(mesh, os.path.join(OUT_03, "03_uv_layout_before.png"))

# ---- ② 废料判据(自参照) ----
waste = base['empty_area'] >= base['big_area']
if waste:
    P(f"⚠ 大面积浪费: 最大空方块面积{base['empty_area']*100:.2f}% >= 最大岛面积{base['big_area']*100:.2f}% "
      f"(空块大到能装下最大的岛) → 调整参数重跑")
else:
    P(f"基准无大面积浪费(空块{base['empty_area']*100:.2f}% < 最大岛{base['big_area']*100:.2f}%), 仍做候选寻优")

# ---- ③ 参数阶梯 ----
cands = []
for ang, uni, rep in CANDIDATES:
    t0 = time.time()
    do_unwrap(mesh, ang, uniformize=uni, repack=rep)
    m = measure(mesh)
    m.update(angle=ang, uniform=uni, repo=rep)
    m['waste'] = m['empty_area'] >= m['big_area']
    m['ok_density'] = m['cv'] <= base['cv']          # 密度约束: 不得差于基准展开
    cands.append(m)
    tag = "+均匀化+重打包" if rep else "(=基准)"
    P(f"   候选 {ang:.0f}°{tag}: U={m['U']*100:.1f}% "
      f"空块={m['empty_side']:.3f}({m['empty_area']*100:.2f}%) 岛数={m['n']} CV={m['cv']:.3f} "
      f"{'✓' if (not m['waste'] and m['ok_density']) else ('✗浪费' if m['waste'] else '✗密度')}  [{time.time()-t0:.0f}s]")

# ---- ④⑤ 选择 ----
valid = [m for m in cands if (not m['waste']) and m['ok_density']]
if valid:
    pick = max(valid, key=lambda m: m['U'])
else:
    pick = max(cands, key=lambda m: m['U'])
    P("⚠ 无候选同时满足废料/密度约束, 取利用率最高并告警")

# ---- ⑥ 用选定参数重跑(确定状态) ----
do_unwrap(mesh, pick['angle'], uniformize=pick['uniform'], repack=pick['repo'])
final = measure(mesh)
P(f"选定: {pick['angle']:.0f}°{'+均匀化+CONCAVE重打包' if pick['repo'] else '(自带打包)'} → "
  f"利用率={final['U']*100:.1f}% (基准{base['U']*100:.1f}%, +{(final['U']-base['U'])*100:.1f}pp) "
  f"最大空方块={final['empty_side']:.3f}({final['empty_area']*100:.2f}%) 岛数={final['n']} CV={final['cv']:.3f}")
uvl = mesh.data.uv_layers.active.data
pts_f = np.empty(len(uvl) * 2); uvl.foreach_get("uv", pts_f); pts_f = pts_f.reshape(-1, 2)
P(f"UV范围: U[{pts_f[:,0].min():.3f}, {pts_f[:,0].max():.3f}] V[{pts_f[:,1].min():.3f}, {pts_f[:,1].max():.3f}]")
draw_layout(mesh, os.path.join(OUT_03, "03_uv_layout_after.png"))

# ---- 自查 ----
assert mesh.data.attributes.get("bevel_weight_edge") is None, "bevel_weight_edge未清除!"
assert not [m for m in mesh.modifiers if m.type == 'BEVEL'], "BEVEL修改器未清除!"
assert final['U'] >= base['U'] - 1e-6, "最终利用率低于基准!"
assert not (final['empty_area'] >= final['big_area']), "最终仍存在大面积浪费!"
P(f"自查: 无倒角残留 PASS | 利用率不低于基准 PASS | 无大面积浪费 PASS | 用时{time.time()-t00:.0f}s")

out_blend = os.path.join(OUT_03, "03_auto_uv.blend")
bpy.ops.wm.save_mainfile(filepath=out_blend)
P(f"已保存: {out_blend}")
P("UV_DONE")
