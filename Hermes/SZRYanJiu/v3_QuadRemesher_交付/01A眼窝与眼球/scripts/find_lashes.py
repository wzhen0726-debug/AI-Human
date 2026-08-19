"""find_lashes: 在贴图上定位眼区睫毛(深色细线)的位置
眼窝碗面avg_uv: L=(0.0770,0.0595) R=(0.5752,0.1090)
扫描这些UV周围区域, 找深色条纹(睫毛应是暗色细长结构)
"""
import bpy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eye_socket_config import *

bpy.ops.wm.open_mainfile(filepath=OUT_BLEND)
obj = [o for o in bpy.data.objects if o.type == 'MESH' and 'tripo' in o.name][0]
tex_img = None
for mat in obj.data.materials:
    if mat and mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type == 'TEX_IMAGE' and n.image:
                tex_img = n.image
W, H = tex_img.size
print(f"贴图: {tex_img.name} {W}x{H}")

# 导出眼区UV周围区域为PNG, 便于PIL分析和肉眼查看
from PIL import Image
import numpy as np
px = np.array(tex_img.pixels[:], dtype=np.float32).reshape(H, W, 4)

for side, cu, cv in [("L", 0.0770, 0.0595), ("R", 0.5752, 0.1090)]:
    # 碗面avg_uv周围 ±0.025 (覆盖整个眼窝开口+眼睑缘)
    half = 0.025
    x0, x1 = int((cu-half)*W), int((cu+half)*W)
    y0, y1 = int((cv-half)*H), int((cv+half)*H)
    x0, y0 = max(0,x0), max(0,y0); x1, y1 = min(W,x1), min(H,y1)
    crop = px[y0:y1, x0:x1, :3]
    # 保存放大图
    img = Image.fromarray((crop*255).astype(np.uint8))
    img = img.resize((800, 800), Image.NEAREST)
    out = os.path.join(os.path.dirname(SHOT_DIR) if False else SHOT_DIR, f"tex_zone_{side}.png")
    img.save(out)
    gray = crop.mean(axis=2)
    dark = gray < 0.35
    print(f"\n{side} 眼区贴图块 UV中心=({cu},{cv}) 范围[{cu-half:.3f},{cu+half:.3f}]x[{cv-half:.3f},{cv+half:.3f}]")
    print(f"  深色像素占比(<0.35): {dark.mean()*100:.1f}% (睫毛/眼线应是深色)")
    print(f"  最暗区域位置(行): ", end="")
    row_dark = dark.mean(axis=1)
    dark_rows = np.where(row_dark > 0.3)[0]
    if len(dark_rows):
        print(f"y={dark_rows[0]}~{dark_rows[-1]} (贴图局部坐标, 占比>{30}%)")
    else:
        print("无显著深色行")
    print(f"  已保存: {out}")
print("\n完成")
