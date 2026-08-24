"""制作演示用 blend: 双视口(正视+侧视) + 两眼选中 + 移动工具 + 联动同步 + 实时数值.
基于当前定案的 01_2_eyeball_placed.blend, 输出 演示_眼球调整.blend.
打开即用: 拖任意一只眼球, 另一只自动镜像同步; 左上角显示偏移毫米数."""
import bpy, os, sys, json
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

OUT_DIR = os.path.dirname(OUT_BLEND)
DEMO_BLEND = os.path.join(OUT_DIR, "演示_眼球调整.blend")
DRIVER_SCRIPT_NAME = "eyeball_sync_driver.py"

# ---------- 1. 生成联动+数值显示的 driver 脚本(内嵌进blend, 打开自动运行) ----------
DRIVER_SRC = r'''
import bpy, json
from bpy.app.handlers import persistent

_CONTOUR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\screenshots\3ddfa\eyelid_contour_manual.json"
_state = {"L": None, "R": None}   # 记录上一帧位置, 用于检测哪只被移动

def _defaults():
    try:
        cont = json.load(open(_CONTOUR, encoding="utf-8"))
        return {s: cont[s]["center"] for s in ("L", "R")}
    except Exception:
        return None

def _sync_and_label():
    """检测被移动的眼, 镜像同步另一只, 并把偏移写到场景自定义属性供HUD显示."""
    cen = _defaults()
    if not cen:
        return
    for src_side, dst_side in (("L", "R"), ("R", "L")):
        src = bpy.data.objects.get(f"Eye002_{src_side}")
        dst = bpy.data.objects.get(f"Eye002_{dst_side}")
        if not src or not dst:
            continue
        cur = tuple(round(v, 6) for v in src.location)
        if _state[src_side] is not None and cur != _state[src_side]:
            # src 被移动了 → 镜像到 dst(镜像x: dst.x = -src.x 相对轮廓中心)
            c_src = cen[src_side]; c_dst = cen[dst_side]
            dx = src.location.x - c_src[0]
            dy = src.location.y - c_src[1]
            dz = src.location.z - c_src[2]
            dst.location = (c_dst[0] - dx, c_dst[1] + dy, c_dst[2] + dz)
            _state[dst_side] = tuple(round(v, 6) for v in dst.location)
            # 写HUD属性
            sc = bpy.context.scene
            sc["eye_dx"] = round(dx * 1000, 2)
            sc["eye_dy"] = round(dy * 1000, 2)
            sc["eye_dz"] = round(dz * 1000, 2)
        _state[src_side] = cur

@persistent
def _handler(scene, depsgraph):
    _sync_and_label()

def register():
    for s in ("L", "R"):
        o = bpy.data.objects.get(f"Eye002_{s}")
        _state[s] = tuple(round(v, 6) for v in o.location) if o else None
    if _handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_handler)
    print("[演示] 眼球联动同步已启动: 动一只, 另一只自动镜像")

def unregister():
    if _handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_handler)

if __name__ == "__main__":
    register()
'''

# ---------- 2. HUD 绘制(左上角显示偏移毫米数) ----------
HUD_SRC_NAME = "eyeball_hud.py"
HUD_SRC = r'''
import bpy, blf

def _draw():
    sc = bpy.context.scene
    dx = sc.get("eye_dx", 0.0); dy = sc.get("eye_dy", 0.0); dz = sc.get("eye_dz", 0.0)
    font_id = 0
    blf.size(font_id, 20)
    blf.color(font_id, 1.0, 0.85, 0.2, 1.0)
    blf.position(font_id, 20, 110, 0)
    blf.draw(font_id, "眼球偏移 (毫米):")
    blf.size(font_id, 18)
    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
    blf.position(font_id, 20, 80, 0)
    blf.draw(font_id, f"  前后: {dy:+.2f}   上下: {dz:+.2f}   左右: {dx:+.2f}")
    blf.size(font_id, 15)
    blf.color(font_id, 0.7, 0.7, 0.7, 1.0)
    blf.position(font_id, 20, 50, 0)
    blf.draw(font_id, "拖动眼球即可, 另一只自动镜像同步")

_handler = None
def register():
    global _handler
    _handler = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')
def unregister():
    global _handler
    if _handler:
        bpy.types.SpaceView3D.draw_handler_remove(_handler, 'WINDOW')
if __name__ == "__main__":
    register()
'''


def main():
    bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)

    # 内嵌两个脚本进 blend(打开自动运行)
    for name, src in [(DRIVER_SCRIPT_NAME, DRIVER_SRC), (HUD_SRC_NAME, HUD_SRC)]:
        old = bpy.data.texts.get(name)
        if old:
            bpy.data.texts.remove(old)
        t = bpy.data.texts.new(name)
        t.write(src)
        t.use_module = True   # 打开blend时自动运行

    # 选中两只眼球, 激活L
    bpy.ops.object.select_all(action='DESELECT')
    for s in ("L", "R"):
        o = bpy.data.objects.get(f"Eye002_{s}")
        if o:
            o.select_set(True)
    if bpy.data.objects.get("Eye002_L"):
        bpy.context.view_layer.objects.active = bpy.data.objects["Eye002_L"]

    bpy.ops.wm.save_as_mainfile(filepath=DEMO_BLEND)
    print(f"Saved demo: {DEMO_BLEND}")
    print("提示: 打开此blend时勾选'允许自动运行脚本'即可启用联动+数值显示")
    print("done")


if __name__ == "__main__":
    main()
