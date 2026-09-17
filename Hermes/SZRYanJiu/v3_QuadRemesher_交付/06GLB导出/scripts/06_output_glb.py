"""06 GLB导出 — 从 05 的 04_动作测试.blend 导出 GLB(含 走/跑/跳 三个动画)。

输入: 05骨骼绑定/ARP新版测试_20260831/04_动作测试.blend
输出: 06GLB导出/输出/06_角色_走跑跳.glb

自查(全部通过才打印 06_DONE):
  ① 源文件: fps=30 / 三动作(名称+帧范围) / 骨架scale=1 / 模型高度合理
  ② GLB头部(纯Python解析glTF JSON): 3个动画(名称/时长秒) + 网格/皮肤/图像数
  ③ 重新导入: 静止高度 vs 源(比例) / 55骨 / 3产品网格 / 4K贴图在场
  ④ 动画正确性: 源与重导入的"逐帧变形包围盒签名"对比(容差内)
  ⑤ 文件大小合理性

注: 只统计"场景内且带ARMATURE修改器"的产品网格 —— glTF导入器会给骨骼
    造显示形状(如Icosphere, 非资产内容), 不可计入包围盒。
"""
import bpy, os, sys, json, struct, time
import numpy as np

t0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))      # 06GLB导出/scripts
STAGE = os.path.dirname(HERE)                          # 06GLB导出
BASE = os.path.dirname(STAGE)                          # 演示版_终端控制端
OUTDIR = os.path.join(STAGE, "输出")
B05 = os.path.join(BASE, "05骨骼绑定", "ARP新版测试_20260831")
SRC = os.path.join(B05, "04_动作测试.blend")
GLB = os.path.join(OUTDIR, "06_角色_走跑跳.glb")
EXPECT = [("Standard Walk", 36), ("Running", 20), ("Jump", 31)]
FPS = 30
SIG_KEYS = [("Standard Walk", (1, 18, 36)), ("Running", (1, 20)), ("Jump", (1, 16))]
ok_all = True

def P(*a):
    print(*a, flush=True)

def bad(msg):
    global ok_all
    ok_all = False
    P(f"   ✗ {msg}")

def good(msg):
    P(f"   ✓ {msg}")

# ---------- 工具 ----------
def product_meshes():
    """场景内的产品网格 = 蒙皮网格(带ARMATURE修改器); 排除导入器/插件附带的显示形状"""
    out = [o for o in bpy.context.scene.objects
           if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
    if not out:
        out = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    return out

def sig_of(meshes):
    dg = bpy.context.evaluated_depsgraph_get()
    mins = np.array([1e18] * 3); maxs = np.array([-1e18] * 3)
    for ob in meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        V = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)
        MW = np.array(ev.matrix_world)
        W = V @ MW[:3, :3].T + MW[:3, 3]
        mins = np.minimum(mins, W.min(axis=0)); maxs = np.maximum(maxs, W.max(axis=0))
        ev.to_mesh_clear()
    return np.concatenate([mins, maxs])

def assign_action(arm, act):
    if not arm.animation_data:
        arm.animation_data_create()
    arm.animation_data.action = act
    for s in getattr(act, "slots", []):
        try:
            arm.animation_data.action_slot = s
            return True
        except Exception:
            continue
    return True

def rest_height(arm, meshes):
    old = arm.data.pose_position
    arm.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    s = sig_of(meshes)
    arm.data.pose_position = old
    bpy.context.view_layer.update()
    return s, (s[5] - s[2])

def capture_sigs(arm, meshes):
    out = {}
    for name, frames in SIG_KEYS:
        act = bpy.data.actions.get(name)
        if act is None:
            continue
        assign_action(arm, act)
        for f in frames:
            bpy.context.scene.frame_set(f)
            out[f"{name}@{f}"] = sig_of(meshes)
    return out

# ---------- 1. 打开源 + 源自查 ----------
P(f"打开源: {os.path.relpath(SRC, BASE)}")
bpy.ops.wm.open_mainfile(filepath=SRC)
scn = bpy.context.scene
P(f"① 源自查: fps={scn.render.fps}")
if scn.render.fps != FPS:
    bad(f"fps={scn.render.fps} ≠ {FPS}(Mixamo参考帧率), 动画时长会错")
else:
    good(f"fps={FPS} 与 Mixamo 参考一致")
acts = {a.name: a for a in bpy.data.actions}
for name, nf in EXPECT:
    a = acts.get(name)
    if a is None:
        bad(f"缺动作 {name!r} (现值: {list(acts)})")
    else:
        fr = a.frame_range
        if abs(fr[0] - 1) > 0.5 or abs(fr[1] - nf) > 0.5:
            bad(f"动作 {name!r} 帧范围 {fr[0]:.0f}-{fr[1]:.0f} ≠ 1-{nf}")
        else:
            good(f"动作 {name!r}: 帧 1-{nf} (={nf/FPS:.3f}s)")
