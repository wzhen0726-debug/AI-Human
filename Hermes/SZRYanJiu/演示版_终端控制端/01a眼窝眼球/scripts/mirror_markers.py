"""镜像R眼标记点到L眼: L(x,y,z) = (2*axis_x - R_x, R_y, R_z).

2026-09-08 v3同步: 继承R眼的尺寸/颜色/自定义属性(分组/序号), 并为L眼建顺序线
(驱动器绑定L标记, 放LM_VIS集合). 曲线对象绝不进LM_R/LM_L(会被read当成标记点).
2026-09-23 v4(活性化): 镜像轴不再硬编码 x=0, 改为从当前网格【眼区带】自算镜像对称最优轴.
  原因: 模型/对象只要带 x 偏移 dx, 绕 x=0 镜像就会让左眼系统偏 2*dx
        (实测本项目 loc.x=-0.16mm → 左眼偏 0.32mm; 眼角曲率半径~1mm, 足以顶出眼眶).
  判据活性: 采样区域由右眼手描点自身给出(眼高±60mm / 前侧 y<眼点y / |x-眼中心|<1.2×眼宽),
            对体型/轮廓变化自动适配, 不写死坐标。"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

MARKERS = os.path.join(S01A, "输出", "01A_markers_eyelid.blend")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=MARKERS)

r_coll = bpy.data.collections.get("LM_R")
r_objs = sorted([o for o in r_coll.objects if o.type == 'EMPTY'], key=lambda o: o.name)

# 清除旧L眼标记 + 旧L顺序线
l_coll = bpy.data.collections.get("LM_L")
if l_coll:
    for o in list(l_coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
else:
    l_coll = bpy.data.collections.new("LM_L")
    bpy.context.scene.collection.children.link(l_coll)
vis = bpy.data.collections.get("LM_VIS")
if vis is None:
    vis = bpy.data.collections.new("LM_VIS")
    bpy.context.scene.collection.children.link(vis)
old_c = bpy.data.objects.get("眼裂顺序线_L")
if old_c:
    bpy.data.objects.remove(old_c, do_unlink=True)

def _mirror_axis_x(ref_pts):
    """求使 (点集, 其镜像) 最贴合的镜像轴 x=dx: 最小化各点到镜像集的最近邻距离中位数.

    只用网格(几何真值), 不依赖手描点/外部 json → 换模型、换体型都自适应。
    """
    import numpy as np
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and len(o.data.polygons) > 1000]
    if not meshes or len(ref_pts) < 8:
        return 0.0
    mo = max(meshes, key=lambda o: len(o.data.polygons))
    me = mo.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3) + np.array(mo.location)          # 世界坐标
    P0 = np.array(ref_pts, dtype=np.float64)
    ez, ey = P0[:, 2].mean(), P0[:, 1].mean()
    ew = float(P0[:, 0].max() - P0[:, 0].min())      # 眼点 x 跨度(≈眼宽), 用于缩放采样区
    # 采样区必须【关于中线对称】(2026-09-23 实测: 若按右眼单侧取样 |x-ex|<1.2ew → x∈[-11,+83]mm,
    # 镜像匹配被推到 +4.7mm 搜索边界; 改为 |x|<1.6×眼宽 对称区后回到正确盆地 -0.9mm).
    # z 带取眼高±60mm, y 取前半侧(排除后脑/头发), |x| 由眼宽(眼点 x 跨度)缩放 → 体型自适应.
    m = ((co[:, 2] > ez - 0.06) & (co[:, 2] < ez + 0.06) &
         (co[:, 1] < ey) & (np.abs(co[:, 0]) < 1.6 * ew))
    P = co[m][:, :2]
    if len(P) < 200:
        print(f"镜像轴(活性): 眼区采样过少({len(P)}), 退回 x=0")
        return 0.0
    # 空间均匀化(关键): 扫描件顶点密度极不均匀(眼睑/睫毛处上千/mm², 面颊稀疏),
    # 直接取顶点会让最近邻中位数被密区主导(实测高模上算到搜索边界 +3mm).
    # 按 1mm 体素每格取一点 → 面积均匀采样, 与网格疏密无关.
    _q = np.round(P / 0.001).astype(np.int64)
    _uniq = np.unique(_q, axis=0, return_index=True)[1]
    P = P[_uniq]
    if len(P) > 1200:
        P = P[np.random.RandomState(0).choice(len(P), min(2500, len(P)), replace=False)]
    res = []
    # v4b: 中位数对"平坦盆地"不敏感(实测残差 0.46→0.48mm 只差 0.02 → 轴抖 ±0.3mm, 让左眼轮廓偏 0.6mm)。
    # 改平方距离均值(SSD) + 0.05mm 细网格 + 2500 点采样 → 盆地由"平台"变"抛物", 最小值可辨。
    for dx in np.arange(-5.0, 5.001, 0.05) * 1e-3:
        Q = P.copy(); Q[:, 0] = 2.0 * dx - Q[:, 0]
        d = np.sqrt(((P[:, None, :] - Q[None, :, :]) ** 2).sum(-1)).min(axis=1)
        res.append((dx, float((d ** 2).mean())))
    bestv = min(v for _, v in res)
    # 残差曲线在最优附近很平(扫描件本身左右不对称 ~0.5mm), 取"盆地中心"而非单点最小值 → 抑制噪声抖动
    # v4b: 判据已改 SSD(mm^2) → 盆地容差必须按"距离"折算(5% 距离带), 否则盆地会退化成整个搜索窗
    _bd = bestv ** 0.5
    tol = (max(_bd * 1.05, _bd + 0.02e-3)) ** 2
    basin = [d for d, v in res if v <= tol]
    axis = float(sum(basin) / len(basin))
    print(f"镜像轴(活性): x={axis*1000:+.2f}mm  (眼区 {len(P)} 点采样, 最优残差 {bestv ** 0.5*1000:.2f}mm, "
          f"盆地 {min(basin)*1000:+.1f}~{max(basin)*1000:+.1f}mm 共{len(basin)}档)")
    return axis


# ---- v4b(2026-09-23): 镜像轴的计算模型必须是【权威模型】(01 输出) ----
# 轮廓最终落在 01 输出的模型上, 而本文件内嵌的是旧模型(带未清零的对象变换 -0.16mm) →
# 实测让左眼轮廓整体偏 0.594mm(用户对 0.16mm 都不接受, 这个必须修)。
_ref_pts = [tuple(o.location) for o in r_objs]
_axis_src = IN_BLEND if "IN_BLEND" in globals() else os.path.join(ROOT, "01高模修复", "输出", "01_highpoly_repair.blend")
if os.path.exists(_axis_src):
    bpy.ops.wm.open_mainfile(filepath=_axis_src)          # → 权威模型
    AXIS_X = _mirror_axis_x(_ref_pts)
    bpy.ops.wm.open_mainfile(filepath=MARKERS)            # → 回打点文件(文档已切换, 下面全部重取引用)
    r_coll = bpy.data.collections.get("LM_R")
    r_objs = sorted([o for o in r_coll.objects if o.type == 'EMPTY'], key=lambda o: o.name)
    for _cname in ("LM_L", "LM_VIS"):                     # 重载后磁盘上的旧 L 标记/旧顺序线又回来了, 再清一次
        _cc = bpy.data.collections.get(_cname)
        if _cc:
            for _o in list(_cc.objects):
                bpy.data.objects.remove(_o, do_unlink=True)
    _oc = bpy.data.objects.get("眼裂顺序线_L")
    if _oc:
        bpy.data.objects.remove(_oc, do_unlink=True)
    l_coll = bpy.data.collections.get("LM_L")
    if l_coll is None:
        l_coll = bpy.data.collections.new("LM_L"); bpy.context.scene.collection.children.link(l_coll)
    vis = bpy.data.collections.get("LM_VIS")
    if vis is None:
        vis = bpy.data.collections.new("LM_VIS"); bpy.context.scene.collection.children.link(vis)
    print(f"镜像轴: 计算模型 = {os.path.basename(_axis_src)} (权威模型, 非本文件内嵌模型)")
else:
    print(f"镜像轴(活性): 权威模型缺失 {_axis_src} → 退回本文件模型")
    AXIS_X = _mirror_axis_x(_ref_pts)
l_objs = []
for o in r_objs:
    rx, ry, rz = o.location
    name = o.name.replace("_R", "_L")
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'SPHERE'
    e.empty_display_size = o.empty_display_size   # 继承尺寸(眼角1.5×)
    e.location = (2.0 * AXIS_X - rx, ry, rz)  # 镜像x(活性轴: 见 _mirror_axis_x)
    e.show_in_front = True
    e.color = o.color           # 继承分组颜色(眼角黄/上睑青/下睑橙)
    for k in ("lid_group", "order_index"):
        if k in o: e[k] = o[k]
    l_coll.objects.link(e)
    l_objs.append(e)

# L眼顺序线(闭合样条+驱动器)
cu = bpy.data.curves.new("眼裂顺序线_L", type='CURVE')
cu.dimensions = '3D'
sp = cu.splines.new('POLY')
sp.points.add(len(l_objs) - 1)
sp.use_cyclic_u = True
for i, e in enumerate(l_objs):
    sp.points[i].co = (*e.location, 1.0)
cu_obj = bpy.data.objects.new("眼裂顺序线_L", cu)
cu_obj.show_in_front = True
cu_obj.hide_select = True
cu_obj.color = (1.0, 1.0, 1.0, 1.0)
vis.objects.link(cu_obj)
n_drv = 0
for i, e in enumerate(l_objs):
    for axis, idx in (("x",0),("y",1),("z",2)):
        drv = sp.points[i].driver_add("co", idx)
        drv.driver.type = 'SCRIPTED'
        var = drv.driver.variables.new()
        var.type = 'TRANSFORMS'
        var.targets[0].id = e
        var.targets[0].transform_type = 'LOC_' + axis.upper()
        var.targets[0].transform_space = 'WORLD_SPACE'
        drv.driver.expression = "var"
        n_drv += 1

bpy.ops.wm.save_as_mainfile(filepath=MARKERS)
print(f"镜像完成: R眼{len(r_objs)}点 -> L眼{len(l_objs)}点 (尺寸/颜色/分组属性已继承)")
print(f"L眼顺序线: {len(l_objs)}点闭合样条 + {n_drv}驱动器")
print("saved")
