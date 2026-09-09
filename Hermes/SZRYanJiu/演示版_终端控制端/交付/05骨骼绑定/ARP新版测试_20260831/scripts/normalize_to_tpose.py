# -*- coding: utf-8 -*-
"""03B 骨骼标准化: 把03绑定好的骨架 rest 开度对齐 Mixamo T-Pose, 网格跟随重摆.

用户决定(2026-09-09): ①全部55骨对齐标准T-Pose ②网格跟随重摆(不是只改骨骼朝向).

为什么这么做(治本):
  v3 retarget 靠 D=R_ref_rest^-1@W_ref(t) 增量补偿来"绕过"我们rest与Mixamo的差异.
  03B 把这个差异在 rest 层面一次性消除 → C=R_our^-1@R_ref → 单位矩阵,
  动画直接是绝对朝向匹配, 且不会重演v2的内八/猫步 —— v2病根是"骨骼扳竖直但网格没动"
  运行时蒙皮硬挤; 03B 是 rest 层面骨骼与网格一起重摆, 始终匹配.

算法:
  1. R_new_b = Mixamo T-Pose 的骨向(实测, 非硬编码)
  2. 骨长保持我们的(体型是我们的, 不照搬Mixamo) → 身高/四肢长度不变
  3. head 层级累积: 根骨位置不变; connect骨 head=父tail; 非connect骨 head=父delta变换
     → 关节重叠与连接关系保持
  4. 网格 LBS 跟随: v_new = Σ w_b·D_b(v) + (1-Σw)·v, D_b(v)=h_new+R_delta@(v-h_old)
     → 骨骼与网格相对关系不变(动画无扭折)
  5. 脚贴地修正: 腿从外展8°变直后垂直投影变长, 脚会下沉 → 整体平移使脚底回 z=0

实测依据(_prep_03B.py): 55/55骨有Mixamo对应; 腿部差异几乎纯外展/pitch(roll差仅0.05~0.22°)
  LeftUpLeg外展 +8.14°→+0.35° | LeftFoot脚尖 +8.45°→+1.55° | Hips已对齐0.01°
"""
import bpy, os, json, math, shutil, datetime, collections
import numpy as np
from mathutils import Matrix, Vector

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
W05 = os.path.join(D, "交付", "05骨骼绑定", "ARP新版测试_20260831")
RIG03 = os.path.join(W05, "03_骨骼绑定.blend")
OUT = os.path.join(W05, "03B_骨骼标准化.blend")
TP = os.path.join(D, "原始文件", "Mixamo动画文件", "T-Pose.fbx")

# ---------------- 工具 ----------------
def R3(M):
    """4x4/3x3 → 纯旋转3x3(逐列归一化去scale). Mixamo FBX的scale=0.01必须去掉,
    否则所有骨假报89.43°(上一版bug)."""
    A = np.array(M.to_3x3(), dtype=np.float64) if hasattr(M, "to_3x3") else np.array(M, dtype=np.float64)[:3, :3]
    for i in range(3):
        n = np.linalg.norm(A[:, i])
        if n > 1e-12: A[:, i] /= n
    return A

def M4(R, t):
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = t; return M

def to_mat(A):
    return Matrix([[float(A[i][j]) for j in range(4)] for i in range(4)])

def topo_order(info):
    """根→叶拓扑序(apply必须按此序, 否则connect骨的head会被父覆盖)"""
    order, rem = [], set(info)
    while rem:
        prog = False
        for n in sorted(rem):
            p = info[n]['parent']
            if p is None or p not in rem:
                order.append(n); rem.discard(n); prog = True
        if not prog:
            order.extend(sorted(rem)); break
    return order

