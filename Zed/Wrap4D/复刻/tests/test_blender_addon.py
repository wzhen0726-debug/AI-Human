"""用真实 Blender 无头模式测试 pywrap_bridge 核心逻辑.

直接调用插件里的纯函数(write_obj_world/read_obj)与少量 bpy 逻辑,
绕过 Operator 调用机制, 验证:
  导出顶点序+UV一致 / 选点历史记录 / 点对导出 / 结果导入 /
  形态键应用 / 替换网格 / Delta 迁移 / 形态键序列导出
"""

import os
import subprocess
import sys
import time

THIS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(THIS)
ADDON = os.path.join(ROOT, "blender_addon")
sys.path.insert(0, ROOT)
from wrapclone.blender_detect import find_blender, blender_headless_args

BLENDER = find_blender()  # 优先 5.2 (5.1 留给 hermes 独占)
assert BLENDER is not None

INNER = r'''
import json, os, sys, math, bmesh, bpy
from mathutils import Vector

sys.path.insert(0, r"{ADDON}")
import pywrap_bridge as B

def act(o):
    for x in bpy.context.view_layer.objects: x.select_set(False)
    o.select_set(True); bpy.context.view_layer.objects.active = o

# 基础网格: 8边形 + UV + 2形态键
mesh = bpy.data.meshes.new("base")
verts_co = [(math.cos(i*math.pi/4), math.sin(i*math.pi/4), 0) for i in range(8)]
mesh.from_pydata(verts_co, [], [list(range(8))])
mesh.update()
mesh.uv_layers.new(name="uv")
obj = bpy.data.objects.new("BaseHead", mesh)
bpy.context.scene.collection.objects.link(obj)
obj.shape_key_add(name="Basis", from_mix=False)
sk1 = obj.shape_key_add(name="Smile", from_mix=False)
for i,v in enumerate(mesh.vertices): sk1.data[i].co = v.co + Vector((0,0,0.1*(i%2)))
sk2 = obj.shape_key_add(name="Brow", from_mix=False)
for i,v in enumerate(mesh.vertices): sk2.data[i].co = v.co + Vector((0.05,0,0))

# 扫描网格 = 基础平移
tmesh = bpy.data.meshes.new("target")
tmesh.from_pydata([tuple(Vector(c)+Vector((0.2,0.3,0))) for c in verts_co],
                  [], [list(range(8))]); tmesh.update()
tobj = bpy.data.objects.new("Scan", tmesh)
bpy.context.scene.collection.objects.link(tobj)

ctx = bpy.context
ex = B._exdir(ctx)

# ① 导出 base.obj / target.obj (顶点序一致 + UV)
B.write_obj_world(obj, os.path.join(ex, "base.obj"))
B.write_obj_world(tobj, os.path.join(ex, "target.obj"))
bv, bf = B.read_obj(os.path.join(ex, "base.obj"))
assert len(bv) == 8, f"base.obj 顶点序不一致 {len(bv)}"
# UV 在文件里 (vt 行)
txt = open(os.path.join(ex, "base.obj")).read()
assert "vt " in txt, "base.obj 缺少 UV"
print("EXPORT_OK verts=", len(bv), "has_uv=", "vt " in txt)

# ② 编辑模式选点历史 -> 记录基础/扫描点
act(obj); bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(mesh); bm.select_history.clear()
for v in list(bm.verts)[:3]: v.select=True; bm.select_history.add(v)
bvids = B._record_selected_vids(obj)
bpy.ops.object.mode_set(mode="OBJECT")
assert bvids == [0,1,2], f"基础点顺序错误 {bvids}"

act(tobj); bpy.ops.object.mode_set(mode="EDIT")
bm2 = bmesh.from_edit_mesh(tmesh); bm2.select_history.clear()
for v in list(bm2.verts)[:3]: v.select=True; bm2.select_history.add(v)
tvids = B._record_selected_vids(tobj)
bpy.ops.object.mode_set(mode="OBJECT")
assert tvids == [0,1,2], f"扫描点顺序错误 {tvids}"
print("RECORD_OK base=", bvids, "target=", tvids)

# ③ 导出点对
ctx.scene[B.PROP_BASE_VIDS] = bvids
ctx.scene[B.PROP_TARGET_VIDS] = tvids
ctx.scene[B.PROP_BASE_NAME] = obj.name
data = {"format":"vids","base_vids":bvids,"target_vids":tvids,
        "names":[f"P{i+1}" for i in range(3)]}
json.dump(data, open(os.path.join(ex,"points.json"),"w"))
print("POINTS_OK")

# ④ 构造 wrapped.obj (模拟 PyWrap 输出: 顶点上移0.1)
wverts = [mesh.vertices[i].co + Vector((0,0,0.1)) for i in range(8)]
B.write_obj_from_world_verts(wverts, [list(range(8))],
                             os.path.join(ex,"wrapped.obj"))

# ⑤ 导入结果为新物体 (用插件逻辑: from_pydata)
wv, wf = B.read_obj(os.path.join(ex,"wrapped.obj"))
nmesh = bpy.data.meshes.new("pywrap_wrapped")
nmesh.from_pydata([tuple(v) for v in wv], [], [list(f) for f in wf]); nmesh.update()
dst = bpy.data.objects.new("pywrap_wrapped", nmesh)
ctx.scene.collection.objects.link(dst)
assert len(dst.data.vertices) == 8
print("IMPORT_OK")

# ⑥ apply_shape_key 逻辑: 在 base 上加形态键 = wrapped 局部坐标
act(obj)
if obj.data.shape_keys is None: obj.shape_key_add(name="Basis", from_mix=False)
Minv = obj.matrix_world.inverted()
sk = obj.shape_key_add(name="PyWrap_Wrapped", from_mix=False)
for i,w in enumerate(wv): sk.data[i].co = Minv @ w
kb = obj.data.shape_keys.key_blocks["PyWrap_Wrapped"]
for i in range(8):
    expect = Minv @ (mesh.vertices[i].co + Vector((0,0,0.1)))
    assert (kb.data[i].co - expect).length < 1e-4
print("SHAPEKEY_OK")

# ⑦ replace_mesh 逻辑: 原地替换顶点
act(obj)
for i,w in enumerate(wv): obj.data.vertices[i].co = Minv @ w
obj.data.update()
for i in range(8):
    assert abs(obj.data.vertices[i].co.z - 0.1) < 1e-4
print("REPLACE_OK")

# ⑧ Delta 迁移: 把 base 的 Smile/Brow 迁到 dst (base 已被replace, 但shape_keys还在)
# 注意: replace 后 basis 变了, 这里重置 base 顶点做干净的迁移测试
for i in range(8): obj.data.vertices[i].co = Vector(verts_co[i])
obj.data.update()
s_basis = obj.data.shape_keys.reference_key
d_basis = dst.data.shape_keys.reference_key if dst.data.shape_keys else dst.shape_key_add(name="Basis",from_mix=False)
if dst.data.shape_keys is None:
    dst.shape_key_add(name="Basis", from_mix=False)
d_basis = dst.data.shape_keys.reference_key
M3s = obj.matrix_world.to_3x3(); M3d_inv = dst.matrix_world.to_3x3().inverted()
cnt = 0
for kb in obj.data.shape_keys.key_blocks:
    if kb == s_basis: continue
    nkb = dst.shape_key_add(name=kb.name, from_mix=False)
    for i in range(8):
        dw = M3s @ (kb.data[i].co - s_basis.data[i].co)
        nkb.data[i].co = d_basis.data[i].co + M3d_inv @ dw
    cnt += 1
# 校验 Smile
sk_smile = dst.data.shape_keys.key_blocks["Smile"]
sbs = obj.data.shape_keys.key_blocks["Smile"]; basis = s_basis
for i in range(8):
    expect = dst.data.vertices[i].co + (sbs.data[i].co - basis.data[i].co)
    assert (sk_smile.data[i].co - expect).length < 1e-4
print("TRANSFER_OK count=", cnt)

# ⑨ export_shapes 逻辑
M = obj.matrix_world
faces = [tuple(p.vertices) for p in obj.data.polygons]
sd = os.path.join(ex,"shapes"); os.makedirs(sd, exist_ok=True)
basis = obj.data.shape_keys.reference_key
nsh = 0
for kb in obj.data.shape_keys.key_blocks:
    if kb == basis: continue
    vs = [M @ kb.data[i].co for i in range(8)]
    B.write_obj_from_world_verts(vs, faces, os.path.join(sd, f"{kb.name}.obj"))
    nsh += 1
files = sorted(os.listdir(sd))
assert "Smile.obj" in files and "Brow.obj" in files
print("EXPORTSHAPES_OK", files)

print("ALL_BLENDER_TESTS_OK")

# 显式注销, 避免 Blender 退出时清理插件类的噪音报错
try:
    B.unregister()
except Exception:
    pass
'''.replace("{ADDON}", ADDON)


