"""结论文档素材渲染: 统一视角拍三个模型(输入原始/修复后/低模带眼球).
每个模型渲染正面+侧面+线框(低模), 自动适配模型尺寸."""
import bpy, os
import numpy as np
from mathutils import Vector

SZRY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu"
OUT = os.path.join(SZRY, "v3_QuadRemesher_交付", "汇报素材")
os.makedirs(OUT, exist_ok=True)

MODELS = [
    ("输入_原始Tripo高模", "GLB", os.path.join(SZRY, "原始模型", "AI生成高模", "01_tripoApose", "tripo001.glb")),
    ("修复后高模(含眼窝)", "BLEND", os.path.join(SZRY, "v3_QuadRemesher_交付", "01A眼窝与眼球", "models", "01_1_eye_socket.blend")),
    ("低模_带眼球", "BLEND", os.path.join(SZRY, "v3_QuadRemesher_交付", "02QuadRemesher拓扑", "02_qr_150k_with_eyes.blend")),
]

def setup_render():
    s = bpy.context.scene
    s.render.engine = 'BLENDER_EEVEE'
    s.render.resolution_x = 1000; s.render.resolution_y = 1100
    for nm in ("Key", "Fill", "Rim"):
        o = bpy.data.objects.get(nm)
        if o: bpy.data.objects.remove(o, do_unlink=True)
    if s.world is None:                       # factory settings 清空了world → 新建
        s.world = bpy.data.worlds.new("World")
    s.world.use_nodes = True
    bg = s.world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs['Color'].default_value = (0.62, 0.62, 0.64, 1.0); bg.inputs['Strength'].default_value = 0.6

def add_lights(center):
    s = bpy.context.scene
    for name, loc_rel, energy in [("Key", Vector((0.25, -1.2, 0.7)), 40),
                                  ("Fill", Vector((1.0, -0.4, 0.2)), 15),
                                  ("Rim", Vector((0, 1.2, 0.6)), 20)]:
        ld = bpy.data.lights.new(name, type='AREA'); ld.energy = energy; ld.size = 1.2
        lo = bpy.data.objects.new(name, ld); lo.location = center + loc_rel
        lo.rotation_euler = (center - lo.location).to_track_quat('-Z', 'Y').to_euler()
        s.collection.objects.link(lo)

def mesh_stats():
    pts = []
    nv = nf = 0
    for o in bpy.data.objects:
        if o.type == 'MESH':
            nv += len(o.data.vertices); nf += len(o.data.polygons)
            verts = o.data.vertices
            step = max(1, len(verts) // 5000)
            for i in range(0, len(verts), step):
                pts.append(o.matrix_world @ verts[i].co)
    pts = np.array(pts)
    return nv, nf, pts

for label, kind, path in MODELS:
    if kind == "GLB":
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        bpy.ops.wm.open_mainfile(filepath=path)
    # 给无材质对象基础灰(防纯黑)
    for o in bpy.data.objects:
        if o.type == 'MESH' and not o.data.materials:
            mat = bpy.data.materials.new("Base")
            mat.use_nodes = True
            mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.5, 0.44, 0.42, 1.0)
            o.data.materials.append(mat)
    nv, nf, pts = mesh_stats()
    mn, mx = pts.min(axis=0), pts.max(axis=0)
    center = Vector(((mn + mx) / 2).tolist())
    size = float((mx - mn).max())
    print(f"=== {label}: 顶点={nv} 面={nf} 尺寸={size*1000:.0f}mm center=({center.x:.3f},{center.y:.3f},{center.z:.3f}) ===")
    setup_render(); add_lights(center)
    cam = bpy.data.objects.get("Camera")
    if cam is None:
        cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
        bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.data.lens = 85
    dist = size * 1.35
    for tag, off in [("front", Vector((0, -dist, size*0.05))), ("side", Vector((dist, 0, size*0.05)))]:
        cam.location = center + off
        cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.scene.render.filepath = os.path.join(OUT, f"{label}_{tag}.png")
        bpy.ops.render.render(write_still=True)
    # 低模加一张线框
    if "低模" in label:
        for o in bpy.data.objects:
            if o.type == 'MESH' and 'Eye' not in o.name:
                o.display_type = 'WIRE'
                # 隐藏眼球看头部拓扑; 眼球单独保留实体
        bpy.context.scene.render.filepath = os.path.join(OUT, f"{label}_wire.png")
        bpy.ops.render.render(write_still=True)
    print(f"  已渲染 {label}")
print("CONCLUSION_RENDERS_DONE")