# ---------------- 1. 打开03 ----------------
print("=" * 70)
print("03B 骨骼标准化: rest开度对齐Mixamo T-Pose + 网格跟随重摆")
print("=" * 70)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.open_mainfile(filepath=RIG03)
arm = next(x for x in bpy.data.objects if x.type == 'ARMATURE')
mesh = max([x for x in bpy.data.objects if x.type == 'MESH'], key=lambda x: len(x.data.vertices))
me = mesh.data
AW = np.array(arm.matrix_world); MW = np.array(mesh.matrix_world)
AWi, MWi = np.linalg.inv(AW), np.linalg.inv(MW)
print(f"骨架 '{arm.name}' {len(arm.data.bones)}骨 | 网格 '{mesh.name}' {len(me.vertices):,}顶点 {len(me.polygons):,}面")
print(f"arm.matrix_world loc={tuple(round(v,6) for v in arm.location)} scale={tuple(round(v,6) for v in arm.scale)}")
print(f"mesh.matrix_world loc={tuple(round(v,6) for v in mesh.location)} scale={tuple(round(v,6) for v in mesh.scale)}")

# 结构基线(结束时必须保持)
BASE_CONN = sum(1 for b in arm.data.bones if b.use_connect)
BASE_PARENT = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}

# ---------------- 2. 记录旧rest ----------------
ours = {}
for b in arm.data.bones:
    m = AW @ np.array(b.matrix_local)
    ours[b.name] = dict(R=R3(m), head=np.array(m[:3, 3]), length=float(b.length),
                        conn=bool(b.use_connect), parent=BASE_PARENT[b.name])
order = topo_order(ours)
assert len(order) == len(ours), f"拓扑序不完整 {len(order)}/{len(ours)}"

# 关节重叠基线
def overlap_stat(heads, Rs, lens, conn, par):
    ovl = tot = 0
    for n, p in par.items():
        if p and p in heads and conn[n]:
            tot += 1
            pt = heads[p] + Rs[p][:, 1] * lens[p]
            if np.linalg.norm(pt - heads[n]) < 1e-5: ovl += 1
    return ovl, tot
BASE_OVL, BASE_TOT = overlap_stat({n: o['head'] for n, o in ours.items()},
                                 {n: o['R'] for n, o in ours.items()},
                                 {n: o['length'] for n, o in ours.items()},
                                 {n: o['conn'] for n, o in ours.items()}, BASE_PARENT)
print(f"\n结构基线: 连接骨={BASE_CONN}/{len(ours)} 关节重叠={BASE_OVL}/{BASE_TOT}")

# ---------------- 3. Mixamo T-Pose 参考朝向 ----------------
# ⚠必须先记录导入前的对象集合: 上一版用 "if o not in (arm, mesh): remove" 反向删除,
#   把03里原有的39个对象全清了 — 包括 Eye002_L/R 眼球(retarget第48行assert眼球蒙皮到Head,
#   丢了04直接崩) 和37个ARP cs_*自定义形状. 只删"本次FBX导入新增的"才是安全的.
pre_objs = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=TP, use_manual_orientation=False)
new_objs = [o for o in bpy.data.objects if o not in pre_objs]
aref = max((x for x in new_objs if x.type == 'ARMATURE'), key=lambda x: len(x.data.bones))
wmr = np.array(aref.matrix_world)
ref = {}
for b in aref.data.bones:
    m = wmr @ np.array(b.matrix_local)
    ref[b.name.split(':')[-1]] = R3(m)
print(f"\nMixamo T-Pose '{aref.name}' {len(aref.data.bones)}骨 (scale={tuple(round(v,4) for v in aref.scale)} 已归一化去除)")

MISS = [n for n in ours if n not in ref]
if MISS:
    print(f"⚠ 无Mixamo对应({len(MISS)}骨, 保持原朝向): {MISS}")
# 只删本次FBX导入新增的对象(参考骨架+其附带网格), 原有对象一个不动
for o in new_objs:
    bpy.data.objects.remove(o, do_unlink=True)
print(f"已移除FBX新增的{len(new_objs)}个对象, 场景保留{len(bpy.data.objects)}个(含眼球/ARP自定义形状)")

