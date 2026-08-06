
import bpy, numpy as np
REPAIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01高模修复与黏连检测\models\01_highpoly_repair.blend"
bpy.ops.wm.open_mainfile(filepath=REPAIR)
obj = max((o for o in bpy.data.objects if o.type=='MESH'), key=lambda o: len(o.data.vertices))
nv = len(obj.data.vertices)
V = np.empty(nv*3, dtype=np.float32); obj.data.vertices.foreach_get("co", V); V=V.reshape(nv,3).astype(np.float64)
# 眉弓: 眼上方 z≈1.70-1.72, x在眼区
brow = V[(V[:,2]>1.70)&(V[:,2]<1.72)&(np.abs(V[:,0])<0.05)]
# 鼻梁: z≈1.60-1.64, x≈0
nose = V[(V[:,2]>1.60)&(V[:,2]<1.64)&(np.abs(V[:,0])<0.015)]
print(f"眉弓最前y={brow[:,1].min():.4f}  鼻梁最前y={nose[:,1].min():.4f}")
# 眉弓-鼻梁轮廓线(侧视) 在眼球中心z=1.6711处的y值(线性插值)
z_b, y_b = 1.71, brow[:,1].min()
z_n, y_n = 1.62, nose[:,1].min()
z_e = 1.6711
y_line = y_b + (y_n-y_b)*(z_e-z_b)/(z_n-z_b)
print(f"眉弓-鼻梁轮廓线在眼高z={z_e}处的y={y_line:.4f}")
print(f"角膜顶点要退到此线内侧(略大y, 即>{y_line:.4f})")
print(f"当前眼球前极(EYE_PUSH_BACK=0.012): 拟合球心y(-0.1202)+0.012-0.0145={-0.1202+0.012-0.0145:.4f}")
