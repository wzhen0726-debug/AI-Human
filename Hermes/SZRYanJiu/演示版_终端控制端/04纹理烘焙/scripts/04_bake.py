import bpy, os
import numpy as np

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
PROJECT_ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
UV_BLEND = os.path.join(ROOT, "03自动UV", "输出", "03_auto_uv.blend")
# 2026-09-22 用户定案: 烘焙源用01修复高模(眼睑闭合), 不用01a眼窝版.
# 原因: 01a的眼窝碗是新切几何, 其UV在8K贴图上无有效texel → 碗内烘出暗青黑块;
# 01眼睑闭合, 眼窝区烘到眼睑皮肤色, 眼球遮挡后整体自然(用户验收标准).
HIGH_POLY = os.path.join(ROOT, "01高模修复", "输出", "01_highpoly_repair.blend")
FIXED_TEX = os.path.join(ROOT, "01高模修复", "输出", "01_original_tex_fixed.png")
OUT_04 = os.path.join(ROOT, "04纹理烘焙", "输出")
os.makedirs(OUT_04, exist_ok=True)

print("=== Step 4: Bake 4K (修复贴图) ===")

# 加载低模(UV已展开)
bpy.ops.wm.open_mainfile(filepath=UV_BLEND)
# 明确选带_QR后缀的低模(避免选到高模残留)
low_poly = None
for o in bpy.data.objects:
    if o.type == 'MESH' and '_QR' in o.name:
        low_poly = o
        break
if low_poly is None:
    low_poly = min([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
print(f"低模: {low_poly.name}, {len(low_poly.data.polygons)}面")

# 导入高模
with bpy.data.libraries.load(HIGH_POLY) as (data_from, data_to):
    data_to.objects = data_from.objects
_loaded = []
for obj in data_to.objects:
    if obj is not None and obj.type == 'MESH':
        bpy.context.collection.objects.link(obj)
        _loaded.append(obj)
# 2026-09-16: 从"新载入的"里取最大=高模(避免多物体时选错)
high_poly = max(_loaded, key=lambda o: len(o.data.vertices))

# 对齐安全检查 (08-05新增): 低模经FBX往返可能带变换, 与高模错位会导致烘焙整体偏移
# 判定: 世界bbox中心偏差>5mm 或 尺寸偏差>1% → 立即报错, 不静默产出废贴图
def _wbbox(o):
    cs = [o.matrix_world @ v.co for v in o.data.vertices]
    mn = [min(c[i] for c in cs) for i in range(3)]
    mx = [max(c[i] for c in cs) for i in range(3)]
    return mn, mx
mn_l, mx_l = _wbbox(low_poly)
mn_h, mx_h = _wbbox(high_poly)
ctr_l = [(mn_l[i]+mx_l[i])/2 for i in range(3)]
ctr_h = [(mn_h[i]+mx_h[i])/2 for i in range(3)]
size_l = [mx_l[i]-mn_l[i] for i in range(3)]
size_h = [mx_h[i]-mn_h[i] for i in range(3)]
ctr_dev = max(abs(ctr_l[i]-ctr_h[i]) for i in range(3))
size_dev = max(abs(size_l[i]-size_h[i])/max(size_h[i], 1e-9) for i in range(3))
# 中心偏差阈值: 按高模bbox尺寸比例(0.5%), 不写死绝对mm, 跨体型自适应
bbox_max = max(size_h)
ctr_tol = bbox_max * 0.005
print(f"对齐检查: 中心偏差={ctr_dev*1000:.2f}mm(容差{ctr_tol*1000:.1f}mm), 尺寸偏差={size_dev*100:.2f}%")
if ctr_dev > ctr_tol or size_dev > 0.01:
    raise SystemExit(f"ERROR: 低模/高模未对齐 (中心偏差{ctr_dev*1000:.2f}mm>{ctr_tol*1000:.1f}mm, 尺寸偏差{size_dev*100:.2f}%), 烘焙将错位, 中止")

# 高模贴图检查（blend里已内嵌贴图，无需外部替换）
# 如果存在修复贴图则替换，否则直接使用高模自带贴图
tex_replaced = 0
for mat in high_poly.data.materials:
    if mat and mat.use_nodes:
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                img_name_lower = node.image.name.lower()
                if any(k in img_name_lower for k in ['basecolor', 'diffuse', 'albedo', 'color', 'tex']):
                    old_name = node.image.name
                    # 如果存在修复贴图则替换，否则保留原贴图
                    if os.path.exists(FIXED_TEX):
                        new_img = bpy.data.images.load(FIXED_TEX)
                        new_img.name = old_name
                        node.image = new_img
                        tex_replaced += 1
                        print(f"高模贴图替换(修复版): {old_name}")
                    else:
                        print(f"使用高模自带贴图: {old_name} ({node.image.size[0]}x{node.image.size[1]})")
if tex_replaced == 0:
    print("使用高模内嵌贴图（无外部替换）")

# Cycles
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 16
bpy.context.scene.cycles.use_denoising = False
bpy.context.scene.cycles.device = 'CPU'

# 低模材质
mat = bpy.data.materials.new(name='MVP_Material')
mat.use_nodes = True
if low_poly.data.materials:
    low_poly.data.materials[0] = mat
else:
    low_poly.data.materials.append(mat)
nt = mat.node_tree
nt.nodes.clear()
output = nt.nodes.new('ShaderNodeOutputMaterial')
bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
tex = nt.nodes.new('ShaderNodeTexImage')
img = bpy.data.images.new('MVP_Diffuse_4K', width=4096, height=4096, alpha=False)
tex.image = img
nt.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])