# ---------------- 4. 计算新rest(层级累积) ----------------
head_new, R_new, tail_new = {}, {}, {}
for n in order:
    o = ours[n]
    p = o['parent']
    if p is None:
        hn = o['head'].copy()                                   # 根骨位置不变
    elif o['conn']:
        hn = tail_new[p].copy()                                 # connect: head=父新tail
    else:
        Rd = R_new[p] @ ours[p]['R'].T                          # 非connect: 按父delta变换
        hn = head_new[p] + Rd @ (o['head'] - ours[p]['head'])
    Rn = ref[n] if n in ref else o['R']                         # Mixamo朝向(无对应则保持)
    tn = hn + Rn[:, 1] * o['length']                            # 骨长保持我们的
    head_new[n], R_new[n], tail_new[n] = hn, Rn, tn

# ---------------- 5. 网格LBS跟随 ----------------
# ⚠必须对**所有**蒙皮网格做LBS, 不只是最大那个: 眼球Eye002_L/R(663顶点)蒙皮到Head,
#   Head骨rest移了+27.5mm, 而带ARMATURE修改器的网格在rest下形变=单位矩阵 →
#   若不同步变换眼球, 眼球会留在原位与新网格错位(眼球凸出/穿帮).
#   ARP的cs_*自定义形状是骨骼显示形状(顶点组=0, 无ARMATURE修改器), 不参与LBS, 保持原样.
H_old = np.array([ours[n]['head'] for n in order])
H_new = np.array([head_new[n] for n in order])
Rd_all = np.array([R_new[n] @ ours[n]['R'].T for n in order])
bidx = {n: i for i, n in enumerate(order)}

def _resolve_bone(nm):
    """顶点组名→骨名. 03骨架骨名无前缀(Head), 但眼球顶点组带mixamorig:前缀(mixamorig:Head)
    (前缀是后续retarget才加的). 匹配时须容忍前缀, 否则眼球被误判'无权重'跳过 → 与新网格错位."""
    if nm in bidx: return bidx[nm]
    bare = nm.split(':')[-1]
    return bidx.get(bare, -1)

def lbs_transform(obj):
    """对蒙皮网格obj做LBS, 返回(新object坐标, 旧世界坐标, 新世界坐标, Σw, VI,BI,W). 无权重则None."""
    mw = np.array(obj.matrix_world)
    m_o = obj.data
    vg = {g.index: g.name for g in obj.vertex_groups}
    c = np.empty(len(m_o.vertices)*3); m_o.vertices.foreach_get("co", c)
    Vo = c.reshape(-1, 3)
    Vw = Vo @ mw[:3, :3].T + mw[:3, 3]
    vi_l, bi_l, w_l = [], [], []
    for v in m_o.vertices:
        for g in v.groups:
            bi = _resolve_bone(vg.get(g.group, ""))
            if bi >= 0 and g.weight > 1e-8:
                vi_l.append(v.index); bi_l.append(bi); w_l.append(float(g.weight))
    if not w_l: return None
    VI = np.array(vi_l, dtype=np.int64); BI = np.array(bi_l, dtype=np.int64); W = np.array(w_l)
    Vn = np.zeros_like(Vw); Wsum = np.zeros(len(Vw))
    for bi in range(len(order)):
        sel = (BI == bi)
        if not sel.any(): continue
        idx = VI[sel]; w = W[sel][:, None]
        np.add.at(Vn, idx, w * (H_new[bi] + (Vw[idx] - H_old[bi]) @ Rd_all[bi].T))
        np.add.at(Wsum, idx, W[sel])
    # ⚠关键: ARP蒙皮权重**未归一化**(实测Σw中位0.9828, min0.897). Blender的Armature修改器
    #   默认 vertex_group_normalize=True → 变形按归一化权重算. 必须复现该行为.
    #   (错用 Vn += (1-Σw)*Vw 补偿会把权重缺口当"绑定到世界原点", 每顶点被往原位拉1.7~10% →
    #    旋转8°长骨上毫米级错位, 边长max变化167%、bbox深度+14.9%.)
    zw = Wsum < 1e-9
    Vn[~zw] /= Wsum[~zw, None]
    if zw.any(): Vn[zw] = Vw[zw]
    return Vo, Vw, Vn, Wsum, mw, VI, BI, W

# 找出所有蒙皮网格(有ARMATURE修改器且顶点组非空)
skinned = [o for o in bpy.data.objects if o.type == 'MESH' and o.vertex_groups
           and any(m.type == 'ARMATURE' for m in o.modifiers)]
