"""在输入高模上放置眼睑缘标记点 - 只R眼. 用户调好后镜像到L.

2026-09-08 重写(v3): 修三个用户实测发现的模板缺陷
─────────────────────────────────────────────────────────────
**旧版缺陷(等弧长采样)**: 沿整条闭合轮廓等弧长取12点, 后果:
  1. 没有任何一点真正落在眼角上 — 眼角位置由弧长决定, 不受控
  2. 名字与实际位置不符: "01 外眼角"实测在 x=19.6mm(内眼角侧),
     "07 内眼角"实测在 x=43.7mm(外眼角侧) — 两个眼角名字是反的
  3. 名义"上睑5+下睑5+眼角2", 实际变成"上睑6+下睑6", 且上下睑分界不在眼角
  根因: 源轮廓(3DDFA)每眼只有6个点, 等弧长插值不保证特征点落在解剖位置.

**v3做法(解剖驱动分段采样)**:
  ① 先定位内外眼角 = 轮廓x极值(远离中线=外眼角, 靠近中线=内眼角), 这是解剖事实
  ② 以两眼角为界把闭合轮廓拆成两段弧, **长弧=上睑, 短弧=下睑**(实测R上睑38.6mm/下睑28.5mm)
  ③ 上睑弧、下睑弧各自等弧长采样**内部点**(端点就是眼角, 不重复放)
  → 结果: 2眼角 + 上睑N点 + 下睑N点(N相等), 顺序沿闭合轮廓连续, 名字与位置严格对应

**顺序与可视化**: 点号 01→12 沿"外眼角→上睑(外→内)→内眼角→下睑(内→外)→回到外眼角"
  连续闭合. 配色区分三组: 眼角=黄, 上睑=青, 下睑=橙. 另建一条穿过全部标记的样条线
  (Hook绑定到每个Empty, 拖动点位时曲线实时跟随)让顺序一目了然.

**防误选**: 原始模型 hide_select=True + lock_location/rotation/scale=True —
  视口里可见可看纹理, 但点不中/拖不动, 只有标记Empty能被选中.

模板源优先级: 若已有 eyelid_contour_manual.json(用户手调过的72点轮廓)则用它做模板
  → 重跑不丢失人工成果且弧长分辨率更高; 否则回退 3DDFA 6点轮廓.

输出: models/01A_markers_eyelid.blend
"""
import bpy, os, sys, json, datetime, shutil
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

# ---- 参数 ----
N_PER_LID = 5          # 每侧眼睑的内部点数(上下睑相等) → 总点数 = 2眼角 + 2*N_PER_LID
N_PTS = 2 + 2 * N_PER_LID
MARKER_SIZE_RATIO = 0.6   # Empty显示尺寸 = 相邻点间距 × 此比例(自适应, 不写死体型)
OUT_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01A_markers_eyelid.blend")

# 分组配色(BGRA): 眼角醒目黄, 上睑青, 下睑橙
COL_CANTHUS = (1.0, 0.85, 0.10, 1.0)
COL_UPPER   = (0.15, 0.85, 1.00, 1.0)
COL_LOWER   = (1.00, 0.45, 0.15, 1.0)
COL_CURVE   = (1.0, 1.0, 1.0, 1.0)


def load_template_contour():
    """模板源: 优先用户手调轮廓(保成果+分辨率高), 回退3DDFA原始."""
    manual = EYELID_CONTOUR_JSON          # eyelid_contour_manual.json
    ddfa = EYELID_CONTOUR_3DDFA_JSON      # eyelid_contour.json
    if os.path.exists(manual):
        try:
            d = json.load(open(manual, encoding="utf-8"))
            rim = [r for r in d['R']["rim_3d"] if r is not None]
            if len(rim) >= N_PTS:
                print(f"模板源: 用户手调轮廓 {os.path.basename(manual)} ({len(rim)}点) — 重跑不丢人工成果")
                return np.array(rim, dtype=np.float64)
        except Exception as e:
            print(f"手调轮廓读取失败({e}), 回退3DDFA")
    d = json.load(open(ddfa, encoding="utf-8"))
    rim = [r for r in d['R']["rim_3d"] if r is not None]
    print(f"模板源: 3DDFA原始轮廓 {os.path.basename(ddfa)} ({len(rim)}点)")
    return np.array(rim, dtype=np.float64)


def arc_from(pts, i_start, i_end, direction):
    """沿闭合轮廓从i_start走到i_end, 返回(路径点数组含端点, 总弧长)."""
    M = len(pts)
    path = [pts[i_start]]
    L = 0.0
    i = i_start
    while i != i_end:
        j = (i + direction) % M
        L += float(np.linalg.norm(pts[j] - pts[i]))
        path.append(pts[j])
        i = j
    return np.array(path), L


