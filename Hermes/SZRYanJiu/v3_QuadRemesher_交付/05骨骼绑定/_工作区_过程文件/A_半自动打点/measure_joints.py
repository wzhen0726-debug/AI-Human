"""测量身体关节位置(骨骼绑定标记模板用) — 01A逻辑: 程序测量→标记初始位置→用户微调→镜像.
测量: 头顶/颈根/会阴/肩/肘/腕/膝/踝 (T-pose几何分析)
输出: landmarks/joints_measured.json + 控制台诊断
"""
import bpy, os, json
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BODY = os.path.join(BASE, "04纹理烘焙", "04_bake.blend")
OUT_DIR = os.path.join(BASE, "05骨骼绑定", "A_半自动打点")
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=BODY)
cands = [o for o in bpy.context.scene.objects if o.type == 'MESH' and 'eye' not in o.name.lower()]
obj = max(cands, key=lambda o: len(o.data.polygons))
mw = obj.matrix_world
pts = np.array([mw @ v.co for v in obj.data.vertices])
print(f"主体: {obj.name} 顶点={len(pts)}")

zmin, zmax = pts[:, 2].min(), pts[:, 2].max()
H = zmax - zmin
res = {}

def band(frac0, frac1):
    z0, z1 = zmin + H * frac0, zmin + H * frac1
    return pts[(pts[:, 2] >= z0) & (pts[:, 2] < z1)]

# ---- 1. 头顶: 顶部1%顶点均值 ----
top = pts[pts[:, 2] > zmax - 0.01 * H]
res["HeadTop"] = [float(top[:, 0].mean()), float(top[:, 1].mean()), float(zmax)]
print(f"头顶: {np.round(res['HeadTop'], 4)} (顶部{len(top)}顶点)")

# ---- 2. 颈根(头颈关节): 84%-90%带内找x跨度最小带(颈)的上缘 = 头颈交界 ----
# 注意: 不能从头顶往下扫(头本身跨度~0.18也<0.30会误判), 必须从肩部往上扫
neck_best = None
for frac in np.arange(0.84, 0.90, 0.005):
    b = band(frac, frac + 0.01)
    if len(b) < 50:
        continue
    span = b[:, 0].max() - b[:, 0].min()
    if neck_best is None or span < neck_best[1]:
        neck_best = (frac, span, b)
if neck_best:
    frac, span, b = neck_best
    z_neck = zmin + H * (frac + 0.01)   # 窄带上缘=头颈交界
    res["NeckBase"] = [float(b[:, 0].mean()), float(b[:, 1].mean()), float(z_neck)]
    print(f"颈根(头颈交界): frac={frac:.3f} span={span:.3f} pos={np.round(res['NeckBase'], 4)}")

# ---- 3. 手臂带(T-pose): x跨度>1.0的z带 ----
arm_fracs = []
for frac in np.arange(0.60, 0.95, 0.005):
    b = band(frac, frac + 0.01)
    if len(b) < 50:
        continue
    span = b[:, 0].max() - b[:, 0].min()
    if span > 1.0:
        arm_fracs.append(frac)
arm_zc = zmin + H * (min(arm_fracs) + max(arm_fracs) + 0.01) / 2
arm_band = pts[(pts[:, 2] >= zmin + H * min(arm_fracs)) & (pts[:, 2] < zmin + H * (max(arm_fracs) + 0.01))]
hand_tip = arm_band[:, 0].max()
print(f"手臂带: frac=[{min(arm_fracs):.3f},{max(arm_fracs):.3f}] z中心={arm_zc:.4f} 手尖x={hand_tip:.4f}")

# ---- 4. 手臂y厚度剖面(x方向) → 找腕(手变薄处)/肘(局部最细) ----
xs = np.arange(0.15, hand_tip, 0.01)
prof = []
for x0 in xs:
    seg = arm_band[(arm_band[:, 0] >= x0) & (arm_band[:, 0] < x0 + 0.01)]
    if len(seg) < 10:
        prof.append(np.nan)
        continue
    prof.append(seg[:, 1].max() - seg[:, 1].min())
prof = np.array(prof)
print("手臂y厚度剖面(x: 厚度mm):")
for x0, t in zip(xs, prof):
    if not np.isnan(t):
        print(f"  x={x0:.2f}: {t*1000:.0f}mm ({int(((arm_band[:,0]>=x0)&(arm_band[:,0]<x0+0.01)).sum())}顶点)")

arm_center_y = float(arm_band[arm_band[:, 0] > 0.35][:, 1].mean())
res["_arm_zc"] = float(arm_zc)
res["_arm_y"] = arm_center_y
res["_hand_tip"] = float(hand_tip)

# ---- 4b. 肩/肘/腕: 用厚度剖面的突变点 ----
# 腕: 手掌起点 = 厚度从递减突然变大的x(0.79→0.82跳变处)
# 肘: 上臂最细处(0.35-0.50范围内的局部最小)
valid = [(x0, t) for x0, t in zip(xs, prof) if not np.isnan(t)]
wrist_x = None
for i in range(len(valid) - 3):
    x0, t = valid[i]
    x1, t1 = valid[i + 3]
    # 厚度在3cm内增加>35% = 手掌开始
    if t1 > t * 1.35 and x0 > 0.60:
        wrist_x = x0
        break
