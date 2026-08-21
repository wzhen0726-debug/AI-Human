"""检查眼睛模型002的Eye.blend结构: 对象/材质/贴图/UV."""
import bpy, os

BLEND = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\眼睛模型002\Eye.blend"
bpy.ops.wm.open_mainfile(filepath=BLEND)

print("=== objects ===")
for o in bpy.data.objects:
    print(f"  {o.type:8} {o.name!r} loc={[round(x,3) for x in o.location]}", end="")
    if o.type == 'MESH':
        print(f" verts={len(o.data.vertices)} faces={len(o.data.polygons)} mats={len(o.data.materials)}", end="")
        for i, m in enumerate(o.data.materials):
            print(f"\n      mat[{i}]={m.name!r}", end="")
    print()

print("\n=== materials ===")
for m in bpy.data.materials:
    print(f"  {m.name!r} use_nodes={m.use_nodes}")
    if m.use_nodes:
        for n in m.node_tree.nodes:
            extra = ""
            if n.type == 'TEX_IMAGE' and n.image:
                extra = f" img={n.image.name!r} {n.image.size[0]}x{n.image.size[1]}"
            print(f"      node {n.type} {n.label or n.name!r}{extra}")

print("\n=== images ===")
for im in bpy.data.images:
    print(f"  {im.name!r} {im.size[0]}x{im.size[1]} filepath={os.path.basename(im.filepath)!r}")
