import bpy, os
import numpy as np

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
PROJECT_ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
UV_BLEND = os.path.join(ROOT, "03自动UV", "输出", "03_auto_uv.blend")
HIGH_POLY = os.path.join(ROOT, "01a眼窝眼球", "输出", "01_1_eye_socket.blend")
FIXED_TEX = os.path.join(ROOT, "01高模修复", "输出", "01_original_tex_fixed.png")
OUT_04 = os.path.join(ROOT, "04纹理烘焙", "输出")
os.makedirs(OUT_04, exist_ok=True)

print("=== Step 4: Bake 4K (修复贴图) ===")

# 加载低模(UV已展开)
bpy.ops.wm.open_mainfile(filepath=UV_BLEND)
# 2026-09-16: 文件里现在含眼球(02起全程连贯), 不能取[0]; 低模=最大网格
low_poly = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
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
# cage挤出/射线距离: 按模型bbox尺寸比例, 不写死绝对值(跨体型自适应)
# 参考: 当前模型bbox_max≈1.8m时 cage=0.02, ray=0.1 → 比例 0.011/0.056
bpy.context.scene.render.bake.cage_extrusion = bbox_max * 0.011   # 避免黑色斑块
bpy.context.scene.render.bake.max_ray_distance = bbox_max * 0.056  # 捕捉rim折角

bpy.ops.object.select_all(action='DESELECT')
high_poly.select_set(True)
low_poly.select_set(True)
bpy.context.view_layer.objects.active = low_poly
nt.nodes.active = tex

# ===== v2(2026-09-18 用户要求): 烘焙审核机制 —— 轮次(边距阶梯)→每轮[烘→存→贴图处理→测量]→字典序择优 =====
#   参数全部由数据推导: 阶梯 = 既有基准×[1, 1.5, 0.6]; 择优 = (未填充, 脏块, 密度CV) 字典序最小; 双零早停.
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from texture_fix import fix_diffuse_png, fix_diffuse_mesh_guided
    _HAVE_FIX = True
except Exception as _e:
    _HAVE_FIX = False
    print(f"⚠ 贴图处理模块缺失(不影响烘焙): {_e}")
from bake_qa import measure as _qa_measure, better as _qa_better
_M0 = int(bpy.context.scene.render.bake.margin)          # 既有基准(16px)
_LADDER = [_M0, int(round(_M0 * 1.5)), int(round(_M0 * 0.6))]
_rounds = []
for _ri, _mg in enumerate(_LADDER):
    bpy.context.scene.render.bake.margin = _mg
    print(f'烘焙Diffuse中(第{_ri+1}轮 margin={_mg}px, cage={bbox_max*0.011:.4f}, ray={bbox_max*0.056:.4f}, 按bbox比例)...')
    bpy.ops.object.bake(type='DIFFUSE')
    _rp = os.path.join(OUT_04, f"_qa_r{_ri+1}_diffuse.png")
    img.filepath_raw = _rp
    img.file_format = 'PNG'
    img.save()
    if _HAVE_FIX:
        try:
            # reach 跟随本轮的烘焙margin(渗出带宽度=边距膨胀): margin越大, 渗带越宽, 清理半径必须同步
            _tx = fix_diffuse_png(_rp, reach_px=_mg + 4)
            print(f"  (第{_ri+1}轮)贴图溢出处理: {_tx.get('note', '')}")
            for _p in (1, 2):
                _ty = fix_diffuse_mesh_guided(_rp, [low_poly])
                print(f"  (第{_ri+1}轮)异常斑清理{_p}: {_ty.get('note', '')}")
                if _ty.get('clusters', 0) == 0:
                    break
        except Exception as _e:
            print(f"  ⚠ (第{_ri+1}轮)贴图处理跳过: {_e}")
    _q = _qa_measure(_rp, low_poly)
    print(f"  第{_ri+1}轮 QA: 未填充={_q['unfilled']*100:.2f}% 脏块={_q['dirty']*100:.2f}% 密度CV={_q['cv']:.3f}")
    _rounds.append((_q, _rp, _mg))
    if _q['unfilled'] <= 0.0 and _q['dirty'] <= 0.0:
        print(f"  第{_ri+1}轮 双零(无空洞无脏块) → 早停")
        break
_best = _rounds[0]
for _r in _rounds[1:]:
    if _qa_better(_r[0], _best[0]):
        _best = _r
tex_path = os.path.join(OUT_04, "04_diffuse_4k.png")
import shutil as _sh
_sh.copyfile(_best[1], tex_path)
bpy.context.scene.render.bake.margin = _best[2]
img.filepath_raw = tex_path
img.file_format = 'PNG'
img.reload()   # 读回选定轮的成品(勿再save: img内存里是"最后一轮"的内容, 会覆盖刚复制好的选定件)
print(f"烘焙审核选定: margin={_best[2]}px (未填充={_best[0]['unfilled']*100:.2f}% 脏块={_best[0]['dirty']*100:.2f}% 密度CV={_best[0]['cv']:.3f}) | 候选: "
      + " / ".join(f"m{r[2]}:{r[0]['unfilled']*100:.2f}%,{r[0]['dirty']*100:.2f}%,{r[0]['cv']:.3f}" for r in _rounds))
try:  # 清理轮次临时件(数字已入日志; 选定件已复制为正式文件)
    for _r in _rounds:
        if os.path.exists(_r[1]):
            os.remove(_r[1])
except Exception:
    pass
pixels = np.array(img.pixels[:])
print(f"Diffuse贴图: min={pixels.min():.3f}, max={pixels.max():.3f}, mean={pixels.mean():.3f}")

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

bpy.ops.object.bake(type='NORMAL')

normal_path = os.path.join(OUT_04, "04_normal_4k.png")
normal_img.filepath_raw = normal_path
normal_img.file_format = 'PNG'
normal_img.save()
print(f"Normal贴图已保存")

# 断开Normal连接（避免影响FBX导出）
# Blender 5.1: links.remove() 只接受1个link参数，且遍历前需拷贝列表
for link in list(nt.links):
    if link.to_node == bsdf and link.to_socket.name == 'Normal':
        nt.links.remove(link)
for link in list(nt.links):
    if link.from_node == normal_tex:
        nt.links.remove(link)

# 删除高模
bpy.data.objects.remove(high_poly, do_unlink=True)

# 导出FBX
fbx_path = os.path.join(OUT_04, "05_for_mixamo.fbx")
# 2026-09-16: 导出含眼球(全场景剩余网格: 低模+眼球; 高模已删)
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

# 保存blend
out_blend = os.path.join(OUT_04, "04_bake.blend")
bpy.ops.wm.save_as_mainfile(filepath=out_blend)

print(f"\n=== 完成 ===")
print(f"贴图(4K): {tex_path}")
print(f"FBX: {fbx_path}")
print(f"Blend: {out_blend}")
print("DONE")
