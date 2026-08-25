"""镜像R侧标记点到L侧: L(x,y,z) = (-R_x, R_y, R_z). 照01A mirror_markers.py."""
import bpy, os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MARKERS = os.path.join(BASE, "05骨骼绑定", "06_rig_markers.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=MARKERS)

r_coll = bpy.data.collections.get("LM_R")
r_objs = sorted([o for o in r_coll.objects], key=lambda o: o.name)

# 清旧L侧
l_coll = bpy.data.collections.get("LM_L")
if l_coll:
    for o in list(l_coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
else:
    l_coll = bpy.data.collections.new("LM_L")
    bpy.context.scene.collection.children.link(l_coll)

for o in r_objs:
    rx, ry, rz = o.location
    # 名称: 后缀_R→_L, 中文"右"→"左"
    name = o.name.replace("_R", "_L") if "_R" in o.name else o.name + "_L"
    name = name.replace("右", "左")
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'SPHERE'
    e.empty_display_size = 0.012
    e.location = (-rx, ry, rz)   # 镜像x
    e.show_in_front = True
    e.color = (0.35, 0.5, 1.0, 1.0)   # L侧蓝色
    e.show_name = True
    l_coll.objects.link(e)
    print(f"  {name}: (-{rx:.3f}, {ry:.3f}, {rz:.3f})")

bpy.ops.wm.save_as_mainfile(filepath=MARKERS)
print(f"镜像完成: R侧{len(r_objs)}点 → L侧")
print("下一步: rig_from_markers.py 生成骨骼+权重+GLB")