# Bake Diffuse
bpy.context.scene.render.bake.use_pass_direct = False
bpy.context.scene.render.bake.use_pass_indirect = False
bpy.context.scene.render.bake.use_pass_color = True
bpy.context.scene.render.bake.margin = 16
bpy.context.scene.render.bake.use_selected_to_active = True
# cage挤出/射线距离 (2026-09-22 用户实测+BVH几何调研定案): **区域自适应cage, 2次烘焙texel合成**
#   数据: 眼窝碗区 cage=0.10 正面命中400/427(0.02时仅60/427) → 眼窝需要大cage;
#         但全局0.10使肩带薄区ray起点10cm外首中肩皮肤 → 肩带皮肤色涡斑(实测回归) → 身体需要小cage.
#   解: passA cage=0.02(身体主体) + passB cage=0.10(眼窝碗), 碗区UV三角形mask内取B, 其余取A.
#   ray = 0(无限): 穿透由首命中决定与ray无关, 有限ray只造成眼窝miss黑块(用户实测0更好).
CAGE_BODY = bbox_max * 0.011
CAGE_EYE = bbox_max * 0.055

bpy.ops.object.select_all(action='DESELECT')
high_poly.select_set(True)
low_poly.select_set(True)
bpy.context.view_layer.objects.active = low_poly
nt.nodes.active = tex

print(f'烘焙Diffuse passA (cage={CAGE_BODY:.4f} 身体主体)...')
bpy.context.scene.render.bake.cage_extrusion = CAGE_BODY
bpy.context.scene.render.bake.max_ray_distance = 0.0
bpy.ops.object.bake(type='DIFFUSE')
pA = np.array(img.pixels[:]).reshape(4096, 4096, 4).copy()

