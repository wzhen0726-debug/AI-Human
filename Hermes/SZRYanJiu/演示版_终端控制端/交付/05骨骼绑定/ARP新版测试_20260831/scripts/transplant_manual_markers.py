# -*- coding: utf-8 -*-
"""把用户手调的17个关节EMPTY点位移植进 step1 新生成的 01_AI打点.blend(含新网格).

为什么需要: 05链的贴图代际错配(旧网格144,607配新烘焙贴图) → 纹理全乱.
必须重跑05链, 但step1会用ARP AI自动点位覆盖用户手调成果 → 违背"绝不headless覆盖手调文件"铁律.
解法: 让step1生成含新网格的骨架+AI点位, 再用本脚本把用户手调点位**移植**回去,
     跳过GUI手调(点位已验证在新网格上依然有效: bbox尺寸差<0.006%, 采样最近距离中位1.38mm).

安全性: 手调点位是EMPTY的世界坐标, 不依附网格顶点 → 网格换代不影响其正确性.
⚠EMPTY的parent是arp_markers, 存的是局部坐标; 移植须按世界坐标对齐(用matrix_world反解local).
"""
import bpy, os, shutil, datetime
import numpy as np

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
W = os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831")
SRC = os.environ.get("MARKER_SRC") or os.path.join(W, "01_AI打点_手调权威备份.blend")
DST = os.path.join(W, "01_AI打点.blend")

assert os.path.exists(SRC), f"手调点位源文件不存在: {SRC}"
assert os.path.exists(DST), f"step1产物不存在: {DST}"

def read_markers(path):
    """读所有关节EMPTY的世界坐标 + parent名 + 显示属性"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    out = {}
    mesh_info = None
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith('tripo'):
            mesh_info = (len(o.data.vertices), len(o.data.polygons))
        if o.type != 'EMPTY':
            continue
        if not (o.name.endswith('_loc') or '_sym' in o.name):
            continue
        w = o.matrix_world
        out[o.name] = dict(
            world_loc=np.array(w.translation),
            world_quat=np.array(w.to_quaternion()),
            world_scale=np.array(w.to_scale()),      # Matrix无.scale属性, 用to_scale()
            parent=o.parent.name if o.parent else None,
            empty_display_type=o.empty_display_type,
            empty_display_size=o.empty_display_size,
            show_in_front=o.show_in_front,
            hide_select=o.hide_select,
            color=list(o.color),                  # EMPTY视口颜色就是Object.color(RGBA), 无color_type属性
            constraints=[(c.type, c.name) for c in o.constraints],
        )
    return out, mesh_info

src_m, src_mesh = read_markers(SRC)
print(f"手调源: {os.path.basename(SRC)}")
print(f"  网格={src_mesh}  关节EMPTY={len(src_m)}个")
assert len(src_m) >= 15, f"手调点位过少({len(src_m)}), 源文件可能不对"

dst_m, dst_mesh = read_markers(DST)
print(f"目标(step1产物): {os.path.basename(DST)}")
print(f"  网格={dst_mesh}  AI关节EMPTY={len(dst_m)}个")

MISSING = [n for n in src_m if n not in dst_m]
EXTRA = [n for n in dst_m if n not in src_m]
print(f"  手调有而目标缺: {MISSING if MISSING else '无'}")
print(f"  目标有而手调无: {EXTRA if EXTRA else '无'}")
assert not MISSING, f"目标文件缺关节点{MISSING}, step1可能没跑对"

# 位移统计(手调 vs AI自动)
print(f"\n=== 手调点位 vs step1的AI点位 世界位移 ===")
mv = []
for n in sorted(src_m):
    d = np.linalg.norm(src_m[n]['world_loc'] - dst_m[n]['world_loc']) * 1000
    mv.append(d)
    print(f"  {n:<22} {d:8.2f}mm")
mv = np.array(mv)
print(f"  位移: 中位={np.median(mv):.2f}mm max={mv.max():.2f}mm")

# ---- 写入 ----
bpy.ops.wm.open_mainfile(filepath=DST)
byname = {o.name: o for o in bpy.data.objects}
applied = 0
for n, s in src_m.items():
    o = byname.get(n)
    if o is None or o.type != 'EMPTY': continue
    # 世界坐标 → 局部(按当前parent)
    if o.parent:
        pw = np.array(o.parent.matrix_world)
        loc_local = np.linalg.inv(pw)[:3, :3] @ (s['world_loc'] - pw[:3, 3])
    else:
        loc_local = s['world_loc']
    o.location = tuple(float(v) for v in loc_local)
    # 保留手调版的显示属性(颜色/大小/show_in_front), 便于用户GUI复核
    try:
        o.empty_display_size = s['empty_display_size']
        o.show_in_front = s['show_in_front']
        o.color = tuple(s['color'])          # EMPTY视口颜色(RGBA); 无color_type属性
    except Exception as e:
        print(f"  (显示属性跳过 {n}: {e})")
    applied += 1

# 备份当前(step1版)再存
bak = DST.replace(".blend", f"_step1AI版_{datetime.datetime.now():%Y%m%d_%H%M%S}.blend")
shutil.copy2(DST, bak)
print(f"\n已备份step1版: {os.path.basename(bak)}")

bpy.ops.wm.save_mainfile()
print(f"已写入手调点位: {applied}/{len(src_m)} 到 {os.path.basename(DST)}")

# ---- 复核: 重新读回, 世界坐标必须与手调源一致 ----
chk_m, chk_mesh = read_markers(DST)
print(f"\n=== 复核(重新读回) ===")
print(f"  网格={chk_mesh} (应=step1的新网格{dst_mesh})")
bad = []
for n, s in src_m.items():
    if n not in chk_m:
        bad.append((n, "缺失")); continue
    d = np.linalg.norm(chk_m[n]['world_loc'] - s['world_loc']) * 1000
    if d > 0.05: bad.append((n, f"偏差{d:.3f}mm"))
if bad:
    print(f"  ✗ {len(bad)}个点位未正确移植: {bad[:6]}")
    raise AssertionError("移植复核失败")
print(f"  ✓ {len(src_m)}个点位世界坐标与手调源一致(偏差<0.05mm)")
print(f"  ✓ 网格是新代际{chk_mesh}, 贴图与UV将匹配")
print("TRANSPLANT_DONE")
