# 眼窝面朝向修复（v46）— tag层 final flip + mode切换陷阱

## 问题现象
用户反馈眼窝上半部分（z≥中心）有 6.5-7.2% 的面朝向翻转（normal.y > 0.05，朝头内），集中在倒角带到碗外缘区域（z[1.662,1.675]）。下半部分只有 1.1-1.8% 翻转。

## 根因分析

### 1. bmesh.update_edit_mesh + mode 切换导致法线重算
`make_eye_cup` 内部多次 `bmesh.update_edit_mesh(mesh)` + `bpy.ops.object.mode_set(mode='OBJECT')` + `mode_set(mode='EDIT')` 循环。每次 mode 切换 EDIT→OBJECT 时，Blender 重新计算 mesh polygons 的法线方向，可能翻转之前已修好的面。

### 2. v38 几何朝向兜底失效
v38 用 `center.y < fc.y < center.y + 0.02` 判断眼窝区，只翻转 `normal.y > 0` 的面。但这个 y 范围下限 `center.y` 是眼中心深度，而倒角带/碗面靠前部分 y < center.y（更靠前），被下限排除，漏掉了上半部分的翻转面。

### 3. 诊断确认
诊断脚本 `diagnose_orientation.py` 用 3DDFA center_3d 作为中心，按 z 分上下半统计 normal.y：
- 上半（z≥中心）：7.2% 翻转，y[-0.1149,-0.1058] 全部 y ≤ center.y
- 下半（z<中心）：0.5% 翻转

翻转面全部在 y ≤ center.y 区域，正是 v38 y 范围下限漏掉的。

## 修复方案（v46）

### 核心修复：tag层 final flip pass
在 UV 分配后、退出 EDIT 前，加 final flip pass：
```python
# v46: 最终翻转pass - 用tag层(倒角带=1/碗=2/原始皮肤=0)只处理新创建面.
# 根因: y范围判断(center.y<fc.y)漏掉倒角带上半部分靠前的面(y<center.y).
_flip2 = 0
_tag_fl = bm.faces.layers.int.get("v44tag_" + side)
for _f in bm.faces:
    _tg = _f[_tag_fl] if _tag_fl is not None else 0
    if _tg == 0:
        continue   # 原始皮肤面不动
    if _f.normal.y > 0.05:
        bmesh.ops.reverse_faces(bm, faces=[_f])
        _flip2 += 1
if _flip2:
    bm.normal_update()
    bmesh.update_edit_mesh(mesh)
    print(f"  final flip: {_flip2} residual flipped faces")
```

**关键点**：
- 用 tag 层（v44 已有：倒角带=1/碗=2/原始皮肤=0）只处理新创建面，不用 y 范围判断
- 原始皮肤面（tag=0）不动，避免误翻
- 阈值 `normal.y > 0.05`（比 v38 的 >0 更宽松，避免误翻合法面）

### 辅助修复：扩大面朝向检查半径
v38 的面朝向检查半径 0.021mm 在 rim 扩大到 10.9mm 后漏检碗外缘，扩到 0.025mm：
```python
# v45: rim扩大后(avg10.9mm) xz半径需从0.021扩到0.025, 覆盖碗外缘翻转面
if center.y < fc.y < center.y + 0.02 and (fc - center).xz.length < 0.025:
```

## 验证结果
- final flip 抓到 190-206 个残留翻转面并翻转
- 诊断显示翻转率从 7.2% 降到 0.2%（每眼只剩 4-6 个面）
- 剩余 4-6 个面在碗底极点三角扇附近（dxz 0.005-0.013，碗底最深处），normal.y 刚好在 0.05 阈值边缘，属可忽略极点残留

## 血泪教训
1. **mode 切换 EDIT→OBJECT 会重算 mesh normals**，可能翻转已修好的面。必须在 UV 分配后加 final flip pass 兜底。
2. **y 范围判断不可靠**——倒角带/碗面靠前部分 y < center.y，会被下限排除。用 tag 层判断更可靠。
3. **诊断必须用正确中心**——config 的 IRIS_L 是错的（6mm 偏），必须用 3DDFA center_3d（与管线一致）。
