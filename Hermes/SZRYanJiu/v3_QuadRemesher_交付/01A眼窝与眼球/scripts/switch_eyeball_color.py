"""眼睛颜色切换工具 — 对已摆好的01_2 blend换色, 不重跑全流程.
用法: python switch_eyeball_color.py <Color> [bloodline]
  Color: Blue/Brown/Green/Hazel/Red/Violet/Zombie
  bloodline: base(默认)/Bld1/Bld2
也可改eye002_config.py的EYE_COLOR/EYE_BLOODLINE后直接运行(无参数)."""
import bpy, os, sys, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import OUT_BLEND, SHOT_DIR
from eye002_config import EYE002_REGISTRY, EYE_COLOR as DEF_COLOR, EYE_BLOODLINE as DEF_BLD

def switch(color, bloodline, blend_path):
    reg = json.load(open(EYE002_REGISTRY, encoding="utf-8"))
    variants = reg["colors"].get(color)
    if not variants:
        raise SystemExit(f"未知颜色'{color}', 可选: {', '.join(reg['colors'].keys())}")
    if bloodline not in variants:
        print(f"注: {color}无{bloodline}, 回退base")
        bloodline = "base"
    tex_path = variants[bloodline]
    tex_name = os.path.basename(tex_path)
    img = bpy.data.images.load(tex_path, check_existing=True)
    img.name = tex_name

    bpy.ops.wm.open_mainfile(filepath=blend_path)
    eyes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("Eye002")]
    if not eyes:
        raise SystemExit("blend中无Eye002_*对象, 请先跑run_eyeball_v2.py")
    swapped = 0
    for eye in eyes:
        for slot in eye.data.materials:
            if not slot or not slot.use_nodes:
                continue
            for n in slot.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image and "_D" in n.image.name:
                    n.image = img
                    swapped += 1
    print(f"切换 {len(eyes)}只眼 → {color}/{bloodline}: 替换{swapped}个贴图节点 → {tex_name}")
    bpy.ops.wm.save_mainfile()
    print(f"Saved: {blend_path}")

if __name__ == "__main__":
    color = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else DEF_COLOR
    bld = sys.argv[sys.argv.index("--") + 2] if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 2 else DEF_BLD
    switch(color, bld, OUT_BLEND)