if wrist_x is None:
    wrist_x = hand_tip * 0.78   # 兜底: 手尖78%
elbow_cands = [(x0, t) for x0, t in valid if 0.30 <= x0 <= 0.55]
elbow_x = min(elbow_cands, key=lambda p: p[1])[0] if elbow_cands else hand_tip * 0.5
# 肩: 手臂与躯干连接处(厚度剖面起点附近的躯干边缘) → 用手臂带z中心, x=躯干半宽
sho_band = band(min(arm_fracs), max(arm_fracs) + 0.01)
sho_band = sho_band[(sho_band[:, 0] > 0.05) & (sho_band[:, 0] < 0.25)]
shoulder_x = float(sho_band[:, 0].mean() + 0.03) if len(sho_band) else 0.15
res["Shoulder_R"] = [shoulder_x, arm_center_y, float(arm_zc)]
res["Elbow_R"] = [float(elbow_x), arm_center_y, float(arm_zc)]
res["Wrist_R"] = [float(wrist_x), arm_center_y, float(arm_zc)]
print(f"肩R: {np.round(res['Shoulder_R'], 4)}")
print(f"肘R: x={elbow_x:.3f} pos={np.round(res['Elbow_R'], 4)}")
print(f"腕R: x={wrist_x:.3f} pos={np.round(res['Wrist_R'], 4)} (手尖={hand_tip:.3f})")

# ---- 5. 会阴: 从上往下找中心空隙(|x|<0.02顶点<20)的第一个带 = 腿分叉 ----
print("会阴扫描(frac: 全距/中心顶点数):")
crotch = None
for frac in np.arange(0.62, 0.35, -0.005):
    b = band(frac, frac + 0.01)
    if len(b) < 50:
        continue
    center = b[np.abs(b[:, 0]) < 0.02]
    span = b[:, 0].max() - b[:, 0].min()
    if frac % 0.05 < 0.006:
        print(f"  frac={frac:.3f} span={span:.3f} center={len(center)}")
    if crotch is None and len(center) < 20 and span < 0.45:
        crotch = zmin + H * (frac + 0.005)
        res["Crotch"] = [0.0, float(b[:, 1].mean()), float(crotch)]
        print(f"  → 会阴: frac={frac:.3f} pos={np.round(res['Crotch'], 4)}")
if "Crotch" not in res:
    res["Crotch"] = [0.0, 0.0, float(zmin + 0.48 * H)]
    print(f"  → 会阴(兜底48%身高): {np.round(res['Crotch'], 4)}")

# ---- 6. 右腿: x>0.03, z<会阴 → 腿宽剖面 → 膝(15-45%最细)/踝(底部最细) ----
leg = pts[(pts[:, 0] > 0.03) & (pts[:, 2] < res["Crotch"][2])]
print("右腿宽度剖面(frac: x跨度/中心x):")
leg_prof = []
for frac in np.arange(0.02, 0.50, 0.01):
    z0, z1 = zmin + H * frac, zmin + H * (frac + 0.01)
    seg = leg[(leg[:, 2] >= z0) & (leg[:, 2] < z1)]
    if len(seg) < 30:
        leg_prof.append((frac, None, None, None))
        continue
    w = seg[:, 0].max() - seg[:, 0].min()
    cx = (seg[:, 0].max() + seg[:, 0].min()) / 2
    cy = seg[:, 1].mean()
    leg_prof.append((frac, w, cx, cy))
    print(f"  frac={frac:.2f} z={z0:.3f} 宽={w*1000:.0f}mm 中心x={cx:.3f} y={cy:.3f}")

# 膝: 15-45%中宽度局部最小
knee_cands = [(f, w, cx, cy) for f, w, cx, cy in leg_prof if w is not None and 0.15 <= f <= 0.45]
if knee_cands:
    f, w, cx, cy = min(knee_cands, key=lambda t: t[1])
    res["Knee_R"] = [float(cx), float(cy), float(zmin + H * f)]
    print(f"膝R: frac={f:.2f} 宽={w*1000:.0f}mm pos={np.round(res['Knee_R'], 4)}")
# 踝: 2-14%中宽度最小
ank_cands = [(f, w, cx, cy) for f, w, cx, cy in leg_prof if w is not None and 0.02 <= f <= 0.14]
if ank_cands:
    f, w, cx, cy = min(ank_cands, key=lambda t: t[1])
    res["Ankle_R"] = [float(cx), float(cy), float(zmin + H * f)]
    print(f"踝R: frac={f:.2f} 宽={w*1000:.0f}mm pos={np.round(res['Ankle_R'], 4)}")

out = os.path.join(OUT_DIR, "joints_measured.json")
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"已保存: {out}")
print("MEASURE_DONE")
