# -*- coding: utf-8 -*-
"""迁移手调定位点到重建后的文件(上游修复后重建管线入口文件时用; 防止重建吞掉用户手调数据)。

用法:
  blender -b --factory-startup --python migrate_hand_markers.py -- <src.blend> <dst.blend> [_loc] [0.5]

原理: 只迁【主定位点】(名字以 suffix 结尾、且不以 suffix+"_sym" 结尾)的局部 location;
      镜像/对称点一般由 COPY_LOCATION 之类约束驱动, 迁完主点后自动重算, 不要手工迁。
校验: 迁移后逐点比对【约束求值后】的世界坐标(= matrix_world.translation, 需先 view_layer.update()),
      偏差 > tol_mm 直接断言失败 —— 超差说明 dst 里父级/约束尚未建好, 失败好过静默错位。
只写 dst; 本脚本不做备份, 运行前先按约定给 dst 留 _备份/ 快照。
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if len(argv) < 2:
    raise SystemExit("用法: ... -- <src.blend> <dst.blend> [_loc] [tol_mm]")
src, dst = argv[0], argv[1]
sfx = argv[2] if len(argv) > 2 else "_loc"
tol = float(argv[3]) if len(argv) > 3 else 0.5

bpy.ops.wm.open_mainfile(filepath=src)
mains = {}
for o in bpy.data.objects:
    if o.name.endswith(sfx) and not o.name.endswith(sfx + "_sym"):
        mains[o.name] = (tuple(float(v) for v in o.location),
                         tuple(float(v) for v in o.matrix_world.translation))
print(f"源: {src} | 主定位点 {len(mains)} 个: {sorted(mains.keys())}", flush=True)
assert mains, "源文件里没有任何主定位点, 检查后缀参数"

bpy.ops.wm.open_mainfile(filepath=dst)
n = 0
for o in bpy.data.objects:
    if o.name in mains:
        o.location = mains[o.name][0]
        n += 1
bpy.context.view_layer.update()
bad = []
for o in bpy.data.objects:
    if o.name in mains:
        w = tuple(float(v) for v in o.matrix_world.translation)
        d = (sum((w[i] - mains[o.name][1][i]) ** 2 for i in range(3)) ** 0.5) * 1000
        if d > tol:
            bad.append((o.name, round(d, 2)))
print(f"写入 {n} 点; 世界偏差 > {tol}mm 的: {bad if bad else '无'}", flush=True)
assert not bad, "迁移后世界位置不匹配 —— dst 里父级/约束没建好"
bpy.ops.wm.save_mainfile()
print("MIGRATE_DONE", flush=True)