# 眼窝碗区mask: 眼球球心0.95r内的低模面 → UV三角形光栅(+2px膨胀盖缝)
eye_objs = [o for o in bpy.data.objects if o.type == 'MESH' and 'Eye' in o.name]
bowl_mask = np.zeros((4096, 4096), bool)
if eye_objs:
    from scipy import ndimage as _ndi
    _lme = low_poly.data
    _luv = np.empty(len(_lme.loops) * 2); _lme.uv_layers.active.data.foreach_get("uv", _luv); _luv = _luv.reshape(-1, 2)
    _lme.calc_loop_triangles()
    _lti = np.empty(len(_lme.loop_triangles) * 3, np.int32); _lme.loop_triangles.foreach_get("loops", _lti); _lti = _lti.reshape(-1, 3)
    _tp = np.empty(len(_lme.loop_triangles), np.int32); _lme.loop_triangles.foreach_get("polygon_index", _tp)
    _ctr = np.empty(len(_lme.polygons) * 3); _lme.polygons.foreach_get("center", _ctr)
    _Ml = np.array(low_poly.matrix_world)
    _CEN = _ctr.reshape(-1, 3) @ _Ml[:3, :3].T + _Ml[:3, 3]
    _bowl = np.zeros(len(_lme.polygons), bool)
    for eo in eye_objs:
        _cs = np.empty(len(eo.data.vertices) * 3); eo.data.vertices.foreach_get("co", _cs)
        _Mw = np.array(eo.matrix_world); _cs = _cs.reshape(-1, 3) @ _Mw[:3, :3].T + _Mw[:3, 3]
        _c = _cs.mean(axis=0); _r = float(np.abs(_cs - _c).max())
        _bowl |= (np.linalg.norm(_CEN - _c, axis=1) < 0.95 * _r)
    _bt = set(np.where(_bowl)[0].tolist())
    G = 4096
    for t in range(len(_lme.loop_triangles)):
        if int(_tp[t]) not in _bt:
            continue
        tri = _luv[_lti[t]]
        xs = np.clip((tri[:, 0] * G).astype(int), 0, G - 1); ys = np.clip((tri[:, 1] * G).astype(int), 0, G - 1)
        x0, x1 = xs.min(), xs.max(); y0, y1 = ys.min(), ys.max()
        gy, gx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        v0, v1, v2 = tri
        d = (v1[0] - v0[0]) * (v2[1] - v0[1]) - (v2[0] - v0[0]) * (v1[1] - v0[1])
        if abs(d) < 1e-12:
            continue
        w1 = ((gx / G - v0[0]) * (v2[1] - v0[1]) - (gy / G - v0[1]) * (v2[0] - v0[0])) / d
        w2 = ((gy / G - v0[1]) * (v1[0] - v0[0]) - (gx / G - v0[0]) * (v1[1] - v0[1])) / d
        bowl_mask[y0:y1 + 1, x0:x1 + 1] |= (w1 >= -0.02) & (w2 >= -0.02) & (w1 + w2 <= 1.02)
    bowl_mask = _ndi.binary_dilation(bowl_mask, iterations=2)
    print(f'眼窝碗区mask: {int(_bowl.sum())}面/{int(bowl_mask.sum())}texel')

print(f'烘焙Diffuse passB (cage={CAGE_EYE:.4f} 眼窝碗区)...')
imgB = bpy.data.images.new('MVP_Diffuse_4K_eye', width=4096, height=4096, alpha=False)
tex.image = imgB
bpy.context.scene.render.bake.cage_extrusion = CAGE_EYE
bpy.ops.object.bake(type='DIFFUSE')
pB = np.array(imgB.pixels[:]).reshape(4096, 4096, 4).copy()
tex.image = img
comp = np.where(bowl_mask[:, :, None], pB, pA)
img.pixels.foreach_set(comp.ravel().astype(np.float32))
img.update()
bpy.data.images.remove(imgB)
print('区域自适应cage合成完成: 碗区取passB, 身体取passA')

tex_path = os.path.join(OUT_04, "04_diffuse_4k.png")
img.filepath_raw = tex_path
img.file_format = 'PNG'
img.save()

# 2026-09-22 用户要求: 保存【纯烘焙态】blend(未做texture_fix), 便于定位问题在烘焙还是后处理
# ⚠ 纯烘焙贴图必须另存+打包: 指向正式路径会被后处理覆盖(raw blend变假对照, 实测踩过)
raw_tex = os.path.join(OUT_04, "04_diffuse_4k_raw.png")
img.filepath_raw = raw_tex
img.save()
img.pack()
raw_blend = os.path.join(OUT_04, "04_bake_raw.blend")
bpy.ops.wm.save_as_mainfile(filepath=raw_blend)
img.unpack(method='WRITE_ORIGINAL')
img.filepath_raw = tex_path
print(f"纯烘焙态已存: {raw_blend} (贴图 {raw_tex} 已打包)")

pixels = np.array(img.pixels[:])
print(f"Diffuse贴图: min={pixels.min():.3f}, max={pixels.max():.3f}, mean={pixels.mean():.3f}")

