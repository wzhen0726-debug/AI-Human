import bpy, os, sys
from mathutils import Vector

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
WRAPPED_BLEND = os.path.join(ROOT, "output", "wrap", "wrapped_torso_tpose_arms_v2.blend")
OUT_DIR = os.path.join(ROOT, "output", "export")

print("="*60)
print("重新导出模型（修正坐标系）")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=WRAPPED_BLEND)

mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")
tripo = bpy.data.objects.get("Tripo_Tripo_HighPoly")

# 检查Blender中的坐标
def get_bbox(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return {
        'min': Vector((min(xs), min(ys), min(zs))),
        'max': Vector((max(xs), max(ys), max(zs))),
        'size': Vector((max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))),
        'center': Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    }

bbox = get_bbox(mh_body)
print(f"Blender中MetaHuman尺寸: X={bbox['size'].x:.3f} Y={bbox['size'].y:.3f} Z={bbox['size'].z:.3f}")
print(f"X范围: [{bbox['min'].x:.3f}, {bbox['max'].x:.3f}]")
print(f"Y范围: [{bbox['min'].y:.3f}, {bbox['max'].y:.3f}]")
print(f"Z范围: [{bbox['min'].z:.3f}, {bbox['max'].z:.3f}]")

# 选择并导出GLB
bpy.ops.object.select_all(action='DESELECT')
mh_body.select_set(True)
bpy.context.view_layer.objects.active = mh_body

glb_path = os.path.join(OUT_DIR, "wrapped_metahuman_v2.glb")
bpy.ops.export_scene.gltf(
    filepath=glb_path,
    use_selection=True,
    export_format='GLB',
    export_apply=True,
    export_yup=True  # 确保Y向上
)

print(f"\n导出: {glb_path}")

# 也导出FBX（带UV）
fbx_path = os.path.join(OUT_DIR, "wrapped_metahuman.fbx")
bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=True,
    apply_scale_options='FBX_SCALE_NONE',
    axis_forward='-Z',
    axis_up='Y'
)

print(f"导出: {fbx_path}")

# 检查UV
mesh = mh_body.data
if mesh.uv_layers:
    print(f"\nUV层: {len(mesh.uv_layers)}")
    for uv_layer in mesh.uv_layers:
        print(f"  - {uv_layer.name}")

print("\nDONE")