arm_src = next((o for o in bpy.context.scene.objects if o.type == 'ARMATURE'), None)
meshes_src = product_meshes()
if arm_src is None:
    bad("无骨架对象")
    P("06_FAIL"); sys.exit(1)
sig0, h_rest_src = rest_height(arm_src, meshes_src)
x_rest_src = sig0[3] - sig0[0]
P(f"   源模型(静止): 高={h_rest_src*1000:.1f}mm 宽(x)={x_rest_src*1000:.1f}mm 产品网格={len(meshes_src)}个 骨={len(arm_src.data.bones)}")
if not (1.4 < h_rest_src < 2.2):
    bad(f"源模型高度 {h_rest_src*1000:.0f}mm 不在人体合理范围(比例错误?)")
if abs(arm_src.scale[0] - 1) > 1e-6 or abs(arm_src.scale[1] - 1) > 1e-6:
    bad(f"骨架 scale={tuple(arm_src.scale)} ≠ 1")
if ok_all:
    good("源骨架 scale=1, 高度比例正确")

# ---------- 2. 采集源动画签名 ----------
P("② 采集源动画签名(变形包围盒)…")
sigs_src = capture_sigs(arm_src, meshes_src)
good(f"源签名 {len(sigs_src)} 帧")

# ---------- 3. 选择并导出 ----------
for o in bpy.data.objects:
    o.select_set(False)
export_objs = [arm_src] + meshes_src
for o in export_objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = arm_src
w = bpy.data.actions.get("Standard Walk")
if w:
    assign_action(arm_src, w)
scn.frame_set(1)

os.makedirs(OUTDIR, exist_ok=True)
if os.path.exists(GLB):
    os.remove(GLB)
props = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}
want = dict(
    filepath=GLB, export_format='GLB', use_selection=True,
    export_yup=True, export_apply=False,
    export_materials='EXPORT', export_image_format='AUTO',
    export_texcoords=True, export_normals=True, export_skins=True,
    export_animations=True, export_animation_mode='ACTIONS',
    export_frame_range=False, export_force_sampling=True,
    export_anim_single_armature=True, export_rest_position_armature=True,
    export_def_bones=False, export_optimize_animation_size=True,
    export_current_frame=False, export_extras=False, export_cameras=False,
    export_lights=False,
)
kw = {k: v for k, v in want.items() if k in props}
P(f"③ 导出 GLB(选择对象{len(export_objs)}个: 骨架+{len(meshes_src)}产品网格)…  (不存在的参数: {sorted(set(want)-set(kw))})")
bpy.ops.export_scene.gltf(**kw)
if not os.path.exists(GLB):
    bad("导出后文件不存在")
    P("06_FAIL"); sys.exit(1)
sz_mb = os.path.getsize(GLB) / 1024 / 1024
good(f"已导出 {os.path.relpath(GLB, BASE)}  {sz_mb:.1f}MB")

# ---------- 4. GLB 头部解析(不经Blender) ----------
P("④ GLB 头部解析(glTF JSON)…")
with open(GLB, 'rb') as fh:
    data = fh.read()
magic, ver, glen = struct.unpack_from('<4sII', data, 0)
if magic != b'glTF' or ver != 2:
    bad(f"GLB头异常 magic={magic} ver={ver}")
else:
    good(f"GLB头正确: glTF v{ver}, {glen/1024/1024:.1f}MB")
js = None
off = 12
while off < glen:
    clen, ctype = struct.unpack_from('<I4s', data, off); off += 8
    if ctype == b'JSON':
        js = json.loads(data[off:off + clen].decode('utf-8'))
    off += clen
if js is None:
    bad("GLB无JSON块")
anim_names = []
for a in js.get('animations', []):
    dur = 0.0
    for smp in a.get('samplers', []):
        acc = js['accessors'][smp['input']]
        if acc.get('max'):
            dur = max(dur, float(acc['max'][0]))
    anim_names.append((a.get('name', '?'), dur))
nmesh = len(js.get('meshes', [])); nskin = len(js.get('skins', []))
nimg = len(js.get('images', [])); njoint = len(js['skins'][0]['joints']) if nskin else 0
P(f"   glTF: 动画={len(anim_names)} 网格={nmesh} 皮肤={nskin} 关节={njoint} 节点={len(js.get('nodes', []))} 图像={nimg}")
for n, d in anim_names:
    P(f"     · {n}: 时长={d:.3f}s")
glb_names = {n for n, _ in anim_names}
for name, nf in EXPECT:
    if name not in glb_names:
        bad(f"GLB 缺动画 {name!r}")
    else:
        exp_dur = (nf - 1) / FPS
        d = dict(anim_names)[name]
        if abs(d - exp_dur) > 0.15 and abs(d - nf / FPS) > 0.15:
            bad(f"GLB 动画 {name!r} 时长 {d:.3f}s 偏离预期 ~{exp_dur:.3f}s")
        else:
            good(f"GLB 动画 {name!r} 时长 {d:.3f}s ✓")