# 2026-09-17 用户要求: 烘焙后【贴图溢出处理】— 暗色衣物渗出到皮肤的区域 → 就近替换为皮肤色 + 边缘过渡
#   (判据: 亮度<95 且 紧贴衣物本体≤18px 且 非UV空白 且 不在衣物本体连通块内; 处理前自动备份)
#   reload 让后续 pack/保存/FBX(embed) 全部携带处理后的像素
try:
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from texture_fix import fix_diffuse_png, fix_diffuse_mesh_guided, fix_diffuse_dark_streaks, fix_diffuse_cloth_specks, fix_diffuse_cloth_faces, fix_diffuse_edge_specks, fix_diffuse_socket_interior
    _tx = fix_diffuse_png(tex_path)
    print(f"贴图溢出处理: {_tx.get('note', '')}")
    # v2: 网格引导的统计离群清理(皮肤上的孤立异常斑: 脚趾暗斑/手侧暗斑等; 阈值全部由模型自身推导)
    #     迭代两遍: 第一遍清完后邻域变干净, 第二遍能吃到剩余的弱斑
    for _p in (1, 2):
        _ty = fix_diffuse_mesh_guided(tex_path, [low_poly])
        print(f"贴图异常斑清理(第{_p}遍): {_ty.get('note', '')}")
        if _p == 1:
            for _ci in _ty.get('cluster_mm_facecol', [])[:8]:
                print(f"    簇: 面={_ci[0]} 位置=({_ci[1][0]},{_ci[1][1]},{_ci[1][2]})mm 色={_ci[2]}")
        if _ty.get('clusters', 0) == 0:
            break
    # v3 (2026-09-21): 皮肤区深色条纹/黑面(含肩/头, 五官柱排除) — 用户红圈肩部黑条纹由此处理
    _tz = fix_diffuse_dark_streaks(tex_path, [low_poly],
                                   crop_dir=os.path.join(OUT_04, "_v3核对"))
    print(f"皮肤深色条纹清理: {_tz.get('note', '')}")
    for _ci in _tz.get('cluster_mm_facecol', [])[:8]:
        print(f"    簇: 面={_ci[0]} 位置=({_ci[1][0]},{_ci[1][1]},{_ci[1][2]})mm 色={_ci[2]}")
    # v4 (2026-09-21): 衣物岛内皮肤色碎点/碎线(领口/袖口骑跨面混色texel) → 周围衣物色
    _tw = fix_diffuse_cloth_specks(tex_path, crop_dir=os.path.join(OUT_04, "_v4核对"))
    print(f"衣物内皮肤碎点清理: {_tw.get('note', '')}")
    # v5 (2026-09-21): 烘焙骑跨误采样(高模真值=衣物色/低模采样=皮肤色) → 按高模真值色替换
    _tv = fix_diffuse_cloth_faces(tex_path, [low_poly], high_poly,
                                  crop_dir=os.path.join(OUT_04, "_v5核对"))
    print(f"衣边骑跨面清理: {_tv.get('note', '')}")
    for _ci in _tv.get('cluster_mm_facecol', [])[:8]:
        print(f"    簇: 面={_ci[0]} 位置=({_ci[1][0]},{_ci[1][1]},{_ci[1][2]})mm 色={_ci[2]}")
    # v6 (2026-09-21): 衣缘像素级骑跨碎线(源贴图缺陷/过渡带, 与皮肤岛粘连v4查不到) → 邻域衣物色
    _t6 = fix_diffuse_edge_specks(tex_path, crop_dir=os.path.join(OUT_04, "_v6核对"))
    print(f"衣缘碎线清理: {_t6.get('note', '')}")
    # v7 (2026-09-22): 眼窝碗心暗块(01闭眼源副作用: 碗底射线打到眼睑内表面) → 眼窝缘皮肤色
    _eyes = [o for o in bpy.data.objects if o.type == 'MESH' and 'Eye' in o.name]
    _t7 = fix_diffuse_socket_interior(tex_path, [low_poly], _eyes,
                                      crop_dir=os.path.join(OUT_04, "_v7核对"))
    print(f"眼窝碗心清理: {_t7.get('note', '')}")
    img.reload()
except Exception as _e:
    import traceback as _tb
    _tb.print_exc()      # 2026-09-22: 原实现只打印一行, 修复崩了也"静默通过"(踩过) → 必须留完整栈
    print(f"⚠ 贴图溢出处理跳过(不影响烘焙): {_e}")

