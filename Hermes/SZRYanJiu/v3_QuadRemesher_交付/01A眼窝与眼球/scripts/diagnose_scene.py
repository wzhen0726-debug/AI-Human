"""diagnose_scene: 检查 blend 场景对象/灯光/材质/渲染设置"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)

print("=== 场景所有对象 ===")
for o in bpy.data.objects:
    mats = [m.name for m in o.data.materials] if o.type == 'MESH' else []
    print(f"  {o.name}: type={o.type}, mats={mats}, "
          f"hide_render={o.hide_render}, hide_viewport={o.hide_get()}")

print("\n=== 灯光 ===")
lights = [o for o in bpy.data.objects if o.type == 'LIGHT']
if not lights:
    print("  !! 场景无任何灯光")
for l in lights:
    print(f"  {l.name}: type={l.data.type}, energy={l.data.energy}")

print("\n=== 世界环境 ===")
w = bpy.context.scene.world
if w:
    bg = w.node_tree.nodes.get('Background') if w.use_nodes else None
    if bg:
        c = bg.inputs['Color'].default_value
        print(f"  背景色=({c[0]:.3f},{c[1]:.3f},{c[2]:.3f}) 强度={bg.inputs['Strength'].default_value}")
else:
    print("  !! 无世界环境")

print("\n=== 渲染引擎设置 ===")
s = bpy.context.scene
print(f"  engine={s.render.engine}")
print(f"  EEVEE: use_raytracing={getattr(s.eevee, 'use_raytracing', 'N/A')}")

print("\n=== 材质细节(有贴图的) ===")
for m in bpy.data.materials:
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                print(f"  材质[{m.name}] 节点[{n.name}] 贴图[{n.image.name}] "
                      f"packed={'YES' if n.image.packed_file else 'no'}")
                bsdf = [x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED']
                if bsdf:
                    b = bsdf[0]
                    print(f"    BSDF: base_color_link={'贴图' if b.inputs['Base Color'].is_linked else '断开!'}")
                    # 检查贴图→BSDF 连接
                    linked = [l for l in m.node_tree.links if l.to_node == b and l.to_socket.name == 'Base Color']
                    print(f"    Base Color 输入连接: {[(l.from_node.name, l.from_socket.name) for l in linked] or '无!'}")
