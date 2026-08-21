"""补查: 用户手动调整后眼球的旋转/缩放是否变化(管线默认旋转0缩放1)."""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eyeball_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
for side in ("L", "R"):
    e = bpy.data.objects[f"Eye002_{side}"]
    r = e.rotation_euler
    s = e.scale
    print(f"{side}: rot=({r[0]:.4f},{r[1]:.4f},{r[2]:.4f}) rad ({r[0]*57.296:.2f},{r[1]*57.296:.2f},{r[2]*57.296:.2f})deg scale=({s[0]:.4f},{s[1]:.4f},{s[2]:.4f})")
print("done")