# Bake Normal (方案md要求)
print('\\n烘焙Normal中 (4K)...')
# 创建Normal贴图节点
normal_tex = nt.nodes.new('ShaderNodeTexImage')
normal_img = bpy.data.images.new('MVP_Normal_4K', width=4096, height=4096, alpha=False)
normal_tex.image = normal_img
# 连接Normal到BSDF
normal_map = nt.nodes.new('ShaderNodeNormalMap')
nt.links.new(normal_tex.outputs['Color'], normal_map.inputs['Color'])
nt.links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
nt.nodes.active = normal_tex

# 2026-09-22 阶段B修正: Normal 改为与 Diffuse 相同的【区域自适应cage 两趟合成】。
#   原实现是单趟 cage=CAGE_BODY(20mm), 认为"碗区法线由 v7 涂漫反射色覆盖即可" —— 实测该判断失效:
#     cage=20mm 时碗区射线 53.5% 命中背面(射线从碗面往回打进颅腔, 起点在眼球之后),
#     烘出的碗区法线与低模法线夹角 mean 83.9° / p95 150.8° / >30° 占 72.4%
#     (身体对照区 mean 3.07° / >30° 1.5%, 同法测量) —— 而 v7 只改漫反射, 改不了法线。
#   证据: logs/_eye_cage_sweep.py(cage扫描) + 04纹理烘焙/scripts/bake_truth.py(真值层, 与真实烘焙 r=0.997)。
_bm = globals().get('bowl_mask')
bpy.context.scene.render.bake.cage_extrusion = CAGE_BODY
print(f'烘焙Normal passA (cage={CAGE_BODY:.4f} 身体主体)...')
bpy.ops.object.bake(type='NORMAL')
_nA = np.array(normal_img.pixels[:]).reshape(4096, 4096, 4).copy()
if _bm is not None and bool(_bm.any()):
    nimgB = bpy.data.images.new('MVP_Normal_4K_eye', width=4096, height=4096, alpha=False)
    normal_tex.image = nimgB
    bpy.context.scene.render.bake.cage_extrusion = CAGE_EYE
    print(f'烘焙Normal passB (cage={CAGE_EYE:.4f} 眼窝碗区)...')
    bpy.ops.object.bake(type='NORMAL')
    _nB = np.array(nimgB.pixels[:]).reshape(4096, 4096, 4).copy()
    normal_tex.image = normal_img
    normal_img.pixels.foreach_set(np.where(_bm[:, :, None], _nB, _nA).ravel().astype(np.float32))
    normal_img.update()
    bpy.data.images.remove(nimgB)
    print('Normal 区域自适应cage合成完成: 碗区取passB, 身体取passA')
    # 当场自报碗区法线质量(验收口径: 与低模法线(切线空间即(0,0,1))的夹角)
    import math as _mth
    _nb = _nB[_bm] if _nB is not None else None
    if _nb is not None and len(_nb):
        _d = _nb[:, :3].astype(np.float64) * 2.0 - 1.0
        _ln = np.linalg.norm(_d, axis=1); _ok = _ln > 1e-6
        _c = np.zeros(len(_d)); _c[_ok] = _d[_ok, 2] / _ln[_ok]
        _ang = np.degrees(np.arccos(np.clip(_c, -1, 1)))
        _black = float((np.abs(_nb[:, :3]).max(axis=1) < 0.02).mean() * 100)
        print(f'碗区法线自检: n={int(len(_d))} 夹角 mean={_ang.mean():.2f}° '
              f'p95={np.percentile(_ang, 95):.2f}° >30°={100*(_ang > 30).mean():.2f}% 全黑比例={_black:.2f}%')
else:
    normal_img.pixels.foreach_set(_nA.ravel().astype(np.float32)); normal_img.update()
    print('⚠ 未找到眼窝碗区mask, Normal 仅用身体cage(异常, 请检查眼球对象是否存在)')

normal_path = os.path.join(OUT_04, "04_normal_4k.png")
normal_img.filepath_raw = normal_path
normal_img.file_format = 'PNG'
normal_img.save()
print(f"Normal贴图已保存")