print(f"\n蒙皮网格={len(skinned)}个: {[(o.name, len(o.data.vertices)) for o in skinned]}")

results = {}
for o in skinned:
    r = lbs_transform(o)
    if r: results[o.name] = r
    print(f"  '{o.name}': 顶点={len(o.data.vertices):,} Σw min={r[3].min():.6f} 中位={np.median(r[3]):.6f}" if r
          else f"  '{o.name}': 无有效权重, 跳过")

# 主网格(body)用于全局判定
BODY = mesh.name
Vo, Vw, Vn, Wsum, MW, VI, BI, W = results[BODY]
me = mesh.data
print(f"\n主网格世界坐标范围: z[{Vw[:,2].min()*1000:.1f},{Vw[:,2].max()*1000:.1f}]mm")
print(f"权重覆盖(主网格): Σw min={Wsum.min():.6f} 中位={np.median(Wsum):.6f} max={Wsum.max():.6f} → 已归一化")
print(f"  (复现Armature修改器 vertex_group_normalize=True 的行为)")

# pose骨rotation必须为零(否则rest重摆会与残留pose叠加)
pz = max((b.rotation_quaternion.angle for b in arm.pose.bones), default=0.0)
pl = max((b.location.length for b in arm.pose.bones), default=0.0)
print(f"pose残留: 最大rotation={math.degrees(pz):.6f}° 最大location={pl*1000:.6f}mm (须≈0, 否则需先clear pose)")
if pz > 1e-4 or pl > 1e-6:
    print("  → 清除pose变换")
    bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.rot_clear(); bpy.ops.pose.loc_clear(); bpy.ops.pose.scale_clear()
    bpy.ops.object.mode_set(mode='OBJECT')

# ---------------- 6. 脚贴地修正 ----------------
zmin_old, zmin_new = Vw[:, 2].min(), Vn[:, 2].min()
dz = zmin_old - zmin_new
print(f"\n脚贴地: 重摆前脚底z={zmin_old*1000:.2f}mm 重摆后={zmin_new*1000:.2f}mm → 整体平移 dz={dz*1000:+.2f}mm")
if abs(dz) > 1e-9:
    for nm, r in results.items():
        r[2][:, 2] += dz          # 每个蒙皮网格的新世界坐标同步平移
    for n in head_new:
        head_new[n] = head_new[n].copy(); head_new[n][2] += dz
        tail_new[n] = tail_new[n].copy(); tail_new[n][2] += dz

# ---------------- 7. 写回骨骼 ----------------
# ⚠必须用 EditBone.matrix 一次性设置(head+tail+roll 由setter正确推导).
#   上一版用 eb.roll=0 + eb.align_roll(局部X轴) → 实测与Mixamo**完整旋转差整整90.000°**
#   (骨向Y轴差0.000°, 但绕Y的roll差90°). 后果隐蔽且致命:
#     - rest外观完全正常(骨向对→head/tail对→网格LBS对→渲染PASS)
#     - 动画崩(骨骼roll错90° → 腿绕自身轴扭转 → 向前伸的脚被甩到z=+158mm, 参考仅-0.1mm;
#       脚z摆幅达参考3倍, walk腾空2帧)
#   而网格LBS用的是正确的R_new → 网格按正确朝向变了, 骨骼却写成roll差90° → 两者不匹配.
bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
ebs = arm.data.edit_bones
# 三遍走(connect约束会干扰matrix设置):
# 第1遍 全部断开 — 否则设父骨matrix时Blender立刻把父tail拉到**尚未更新**的子骨head,
#        骨长被破坏(实测最大变化78.33mm, ③自查FAIL)
for n in order:
    ebs[n].use_connect = False
# 第2遍 根→叶 设matrix(head+roll) + 恢复原骨长
for n in order:
    eb = ebs[n]
    eb.matrix = to_mat(AWi @ M4(R_new[n], head_new[n]))
    eb.length = ours[n]['length']          # 用记录的原始骨长(体型是我们的, 不照搬Mixamo)
