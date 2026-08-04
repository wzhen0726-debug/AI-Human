import bpy, os, sys
from mathutils import Vector

ROOT = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\test02"
WRAPPED_BLEND = os.path.join(ROOT, "output", "wrap", "wrapped_tpose.blend")
OUT_DIR = os.path.join(ROOT, "output", "export")
os.makedirs(OUT_DIR, exist_ok=True)

print("="*60)
print("导出包裹后的模型")
print("="*60)

bpy.ops.wm.open_mainfile(filepath=WRAPPED_BLEND)

# 获取MetaHuman Body
mh_body = bpy.data.objects.get("MH_NewMetaHumanCharacter_Body")

# 选择并导出GLB
bpy.ops.object.select_all(action='DESELECT')
mh_body.select_set(True)
bpy.context.view_layer.objects.active = mh_body

glb_path = os.path.join(OUT_DIR, "wrapped_metahuman.glb")
bpy.ops.export_scene.gltf(
    filepath=glb_path,
    use_selection=True,
    export_format='GLB',
    export_apply=True
)

print(f"导出: {glb_path}")

# 也导出OBJ（带UV）
obj_path = os.path.join(OUT_DIR, "wrapped_metahuman.obj")
bpy.ops.wm.obj_export(
    filepath=obj_path,
    export_selected_objects=True,
    export_uv=True,
    export_normals=True,
    export_materials=False
)

print(f"导出: {obj_path}")

# 检查UV
mesh = mh_body.data
if mesh.uv_layers:
    print(f"\nUV层: {len(mesh.uv_layers)}")
    for uv_layer in mesh.uv_layers:
        print(f"  - {uv_layer.name}")
else:
    print("\n无UV层")

print("\nDONE")