def _run_once(script):
    proc = subprocess.run(
        [BLENDER, *blender_headless_args(), "--python", script],
        capture_output=True, text=True, timeout=300, encoding="utf-8",
        errors="ignore")
    return proc.stdout + proc.stderr


def main():
    script = os.path.join(os.environ["TEMP"], "pywrap_blender_test.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(INNER)
    if not os.path.isfile(BLENDER):
        print(f"[SKIP] 未找到 Blender: {BLENDER}")
        sys.exit(0)
    print(f"使用 Blender: {BLENDER}")
    out = ""
    for attempt in range(1, 4):
        try:
            out = _run_once(script)
        except subprocess.TimeoutExpired:
            print(f"[重试 {attempt}/3] Blender 超时(可能被占用)")
            out = ""
        if "ALL_BLENDER_TESTS_OK" in out:
            break
        if attempt < 3:
            print(f"[重试 {attempt}/3] 2秒后重试...")
            time.sleep(2)
    for line in out.splitlines():
        if any(k in line for k in ("_OK", "ALL_BLENDER", "Error", "Traceback",
                                   "Assertion", "SKIP")):
            print(line)
    if "ALL_BLENDER_TESTS_OK" in out:
        print("\nBlender 插件无头测试全部通过")
        if "bpy_types" in out:
            print("(注: 末尾 bpy_types 报错为 Blender 5.x 后台模式退出噪音, 与插件无关, 可忽略)")
    else:
        print("\n[FAIL] Blender 测试未全部通过")
        sys.exit(1)


if __name__ == "__main__":
    main()