# 第3遍 恢复connect — 此时子骨head已是新值, 父tail自动贴合 → 关节重叠保持
#        (层级累积已保证 connect骨head==父tail_new, 所以恢复后length不变)
for n in order:
    if ours[n]['conn']:
        ebs[n].use_connect = True
bpy.ops.object.mode_set(mode='OBJECT')

# ---------------- 8. 写回网格(所有蒙皮网格: 主网格 + 眼球) ----------------
print(f"\n写回蒙皮网格:")
for o in skinned:
    if o.name not in results: continue
    _Vo, _Vw, _Vn, _Ws, _mw, _vi, _bi, _w = results[o.name]
    _mo = o.data
    Vn_o = (_Vn - _mw[:3, 3]) @ np.array(_mw[:3, :3])            # 世界→该对象的object空间
    _mo.vertices.foreach_set("co", Vn_o.astype(np.float64).ravel())
    _mo.update()
    print(f"  '{o.name}': {len(_Vn):,}顶点已写回 (世界位移中位={np.median(np.linalg.norm(_Vn-_Vw,axis=1))*1000:.2f}mm)")
bpy.context.view_layer.update()

# ---------------- 9. 自查 ----------------
print("\n" + "=" * 70); print("自查"); print("=" * 70)
arm.data.update_tag()
bpy.context.view_layer.update()

# 9.1 结构一致
conn_n = sum(1 for b in arm.data.bones if b.use_connect)
par_now = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
par_diff = [n for n in par_now if par_now[n] != BASE_PARENT[n]]
hn2, Rn2, ln2 = {}, {}, {}
for b in arm.data.bones:
    m = AW @ np.array(b.matrix_local)
    hn2[b.name] = np.array(m[:3, 3]); Rn2[b.name] = R3(m); ln2[b.name] = float(b.length)
ovl2, tot2 = overlap_stat(hn2, Rn2, ln2, {b.name: b.use_connect for b in arm.data.bones}, par_now)
print(f"① 结构: 骨={len(arm.data.bones)}/{len(ours)} 连接骨={conn_n}/{BASE_CONN} 关节重叠={ovl2}/{tot2}(基线{BASE_OVL}/{BASE_TOT}) 父子变更={len(par_diff)}")
ok1 = (len(arm.data.bones) == len(ours)) and (conn_n == BASE_CONN) and (ovl2 == BASE_OVL) and not par_diff

# 9.2 朝向对齐Mixamo — **完整旋转矩阵**差(不只骨向!)
# ⚠原判据只比骨向R[:,1], 曾让"绕骨向轴roll差90°"的错误结果报0.0000°全过:
#   roll错不影响rest外观(骨向对→head/tail对→网格LBS对→渲染正常), 但动画会崩
#   (腿绕自身轴扭转, 脚被甩到z=+158mm). 必须查完整旋转 + 单独报roll分量.
def _aa(Rm):
    tr = np.clip((np.trace(Rm) - 1) / 2, -1, 1)
    a = math.degrees(math.acos(tr))
    ax = np.array([Rm[2,1]-Rm[1,2], Rm[0,2]-Rm[2,0], Rm[1,0]-Rm[0,1]])
    n = np.linalg.norm(ax)
    return a, (ax/n if n > 1e-9 else np.array([0.,0.,1.]))

ang_full, ang_dir, ang_roll = [], [], []
worst = None
for n in ours:
    if n not in ref: continue
    Ro, Rr = Rn2[n], ref[n]
    full, ax = _aa(Ro.T @ Rr)
    d = math.degrees(math.acos(np.clip(Ro[:,1].dot(Rr[:,1]), -1, 1)))
    rl = abs(math.degrees(math.asin(np.clip(np.dot(ax, Rr[:,1]) * math.sin(math.radians(full)), -1, 1))))
    ang_full.append(full); ang_dir.append(d); ang_roll.append(rl)
    if worst is None or full > worst[1]: worst = (n, full, d, rl)
