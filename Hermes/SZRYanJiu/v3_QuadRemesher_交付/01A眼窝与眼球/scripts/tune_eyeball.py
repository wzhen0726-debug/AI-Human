"""眼球位置微调对比: 一次Blender运行内渲染2组候选(凸出量/高度), 供用户挑选.
用法: 改下方CANDIDATES后运行. 每组渲染正面+特写."""
import bpy, os, sys, json
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *
from eye002_config import *
import run_eyeball_v2 as rev2

# 候选: (标签, 凸出量mm, 高度偏移mm)
# 凸出量 = 角膜顶点凸出眼睑缘平面的毫米数. 越大眼球越靠前(更凸), 越小/负值越靠里.
# 高度偏移 = 虹膜中心相对眼开口中心的上抬量. 越小眼球越靠下.
# 说明: 早前v2.1验收位置≈凸出2.8mm; v3首版给0.6mm用户仍觉凸 → 提供多档对比挑选.
CANDIDATES = [
    ("A_凸2.8_高0.7", 2.8, 0.7),   # 参照: 回到早前验收的001位置
    ("B_凸1.0_高0.4", 1.0, 0.4),   # 往里收1.8mm, 略降低
    ("C_凸负1.0_高0.2", -1.0, 0.2),# 再往里收, 角膜收到眼睑缘后, 明显降低
]

def render_shots(tag):
    from eyeball_config import SHOT_DIR
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 800; scene.render.resolution_y = 800
    eyes = [o for o in bpy.data.objects if o.name.startswith("Eye002")]
    fc = sum((o.location for o in eyes), Vector((0,0,0))) / 2
    cam = bpy.data.objects.get("Camera") or bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    if not cam.users_scene:
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 85
    for name, pos in [("front", Vector((fc.x, fc.y - 0.30, fc.z))),
                      ("close", Vector((fc.x, fc.y - 0.12, fc.z)))]:
        cam.location = pos
        cam.rotation_euler = (fc - pos).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(SHOT_DIR, f"tune_{tag}_{name}.png")
        bpy.ops.render.render(write_still=True)

def main():
    bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)  # 已摆好眼球的blend
    cont = json.load(open(EYE_XZ_JSON, encoding="utf-8"))
    eyes = {o.name: o for o in bpy.data.objects if o.name.startswith("Eye002")}

    for tag, prot, zoff in CANDIDATES:
        for side in ("L", "R"):
            eye = eyes[f"Eye002_{side}"]
            c = cont[side]["center"]
            corneal_dist = rev2.measure_corneal_dist(eye)
            cy = c[1] + corneal_dist - prot / 1000.0
            eye.location = (c[0], cy, c[2] + zoff / 1000.0)
            print(f"{tag} {side}: 球心y={cy:.4f} 角膜顶点y={cy-corneal_dist:.4f} z={c[2]+zoff/1000:.4f}")
        render_shots(tag)
    print("done — 注意: blend未保存(只渲染对比), 选定后改eye002_config重跑run_eyeball_v2.py")

if __name__ == "__main__":
    main()