def resample_interior(path, total_len, n):
    """沿路径等弧长取n个**内部**点(不含两端点, 端点是眼角)."""
    seg = np.array([np.linalg.norm(path[i+1] - path[i]) for i in range(len(path)-1)])
    out = []
    for k in range(1, n + 1):
        target = total_len * k / (n + 1)
        acc = 0.0
        for i in range(len(seg)):
            if acc + seg[i] >= target:
                t = (target - acc) / seg[i] if seg[i] > 1e-12 else 0.0
                out.append(path[i] + (path[i+1] - path[i]) * t)
                break
            acc += seg[i]
        else:
            out.append(path[-1])
    return out


def build_template(side='R'):
    """返回有序标记点: [(序号, 中文名, 英文名, 分组, xyz), ...] 共N_PTS个."""
    pts = load_template_contour()
    M = len(pts)
    # ① 内外眼角 = x极值(相对中线x=0: |x|大=外眼角, |x|小=内眼角)
    ax = np.abs(pts[:, 0])
    i_outer = int(np.argmax(ax))
    i_inner = int(np.argmin(ax))
    outer, inner = pts[i_outer], pts[i_inner]
    # ② 两眼角之间拆两段弧, 长弧=上睑
    fwd, L_fwd = arc_from(pts, i_outer, i_inner, +1)
    bwd, L_bwd = arc_from(pts, i_outer, i_inner, -1)
    if L_fwd >= L_bwd:
        upper_path, L_up, lower_path, L_lo = fwd, L_fwd, bwd, L_bwd
    else:
        upper_path, L_up, lower_path, L_lo = bwd, L_bwd, fwd, L_fwd
    print(f"  眼角定位: 外眼角 idx={i_outer} |x|={abs(outer[0])*1000:.1f}mm · "
          f"内眼角 idx={i_inner} |x|={abs(inner[0])*1000:.1f}mm")
    print(f"  弧长分段: 上睑={L_up*1000:.2f}mm({len(upper_path)}原始点) "
          f"下睑={L_lo*1000:.2f}mm({len(lower_path)}原始点) → 长弧判为上睑")
    # ③ 各弧等弧长取内部点(上睑: 外→内; 下睑: 内→外, 保证闭合顺序连续)
    up_pts = resample_interior(upper_path, L_up, N_PER_LID)
    # 下睑路径同样是从outer走到inner, 但闭合顺序要求"内→外", 必须反转
    lo_pts = resample_interior(lower_path, L_lo, N_PER_LID)[::-1]

    marks = []
    marks.append((1, "外眼角", "outer_canthus", "canthus", outer))
    for k, p in enumerate(up_pts):
        marks.append((2 + k, f"上睑{k+1}外起", f"upper_{k+1}", "upper", p))
    marks.append((2 + N_PER_LID, "内眼角", "inner_canthus", "canthus", inner))
    base = 3 + N_PER_LID
    for k, p in enumerate(lo_pts):
        marks.append((base + k, f"下睑{k+1}内起", f"lower_{k+1}", "lower", p))
    return marks


def make_order_curve(marks, coll):
    """建一条穿过全部标记的样条线, 每个样条点由对应Empty的location**驱动**(实时跟随).
    用驱动器而非Hook: 驱动器是纯数据API(不需编辑模式选区/上下文), 拖动点位曲线实时重绘.
    注意: 曲线对象link到独立的LM_VIS集合, 不进LM_R/LM_L — mirror/read脚本按集合遍历,
    混入曲线会被当成标记点(location=(0,0,0)会把轮廓拉向原点)."""
    try:
        vis = bpy.data.collections.get("LM_VIS")
        if vis is None:
            vis = bpy.data.collections.new("LM_VIS")
            bpy.context.scene.collection.children.link(vis)
        cu = bpy.data.curves.new("眼裂顺序线_R", type='CURVE')
        cu.dimensions = '3D'
        sp = cu.splines.new('POLY')      # Blender 5.1 enum是'POLY'(不是'POLYLINE')
        sp.points.add(len(marks) - 1)
        sp.use_cyclic_u = True           # 闭合: 直观显示末点→01首尾相连
        for idx, (num, cn, en, grp, p) in enumerate(marks):
            sp.points[idx].co = (float(p[0]), float(p[1]), float(p[2]), 1.0)
        cu_obj = bpy.data.objects.new("眼裂顺序线_R", cu)
        cu_obj.show_in_front = True
        cu_obj.hide_select = True        # 不干扰选点
        cu_obj.color = COL_CURVE
        vis.objects.link(cu_obj)         # 独立可视化集合, 不混入LM_R

        # 每个样条点XYZ由对应Empty的location驱动
        n_drv = 0
        for num, cn, en, grp, p in marks:
            tgt = bpy.data.objects.get(f"LM_{num:02d}_{cn}_{en}_R")
            if tgt is None:
                continue
            pt = sp.points[num - 1]
            for axis, idx in (("x", 0), ("y", 1), ("z", 2)):
                drv = pt.driver_add("co", idx)
                drv.driver.type = 'SCRIPTED'
                var = drv.driver.variables.new()
                var.type = 'TRANSFORMS'
                var.targets[0].id = tgt
                # Blender 5.1 enum: LOC_X/LOC_Y/LOC_Z (不是裸'X')
                var.targets[0].transform_type = 'LOC_' + axis.upper()
                var.targets[0].transform_space = 'WORLD_SPACE'
                drv.driver.expression = "var"
                n_drv += 1
        print(f"  顺序线: {len(marks)}点闭合样条 + {n_drv}个驱动器(拖动点位曲线实时跟随)")
        return cu_obj
    except Exception as e:
        print(f"  顺序线创建失败(不影响打点): {e}")
        return None


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
obj = [o for o in bpy.context.scene.objects if o.type == 'MESH'][0]