ang_full = np.array(ang_full)
print(f"② 朝向对齐Mixamo: {len(ang_full)}骨")
print(f"    完整旋转差(axis-angle): 中位={np.median(ang_full):.4f}° max={ang_full.max():.4f}° (须<0.5°)")
print(f"    其中骨向(Y轴)差 max={max(ang_dir):.4f}° | roll分量差 max={max(ang_roll):.4f}°")
print(f"    最差骨: {worst[0]} 完整={worst[1]:.4f}° 骨向={worst[2]:.4f}° roll={worst[3]:.4f}°")
ok2 = ang_full.max() < 0.5

# 9.3 骨长保持
dl = np.array([abs(ln2[n] - ours[n]['length']) * 1000 for n in ours])
print(f"③ 骨长保持: 最大变化={dl.max():.6f}mm (目标<0.01mm) → 身高/四肢长度不变")
ok3 = dl.max() < 0.01

# 9.4 网格与骨骼相对关系(抽关节: 顶点到骨轴的距离)
def axis_dist(P, h, R):
    """点P到骨轴(h, 方向R[:,1])的距离"""
    d = P - h; ax = R[:, 1]
    return np.linalg.norm(d - ax * d.dot(ax))
# 取大腿/小腿中段的蒙皮顶点, 对比重摆前后到对应骨轴的距离
probe = []
for bn in ["LeftUpLeg", "LeftLeg", "RightUpLeg", "LeftArm", "LeftForeArm", "Spine1"]:
    if bn not in hn2: continue
    mid_o = ours[bn]['head'] + ours[bn]['R'][:, 1] * ours[bn]['length'] * 0.5
    mid_n = hn2[bn] + Rn2[bn][:, 1] * ln2[bn] * 0.5
    i = int(np.argmin(np.linalg.norm(Vw - mid_o, axis=1)))
    d_o = axis_dist(Vw[i], ours[bn]['head'], ours[bn]['R'])
    d_n = axis_dist(Vn[i], hn2[bn], Rn2[bn])
    probe.append((bn, d_o * 1000, d_n * 1000))
print(f"④ 网格-骨骼相对关系(顶点到骨轴距离, 应保持):")
ok4 = True
for bn, do, dn in probe:
    dev = abs(dn - do)
    flag = "✓" if dev < 2.0 else "⚠"
    if dev >= 2.0: ok4 = False
    print(f"    {bn:<14} 重摆前={do:8.2f}mm 后={dn:8.2f}mm 偏差={dev:6.3f}mm {flag}")

# 9.5 脚贴地 + 身高(身高变化是"外八→直腿"的必然几何结果, 不判FAIL, 但须分解可解释)
zmin_fin = Vn[:, 2].min(); zmax_fin = Vn[:, 2].max()
zmin_o, zmax_o = Vw[:, 2].min(), Vw[:, 2].max()
h_old, h_new = np.ptp(Vw[:, 2]), np.ptp(Vn[:, 2])
# 分解: 平移dz不影响ptp; 头顶变化 = 腿变直的垂直投影增加
top_delta = (zmax_new_pre := (Vn[:, 2].max() - dz)) - zmax_o      # 平移前的头顶变化
print(f"⑤ 脚贴地: 脚底z={zmin_fin*1000:.3f}mm (须≈0)")
print(f"   身高: 重摆前={h_old*1000:.1f}mm 后={h_new*1000:.1f}mm 变化={((h_new-h_old)*1000):+.1f}mm ({(h_new/h_old-1)*100:+.2f}%)")
print(f"   分解: 头顶{top_delta*1000:+.1f}mm(腿变直的垂直投影增加) + 脚底{-dz*1000:+.1f}mm(Foot骨下倾+脚跟旋转)")
ok5 = abs(zmin_fin) < 0.001 and abs(h_new / h_old - 1) < 0.05      # 脚必须贴地; 身高变化须<5%且可解释

