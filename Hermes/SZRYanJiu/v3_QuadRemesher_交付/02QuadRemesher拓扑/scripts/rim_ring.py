"""眼窝rim环形布线替换 v2: 沿rim轮廓做放射状环形网格, 桥接替换QR的碎rim.
关键: 只保存低模+rim环,  rim环与低模桥接(Bridge Edge Loops)."""
import bpy, os, json, bmesh
import numpy as np
from mathutils import Vector

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
HI_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
OUT_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_ring.blend")
XZ_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
cont = json.load(open(XZ_JSON, encoding="utf-8"))

# 1. 打开低模
bpy.ops.wm.open_mainfile(filepath=LOW_BLEND)
head = max([o for o in bpy.data.objects if o.type == 'MESH'],
           key=lambda o: len(o.data.vertices))
print(f"低模: {head.name} 顶点={len(head.data.vertices)} 面={len(head.data.polygons)}")

# 2. 加载高模(仅Shrinkwrap参考, 不保存)
bpy.ops.wm.append(filepath=os.path.join(HI_BLEND, "Object"),
                  directory=os.path.join(HI_BLEND, "Object"),
                  filename="tripo_node_89f96507-4268-42bd-8c27-bf6892366069", autoselect=False)
hi = bpy.data.objects.get("tripo_node_89f96507-4268-42bd-8c27-bf6892366069")
if hi is None:
    hi = max([o for o in bpy.data.objects if o.type == 'MESH' and o != head],
             key=lambda o: len(o.data.vertices))
hi.hide_render = True
hi.hide_viewport = True
print(f"高模参考: {hi.name} 顶点={len(hi.data.vertices)}")

# 3. 构建rim环形网格
def build_ring(side, n_ring=48):
    rim = np.array(cont[side]["rim_3d"], dtype=np.float64)
    c = cont[side]["center"]
    idx = np.linspace(0, len(rim), n_ring, endpoint=False).astype(int) % len(rim)
    rim_pts = rim[idx]
    center2d = np.array([c[0], c[2]])
    ring_data = []
    for r_scale, tag in [(1.0, "rim"), (1.15, "outer")]:
        ring = []
        for p in rim_pts:
            p2d = np.array([p[0], p[2]])
            dir2d = p2d - center2d
            n = np.linalg.norm(dir2d)
            dir2d = dir2d / n if n > 1e-6 else np.array([1.0, 0.0])
            new2d = center2d + dir2d * (n * r_scale)
            y = p[1] + (0.002 if tag == "outer" else 0.0)
            ring.append([new2d[0], y, new2d[1]])
        ring_data.append(np.array(ring))
    return ring_data

# 4. 对每侧建rim环
all_new = []
for side in ("L", "R"):
    rim_ring, outer_ring = build_ring(side)
    verts = []
    for i in range(len(rim_ring)):
        verts.append(tuple(rim_ring[i]))
    for i in range(len(outer_ring)):
        verts.append(tuple(outer_ring[i]))
    n = len(rim_ring)
    faces = []
    for i in range(n):
        a = i; b = (i + 1) % n
        c = n + (i + 1) % n; d = n + i
        faces.append((a, b, c, d))
    me_new = bpy.data.meshes.new(f"RimRing_{side}")
    me_new.from_pydata(verts, [], faces)
    me_new.update()
    ob = bpy.data.objects.new(f"RimRing_{side}", me_new)
    bpy.context.scene.collection.objects.link(ob)
    all_new.append(ob)
    print(f"{side}: rim环 {n}段, {len(faces)}面")

# 5. Shrinkwrap rim环到高模
for ob in all_new:
    sw = ob.modifiers.new("Shrink", 'SHRINKWRAP')
    sw.target = hi
    sw.wrap_method = 'NEAREST_SURFACEPOINT'
    sw.offset = 0.0
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier="Shrink")
    print(f"{ob.name} 已贴合高模")

# 6. 合并rim环到低模
bpy.ops.object.select_all(action='DESELECT')
for ob in all_new:
    ob.select_set(True)
head.select_set(True)
bpy.context.view_layer.objects.active = head
bpy.ops.object.join()
print(f"合并后: {head.name} 顶点={len(head.data.vertices)} 面={len(head.data.polygons)}")

# 7. 删除高模(不保存) - 关键: 先确保高模不在场景里
del_names = []
for o in list(bpy.data.objects):
    if o.type == 'MESH' and len(o.data.vertices) > 500000:
        del_names.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
for nm in del_names:
    print(f"删除高模: {nm}")

# 8. 保存(确认只剩低模)
print(f"保存前场景对象: {[o.name for o in bpy.data.objects if o.type=='MESH']}")
bpy.ops.wm.save_mainfile(filepath=OUT_BLEND)
print(f"已保存: {OUT_BLEND}")
print("RIM_RING_DONE")