if nskin != 1 or njoint != 55:
    bad(f"GLB 皮肤/关节异常: skin={nskin} joints={njoint} (应=1/55)")
else:
    good(f"GLB 蒙皮完整: 1皮肤/55关节 ✓")
if nmesh != 3:
    bad(f"GLB 网格数 {nmesh} ≠ 3")
if nimg < 3:
    bad(f"GLB 图像仅 {nimg} 个(贴图可能没带上)")

# ---------- 5. 重新导入验证 ----------
P("⑤ 重新导入验证…")
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps = FPS
bpy.ops.import_scene.gltf(filepath=GLB)
arm2 = next((o for o in bpy.context.scene.objects if o.type == 'ARMATURE'), None)
meshes2 = product_meshes()
strays = [o.name for o in bpy.context.scene.objects if o.type == 'MESH' and o not in meshes2]
if strays:
    P(f"   (忽略非蒙皮附带对象: {strays} — glTF导入器的骨骼显示形状, 非资产内容)")
if arm2 is None:
    bad("重导入无骨架")
else:
    good(f"重导入: 骨架 {arm2.name!r} 骨数={len(arm2.data.bones)}")
    if len(arm2.data.bones) != 55:
        bad(f"骨数 {len(arm2.data.bones)} ≠ 55")
if len(meshes2) != 3:
    bad(f"重导入产品网格数 {len(meshes2)} ≠ 3")
sig2r, h_rest2 = rest_height(arm2, meshes2) if arm2 else (np.zeros(6), 0)
x_rest2 = sig2r[3] - sig2r[0]
P(f"   重导入(静止): 高={h_rest2*1000:.1f}mm 宽(x)={x_rest2*1000:.1f}mm")
dh = abs(h_rest2 - h_rest_src) * 1000
dx = abs(x_rest2 - x_rest_src) * 1000
if dh > 5 or dx > 5:
    bad(f"比例不符: 高差 {dh:.1f}mm / 宽差 {dx:.1f}mm (源 {h_rest_src*1000:.1f}/{x_rest_src*1000:.1f} vs 导入 {h_rest2*1000:.1f}/{x_rest2*1000:.1f})")
else:
    good(f"比例正确: 静止高差 {dh:.2f}mm / 宽差 {dx:.2f}mm (1个单位=1米)")
imgs = [im for im in bpy.data.images if im.size[0] > 0]
big = [im for im in imgs if im.size[0] >= 4096]
if not big:
    bad(f"重导入无 4K 贴图 (图像: {[(i.name, tuple(i.size)) for i in imgs]})")
else:
    good(f"4K 贴图在场: {big[0].name} {big[0].size[0]}x{big[0].size[1]}; 图像共{len(imgs)}张")

acts2 = {a.name: a for a in bpy.data.actions}
for name, nf in EXPECT:
    a2 = acts2.get(name)
    if a2 is None:
        cand = [k for k in acts2 if k.startswith(name)]
        a2 = acts2[cand[0]] if cand else None
    if a2 is None:
        bad(f"重导入缺动作 {name!r} (现值: {list(acts2)})")
    else:
        fr = a2.frame_range
        if abs(fr[0] - 1) > 2.5 or abs(fr[1] - nf) > 2.5:
            bad(f"重导入动作 {name!r} 帧范围 {fr[0]:.0f}-{fr[1]:.0f} ≠ 1-{nf}")
        else:
            good(f"重导入动作 {name!r} 帧 1-{nf} ✓")

# ---------- 6. 动画签名对比(源 vs 重导入) ----------
P("⑥ 动画正确性对比(逐帧变形包围盒签名, 阈值5mm)…")
sigs2 = capture_sigs(arm2, meshes2) if arm2 else {}
worst = 0.0; worst_k = ""
for k, v0 in sigs_src.items():
    v2 = sigs2.get(k)
    if v2 is None:
        bad(f"重导入缺签名 {k}")
        continue
    d = float(np.abs(v0 - v2).max()) * 1000
    if d > worst:
        worst, worst_k = d, k
    P(f"     {k}: 最大差 {d:.2f}mm {'✓' if d <= 5 else '✗'}")
if worst <= 5:
    good(f"动画正确: 全部签名最大差 {worst:.2f}mm (最差 {worst_k})")
else:
    bad(f"动画偏差过大: {worst:.2f}mm @ {worst_k}")

# ---------- 7. 汇总 ----------
P(f"\n文件: {os.path.relpath(GLB, BASE)}  {sz_mb:.1f}MB")
P(f"动画: " + ", ".join(f"{n}({d:.3f}s)" for n, d in anim_names))
P(f"比例: 静止高 {h_rest2*1000:.1f}mm (源 {h_rest_src*1000:.1f}mm)  骨 {len(arm2.data.bones) if arm2 else '?'}  网格 {len(meshes2)}  用时 {time.time()-t0:.0f}s")
if ok_all:
    P("========== 06_DONE ==========")
else:
    P("06_FAIL")
    sys.exit(1)
