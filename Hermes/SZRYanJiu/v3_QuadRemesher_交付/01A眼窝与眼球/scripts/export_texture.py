"""导出输入高模的打包贴图到png."""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
outdir = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots")
for img in bpy.data.images:
    print(f"[{img.name}] size={img.size} packed={img.packed_file is not None}")
    if img.size[0] > 0:
        p = os.path.join(outdir, "input_" + img.name.replace("/", "_") + ".png")
        img.filepath_raw = p
        img.save()
        print(f"  saved -> {p}")
print("DONE")