# 9.8 刚性区检验(替代原先错误的"边长不变"判据)
#     ⚠原判据错在: 03B的目的就是改变姿态(外八A字→标准T-Pose), 手臂必然从当前角度摆成水平
#       (Shoulder差21°/Hand差14°), 腿从外展8°变直 → 边长与bbox变化是**预期结果不是缺陷**.
#       拿"网格不该变形"卡"就是要变形"的操作, 判据与目标自相矛盾.
#     正确判据: 单骨主导的顶点必须**刚性**移动(同骨两端边长0变化) → 检验LBS实现;
#               多骨混合区涂抹是LBS固有(等价于pose模式摆同样姿势), 不算缺陷, 只报告量级.
ei = np.empty(len(me.edges) * 2, dtype=np.int32); me.edges.foreach_get("vertices", ei)
E = ei.reshape(-1, 2)
Lo = np.linalg.norm(Vw[E[:, 0]] - Vw[E[:, 1]], axis=1)
Ln = np.linalg.norm(Vn[E[:, 0]] - Vn[E[:, 1]], axis=1)
rel = np.abs(Ln - Lo) / np.maximum(Lo, 1e-12)

# 每顶点的主导骨与**归一化后**的主导权重
# ⚠判据必须用归一化后权重: 原始Σw低至0.897(ARP未归一化), 若用原始dom_w>0.9判"刚性",
#   归一化后有效权重可达1.059且两端次骨混入不同 → 仍有相对位移(实测p99=5%), 判据失效.
#   只有"归一化后单骨独占(>0.9999)"的顶点才是纯刚体变换 T_A, 边长必须严格0变化.
dom_bone = np.full(len(Vw), -1, dtype=np.int64)
dom_w = np.zeros(len(Vw))
for k in range(len(W)):
    vi = VI[k]
    if W[k] > dom_w[vi]: dom_w[vi] = W[k]; dom_bone[vi] = BI[k]
dom_wn = np.where(Wsum > 1e-9, dom_w / np.maximum(Wsum, 1e-12), 0.0)   # 归一化后主导权重
same = (dom_bone[E[:, 0]] == dom_bone[E[:, 1]]) & (dom_bone[E[:, 0]] >= 0)
rigid = same & (dom_wn[E[:, 0]] > 0.9999) & (dom_wn[E[:, 1]] > 0.9999)
blend = ~rigid

r_rel = rel[rigid]; b_rel = rel[blend]
print(f"⑧ 刚性区检验(区分'LBS实现bug'与'LBS固有涂抹'):")
print(f"    刚性边(归一化后单骨独占>0.9999)={int(rigid.sum()):,}: 相对变化 中位={np.median(r_rel)*100:.8f}% "
      f"p99={np.percentile(r_rel,99)*100:.8f}% max={r_rel.max()*100:.8f}%  (须严格≈0 → LBS实现正确)")
print(f"    混合边(跨骨/低权重)={int(blend.sum()):,}: 中位={np.median(b_rel)*100:.3f}% "
      f"p95={np.percentile(b_rel,95)*100:.3f}% max={b_rel.max()*100:.3f}%  (LBS固有涂抹, 仅报告)")
bx_o = np.ptp(Vw, axis=0) * 1000; bx_n = np.ptp(Vn, axis=0) * 1000
print(f"    bbox(姿态变化的预期结果): 前={bx_o.round(1)}mm 后={bx_n.round(1)}mm 变化={((bx_n/bx_o-1)*100).round(2)}%")
print(f"      x={bx_o[0]:.0f}→{bx_n[0]:.0f}(手臂摆成水平T-Pose) y={bx_o[1]:.0f}→{bx_n[1]:.0f}(前后深度) z={bx_o[2]:.0f}→{bx_n[2]:.0f}(腿变直)")
# 面翻转检查(刚性变形不应翻法线)
def tri_normal(V):
    q = [me.polygons[i].vertices for i in range(len(me.polygons)) if len(me.polygons[i].vertices) == 3]
    if not q: return None
    q = np.array(q)
    a, b, c = V[q[:, 0]], V[q[:, 1]], V[q[:, 2]]
    n = np.cross(b - a, c - a)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
