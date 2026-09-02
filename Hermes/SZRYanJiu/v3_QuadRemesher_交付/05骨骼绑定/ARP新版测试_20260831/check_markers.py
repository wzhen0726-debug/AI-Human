"""ARP全新测试 — 点位合理性自检 (读当前blend的标记点, 打印量化的检查结果)
用法: blender -b <blend文件> --python check_markers.py"""
import bpy, sys

EXPECTED_Z = {  # 速览表数值(米)
    "chin_loc": 1.59, "neck_loc": 1.47, "shoulder_loc": 1.435,
    "elbow_loc": 1.435, "hand_loc": 1.435, "hand_tip_loc": 1.435,
    "root_loc": 0.88, "thigh_loc": 0.88, "knee_loc": 0.52, "foot_loc": 0.14,
}

def w(o): return o.matrix_world.translation

pts = {o.name: o for o in bpy.data.objects if o.name.endswith('_loc') or '_sym' in o.name}
print(f"\n===== 点位自检 ({len(pts)}点) =====")
warn = 0

# 1. 左右对称
for base in ["shoulder", "elbow", "hand", "hand_tip", "thigh", "knee", "foot"]:
    a, b = pts.get(base + "_loc"), pts.get(base + "_loc_sym")
    if not (a and b): continue
    dx = abs(abs(w(a).x) - abs(w(b).x)); dz = abs(w(a).z - w(b).z)
    if dx > 0.01 or dz > 0.01:
        print(f"[对称] {base}: |x|差{dx*100:.1f}cm z差{dz*100:.1f}cm  ← 不对称")
        warn += 1

# 2. 高度参考(容差±5cm)
for n, zref in EXPECTED_Z.items():
    o = pts.get(n)
    if not o: continue
    d = (w(o).z - zref) * 100
    flag = "  ← 偏差偏大" if abs(d) > 5 else ""
    if abs(d) > 5: warn += 1
    print(f"[高度] {n}: z={w(o).z:.3f} (参考{zref}, 差{d:+.1f}cm){flag}")

# 3. T-pose 手臂水平线
arm_z = [w(pts[n]).z for n in ["shoulder_loc","elbow_loc","hand_loc","hand_tip_loc"] if n in pts]
if arm_z and max(arm_z) - min(arm_z) > 0.03:
    print(f"[手臂] 肩肘腕指尖z差{(max(arm_z)-min(arm_z))*100:.1f}cm  ← T-pose应同高(±3cm)")
    warn += 1

# 4. 链条顺序(手臂x递增, 腿z递减)
chain = [n for n in ["shoulder_loc","elbow_loc","hand_loc","hand_tip_loc"] if n in pts]
xs = [w(pts[n]).x for n in chain]
if any(xs[i+1] < xs[i] - 0.01 for i in range(len(xs)-1)):
    print(f"[链条] 手臂x未递增: {[f'{x:.2f}' for x in xs]}  ← 顺序异常")
    warn += 1
lz = [(n, w(pts[n]).z) for n in ["thigh_loc","knee_loc","foot_loc"] if n in pts]
if any(lz[i+1][1] > lz[i][1] + 0.01 for i in range(len(lz)-1)):
    print(f"[链条] 腿z未递减: {[(n, f'{z:.2f}') for n, z in lz]}  ← 顺序异常")
    warn += 1

# 5. 中线上点x应≈0
for n in ["chin_loc", "neck_loc", "root_loc"]:
    o = pts.get(n)
    if o and abs(w(o).x) > 0.01:
        print(f"[中线] {n}: x={w(o).x:.3f}  ← 应在正中线(x≈0)")
        warn += 1

# 6. 比例合理性
sh = pts.get("shoulder_loc"); th = pts.get("thigh_loc")
if sh and th:
    if abs(w(sh).x) < abs(w(th).x):
        print(f"[比例] 肩宽{abs(w(sh).x)*2:.2f}m < 胯宽{abs(w(th).x)*2:.2f}m  ← 异常(一般肩宽>胯宽)")
        warn += 1
el = pts.get("elbow_loc"); ha = pts.get("hand_loc")
if sh and el and ha:
    ue = (w(el) - w(sh)).length; ef = (w(ha) - w(el)).length
    r = ue / ef if ef > 0 else 0
    if not 0.7 < r < 1.4:
        print(f"[比例] 上臂{ue*100:.0f}cm/前臂{ef*100:.0f}cm 比值{r:.2f}  ← 异常(应0.7~1.4)")
        warn += 1
if th:
    kn = pts.get("knee_loc"); ft = pts.get("foot_loc")
    if kn and ft:
        thigh = (w(kn) - w(th)).length; shank = (w(ft) - w(kn)).length
        r = thigh / shank if shank > 0 else 0
        if not 0.75 < r < 1.3:
            print(f"[比例] 大腿{thigh*100:.0f}cm/小腿{shank*100:.0f}cm 比值{r:.2f}  ← 异常(应0.75~1.3)")
            warn += 1

# 7. root 应高于 thigh 约6-7cm(Hips骨盆上缘骑在大腿根上方, Mixamo实测差6.7cm)
rt = pts.get("root_loc")
if rt and th:
    d = (w(rt).z - w(th).z) * 100
    if not 4 < d < 9:
        print(f"[结构] root比thigh高{d:.1f}cm  ← 应高6-7cm(骨盆上缘在大腿根上方)")
        warn += 1

print(f"\n===== 自检完成: {'全部通过 ✓' if warn == 0 else f'{warn}项提示, 请人工核对上图示位置'} =====")