# ⚠ 2026-09-22 根因修正(实测): 原代码在这里【断开】两处连线, 但只恢复了其中一处,
#   导致 image→NormalMap 那条线永久丢失 → 法线图成为孤立节点:
#     node 'Image Texture.001' (MVP_Normal_4K) 无任何输出连线
#     node 'Normal Map' 只有 OUT Normal -> Principled BSDF.Normal 被恢复
#   → 保存的 blend 里法线不生效, 导出的 FBX 里干脆没有法线贴图(实测内嵌 PNG 只有 1 个)。
#   而同一 FBX 里眼球材质是带法线的(Eye_N.tga 正常内嵌) → 导出器本身支持法线, 断连毫无必要。
#   故: 不再断连。法线链 image → NormalMap → BSDF.Normal 全程保持完整。

# 删除高模(保留眼球: 09-16定案 04产物含眼球, 05绑定需要)
bpy.data.objects.remove(high_poly, do_unlink=True)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o != low_poly and 'Eye' not in o.name:
        bpy.data.objects.remove(o, do_unlink=True)
print(f"清理: 删除高模, 保留 {low_poly.name} + 眼球")

# 法线链自检 + 缺则补连(2026-09-22 根因)
#   历史: 原代码"断开Normal→导出FBX→重新连接→存blend", 且只恢复了一条线(image→NormalMap 永久丢失),
#   结果 blend 与 FBX 里法线都不生效(实测 FBX 内嵌 PNG 只有 1 个)。现已取消断连, 这里再加自检兜底。
#   完整链需要【两条】连线: image.Color -> NormalMap.Color 和 NormalMap.Normal -> BSDF.Normal
def _has_link(_nt, _fo, _ti):
    return any(l.from_socket == _fo and l.to_socket == _ti for l in _nt.links)
if normal_map and bsdf and normal_tex:
    if 'Normal' in bsdf.inputs and not _has_link(nt, normal_map.outputs['Normal'], bsdf.inputs['Normal']):
        nt.links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
        print("补连: NormalMap.Normal -> BSDF.Normal")
    if 'Color' in normal_map.inputs and not _has_link(nt, normal_tex.outputs['Color'], normal_map.inputs['Color']):
        nt.links.new(normal_tex.outputs['Color'], normal_map.inputs['Color'])
        print("补连: Image(Color) -> NormalMap.Color")
    _ok1 = _has_link(nt, normal_tex.outputs['Color'], normal_map.inputs['Color'])
    _ok2 = _has_link(nt, normal_map.outputs['Normal'], bsdf.inputs['Normal'])
    print(f"法线链自检: image→NormalMap={_ok1}  NormalMap→BSDF={_ok2}"
          + ("" if (_ok1 and _ok2) else "   ⚠ 法线链不完整, FBX/blend 里法线将不生效!"))

# 导出FBX (⚠ 必须在 Normal Map 已连接之后)
fbx_path = os.path.join(OUT_04, "05_for_mixamo.fbx")
# 导出含眼球(全场景剩余网格: 低模+眼球; 高模已删)
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.select_set(True)
bpy.context.view_layer.objects.active = low_poly
bpy.ops.export_scene.fbx(
    filepath=fbx_path, use_selection=True, use_mesh_modifiers=False,
    mesh_smooth_type='FACE', use_tspace=True, use_custom_props=False,
    add_leaf_bones=False, bake_anim=False, path_mode='COPY', embed_textures=True
)
# 导出后当场自检: FBX 内嵌 PNG 数(应为 2: diffuse + normal)
try:
    with open(fbx_path, 'rb') as _f:
        _fbx = _f.read()
    _PNG_SIG = bytes.fromhex("89504e470d0a1a0a")   # 用十六进制构造, 避免源码里出现控制字符
    _npng = _fbx.count(_PNG_SIG)
    print(f"FBX 自检: 内嵌 PNG blob = {_npng} (期望 2 = diffuse + normal)"
          + ("" if _npng >= 2 else "  ⚠ 法线贴图未进入 FBX!"))
    del _fbx
except Exception as _e:
    print(f"FBX 自检跳过: {_e}")

# 保存blend
out_blend = os.path.join(OUT_04, "04_bake.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)

print(f"\n=== 完成 ===")
print(f"贴图(4K): {tex_path}")
print(f"FBX: {fbx_path}")
print(f"Blend: {out_blend}")
print("DONE")