n_o, n_n = tri_normal(Vw), tri_normal(Vn)
if n_o is not None:
    dot = (n_o * n_n).sum(axis=1)
    flipped = int((dot < 0).sum())
    print(f"    三角面法线翻转={flipped}/{len(dot)} (须=0)")
    # 分层判据: 中位+p99机器精度=证明LBS实现正确(硬判); max工程阈值=容忍dom_wn≈0.9999边界顶点的次骨残留
    #   (0.16%在3.8mm边上=6微米, 低于float32顶点存储精度, 非bug)
    ok8 = (np.median(r_rel) < 1e-6 and np.percentile(r_rel, 99) < 1e-5
           and r_rel.max() < 0.01 and flipped == 0)
else:
    ok8 = (np.median(r_rel) < 1e-6 and np.percentile(r_rel, 99) < 1e-5 and r_rel.max() < 0.01)

# 混合边涂抹按骨统计(LBS固有, 等价于pose模式摆姿势; retarget动画本来就有同样涂抹)
blend_bone = collections.Counter()
blend_max = collections.defaultdict(float)
for i in np.where(blend)[0]:
    b0 = dom_bone[E[i, 0]]; b1 = dom_bone[E[i, 1]]
    bn = order[b0] if b0 >= 0 else (order[b1] if b1 >= 0 else "?")
    blend_bone[bn] += 1
    blend_max[bn] = max(blend_max[bn], rel[i])
top = sorted(blend_max.items(), key=lambda t: -t[1])[:6]
print(f"    混合边涂抹最重的骨(LBS固有, 非bug): " + ", ".join(f"{n}={v*100:.0f}%" for n, v in top))

# 9.6 左右对称(踝/膝 x 应等距反号)
sym = []
for a, b in [("LeftUpLeg","RightUpLeg"), ("LeftLeg","RightLeg"), ("LeftFoot","RightFoot")]:
    if a in hn2 and b in hn2:
        sym.append((a, hn2[a][0]*1000, hn2[b][0]*1000))
print(f"⑥ 左右对称(关节x):")
ok6 = True
for a, xa, xb in sym:
    dev = abs(abs(xa) - abs(xb))
    if dev > 1.0: ok6 = False
    print(f"    {a:<12} L_x={xa:+8.2f}mm R_x={xb:+8.2f}mm 差={dev:.3f}mm {'✓' if dev<=1.0 else '⚠'}")

# 9.7 腿部关键指标(用户关切: 大腿自然 + 标准)
print(f"⑦ 腿部标准化结果:")
for n in ["LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase"]:
    if n not in Rn2: continue
    zo = ours[n]['R'][:, 1]; zn = Rn2[n][:, 1]
    so = math.degrees(math.atan2(zo[0], -zo[2])); sn = math.degrees(math.atan2(zn[0], -zn[2]))
    print(f"    {n:<14} 外展 {so:+6.2f}° → {sn:+6.2f}°")
ank_l = hn2.get("LeftFoot"); ank_r = hn2.get("RightFoot")
if ank_l is not None and ank_r is not None:
    print(f"    踝离中线: 重摆前 L={abs(ours['LeftFoot']['head'][0])*1000:.1f}mm → 后 L={abs(ank_l[0])*1000:.1f}mm (Mixamo参考≈91mm)")

ALL = ok1 and ok2 and ok3 and ok4 and ok5 and ok6 and ok8
print(f"\n{'='*70}")
print(f"自查判定: ①结构{'✓' if ok1 else '✗'} ②朝向{'✓' if ok2 else '✗'} ③骨长{'✓' if ok3 else '✗'} "
      f"④蒙皮探针{'✓' if ok4 else '✗'} ⑤贴地/身高{'✓' if ok5 else '✗'} ⑥对称{'✓' if ok6 else '✗'} "
      f"⑧边长完整{'✓' if ok8 else '✗'}")
print(f"→ {'ALL PASS' if ALL else 'FAIL'}")
if not ALL:
    print("⚠ 自查未全过, 不保存(避免产出坏文件)")
    print("03B_DONE_FAIL")
    raise SystemExit(1)

# ---------------- 10. 保存 ----------------
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print(f"\n已保存: {OUT}")
print(f"  (输入 {os.path.basename(RIG03)} 未改动)")
print("03B_DONE")