# ===== 防误选: 锁定原始模型(可见/可看纹理, 但选不中也拖不动) =====
for o in bpy.context.scene.objects:
    if o.type == 'MESH':
        o.hide_select = True
        o.lock_location = (True, True, True)
        o.lock_rotation = (True, True, True)
        o.lock_scale = (True, True, True)
print(f"原始模型已锁定: {obj.name} (hide_select=True, 变换已锁 — 视口只能选中标记点)")

# ===== 清旧标记 =====
for cname in ["LM_L", "LM_R", "LM_VIS"]:
    c = bpy.data.collections.get(cname)
    if c:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)

# ===== 建R眼标记 =====
marks = build_template('R')
coll = bpy.data.collections.new("LM_R")
bpy.context.scene.collection.children.link(coll)

# 自适应标记尺寸(按相邻点间距比例, 不写死绝对值)
coords = np.array([m[4] for m in marks])
spacing = float(np.linalg.norm(np.diff(coords, axis=0), axis=1).mean())
size = max(0.001, spacing * MARKER_SIZE_RATIO)
print(f"  标记尺寸: 自适应 {size*1000:.2f}mm (相邻点间距{spacing*1000:.2f}mm × {MARKER_SIZE_RATIO})")

COL = {"canthus": COL_CANTHUS, "upper": COL_UPPER, "lower": COL_LOWER}
for num, cn, en, grp, p in marks:
    e = bpy.data.objects.new(f"LM_{num:02d}_{cn}_{en}_R", None)
    e.empty_display_type = 'SPHERE'
    # 眼角稍大醒目(1.5×), 便于识别哪两个是眼角
    e.empty_display_size = size * (1.5 if grp == "canthus" else 1.0)
    e.location = (float(p[0]), float(p[1]), float(p[2]))
    e.show_in_front = True
    e.color = COL[grp]
    e["lid_group"] = grp        # 自定义属性: 记录所属分组, 供下游/校验读取
    e["order_index"] = num      # 自定义属性: 顺序号
    coll.objects.link(e)

# 顺序线(可视化01→12走向)
make_order_curve(marks, coll)

# ===== 面捕捉(原生snap; 不用Shrinkwrap约束, 约束会把手调位置弹回) =====
ts = bpy.context.scene.tool_settings
ts.use_snap = True
try:
    ts.snap_elements = {'FACE'}
except (TypeError, AttributeError):
    try:
        ts.snap_elements_base = {'FACE'}
    except AttributeError:
        pass
for attr in ("use_project", "snap_target_best"):
    if hasattr(ts, attr):
        setattr(ts, attr, False if attr == "use_project" else 'CLOSEST')

# ===== 空L眼集合(供镜像脚本填充) =====
lcoll = bpy.data.collections.new("LM_L")
bpy.context.scene.collection.children.link(lcoll)

# ===== 备份已有标记文件(可能含用户手调) =====
if os.path.exists(OUT_BLEND):
    bak = OUT_BLEND.replace(".blend", f"_备份_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.blend")
    shutil.copy2(OUT_BLEND, bak)
    print(f"已有标记文件, 已备份: {os.path.basename(bak)}")

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

# ===== 打印图例(用户对照) =====
print("\n" + "=" * 62)
print(f"R眼标记点 {len(marks)}个 — 顺序与分组图例")
print("=" * 62)
print(f"  {'序号':<5}{'名称':<14}{'分组':<8}{'颜色':<8}x(mm)      z(mm)")
CN_GRP = {"canthus": "眼角", "upper": "上睑", "lower": "下睑"}
CN_COL = {"canthus": "黄", "upper": "青", "lower": "橙"}
for num, cn, en, grp, p in marks:
    print(f"  {num:02d}   {cn:<14}{CN_GRP[grp]:<8}{CN_COL[grp]:<8}{p[0]*1000:+8.1f}  {p[2]*1000:+8.1f}")
print("-" * 62)
print(f"  顺序: 01外眼角 → 02~0{1+N_PER_LID}上睑(外→内) → {2+N_PER_LID}内眼角 "
      f"→ {3+N_PER_LID}~{N_PTS}下睑(内→外) → 回到01")
print(f"  上睑{N_PER_LID}点 = 下睑{N_PER_LID}点 (对称) · 眼角2点为黄色且尺寸1.5×")
print(f"  原始模型已锁定, 视口点击只会选中标记点")
print("=" * 62)
print("L眼: 空集合 LM_L (等待镜像)")
print("saved:", OUT_BLEND)
