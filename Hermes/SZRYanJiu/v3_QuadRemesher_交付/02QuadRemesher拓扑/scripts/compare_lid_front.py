"""定量对比: 高模(01_1眼窝) vs 低模(02_qr) 的眼睑缘最前点是否后退.
眼睑缘后退 = 眼球裸露 = 显瞪(正面) + 侧面无眼皮包裹.
方法: 眼心z高度±1.5mm横截面, |x-眼心x|<22mm, 取该带最靠前皮肤的y."""
import bpy, os, json
import numpy as np

DELIVERY = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付"
HI_BLEND = os.path.join(DELIVERY, "01A眼窝与眼球", "models", "01_1_eye_socket.blend")
LOW_BLEND = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
XZ_JSON = os.path.join(DELIVERY, "01A眼窝与眼球", "screenshots", "3ddfa", "eyelid_contour_manual.json")
cont = json.load(open(XZ_JSON, encoding="utf-8"))
centers = {s: np.array(cont[s]["center"], dtype=np.float64) for s in ("L", "R")}

def lid_front(blend_path, label):
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    head = max([o for o in bpy.data.objects if o.type == 'MESH'],
               key=lambda o: len(o.data.vertices))
    hp = np.array([head.matrix_world @ v.co for v in head.data.vertices])
    print(f"--- {label}: {head.name} 顶点={len(hp)} ---")
    for side, c in centers.items():
        # 眼心z高度±1.5mm横截面, 横向±22mm
        m = (np.abs(hp[:, 2] - c[2]) < 0.0015) & (np.abs(hp[:, 0] - c[0]) < 0.022)
        band = hp[m]
        # 最靠前(y最小)的点 = 眼睑缘/眼角最前突
        fy = band[:, 1].min()
        # 开口平面y(用户标记, 定案参考)
        rim_y = c[1]
        print(f"{side}: 眼睑横带最前皮肤y={fy*1000:.2f}mm  开口平面y={rim_y*1000:.2f}mm  眼睑缘相对开口平面{'前' if fy<rim_y else '后'}{abs(fy-rim_y)*1000:.2f}mm")
    return None

lid_front(HI_BLEND, "高模(01_1眼窝定案)")
lid_front(LOW_BLEND, "低模(02_qr_150k)")
print("LID_COMPARE_DONE")
