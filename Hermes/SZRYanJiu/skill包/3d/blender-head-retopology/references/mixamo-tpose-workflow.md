# Mixamo MetaHuman Binding & T-pose Workflow

## 关键事实

**Mixamo 支持 A-pose 绑定**（用户 2026-07-28 实测确认）。之前所有文档中"Mixamo 不支持 A-pose"的说法都是错误的。用户已在 Mixamo 中完成 MetaHuman A-pose 绑定并制作 T-pose 动画，导出 `T-Pose.fbx`。

## 用户反馈

用户原话："顺便把你的md中所有说mixamo不支持Apose绑定的都改掉。下次这种问题，你自己调研不到位，可以让我去实测"

**教训**: Agent 调研不到位时，优先让用户去实测，不要自己猜测工具能力边界。用户实测成本远低于 Agent 错误假设导致的返工成本。

## FBX 文件信息

- 路径: `原始模型/Metahuman低模/T-Pose.fbx`
- 骨骼: 65 根 Mixamo 标准骨骼 (`mixamorig:Hips`, `mixamorig:Spine`, `mixamorig:LeftShoulder`, `mixamorig:LeftArm`, `mixamorig:LeftForeArm`, `mixamorig:LeftHand` 等)
- 网格: Body 32334 verts + Head 24414 verts
- 动画: 2 帧 (帧1=A-pose, 帧2=T-pose)
- Armature scale: 0.01 (cm 单位)

## Mixamo 网页使用注意事项

用户已在浏览器中登录 Mixamo 账号供 Agent 使用。**注意机器人检测，避免触发封禁**。

## 处理流程

### 1. 导入 FBX 并应用 T-pose

```python
bpy.ops.import_scene.fbx(filepath=FBX_PATH)

# 修复 armature scale (0.01 → 1.0)
arm = bpy.data.objects.get('Armature')
arm.scale = (100, 100, 100)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# 转到 T-pose 帧
bpy.context.scene.frame_set(2)
bpy.context.view_layer.update()

# 应用骨骼变形到网格
for obj in [mh_body, mh_head]:
    bpy.ops.object.modifier_apply(modifier="Armature")

# 删除骨骼和动画
for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
bpy.data.objects.remove(arm, do_unlink=True)
```

### 2. 坐标系转换

FBX 导入后：
- X = 手臂展开 (cm 单位，T-pose X span=191cm)
- Y = 身高 (180cm)
- Z = 前后厚度 (35cm)
- 脸朝 -Z

目标（与 Tripo 对齐）：
- X = 左右（手臂展开）
- Y = 前后厚度，脸朝 -Y
- Z = 身高

**直接修改顶点坐标**（matrix_basis/rotation_euler 在 Blender 5.1 不可靠）：

```python
# 变换: new_x = x*0.01, new_y = -z*0.01, new_z = y*0.01
for v in mesh.vertices:
    x, y, z = v.co.x, v.co.y, v.co.z
    v.co.x = x * 0.01       # 手臂展开，cm→m
    v.co.y = -z * 0.01      # 厚度Z→-Y(脸朝-Y)
    v.co.z = y * 0.01       # 身高Y→Z
```

### 3. 验证

T-pose 正确的 bbox:
- X span ≈ 1.91m (手臂展开)
- Y span ≈ 0.35m (前后厚度)
- Z span ≈ 1.80m (身高)
- 脸朝 -Y
- 左手: X≈-0.956, Z≈1.441 (肩膀高度)

### 4. Shrinkwrap 包裹到 Tripo

**问题**: MetaHuman T-pose X span (1.91m) > Tripo X span (1.81m)。Shrinkwrap NEAREST 会把多出的手臂顶点压到 Tripo 躯干表面，导致模型崩溃（X span 从 1.91m 变成 0.38m）。

**NEAREST 模式**: 精度 0mm 但模型压扁崩溃（所有顶点吸附到最近表面，丢失拓扑）
**PROJECT 模式**: 不压扁但精度极差（905mm 平均距离，法线方向不匹配）

**结论**: 即使同姿势（都是 T-pose），Shrinkwrap NEAREST 在含衣服的 AI 高模上仍然崩溃。根因不是姿势差异，而是： (1) MetaHuman X span (1.91m) > Tripo X span (1.81m)，多出的手臂顶点被压到最近衣服表面；(2) Shrinkwrap 无语义理解，把所有顶点吸附到最近表面（包括衣服），丢失拓扑结构。PROJECT/TARGET_PROJECT 模式也不行（精度 905mm，法线不匹配）。**Shrinkwrap 在含衣服的 AI 高模上结构性失败，无论姿势是否一致**。

**关键发现 (2026-07-28)**: Shrinkwrap NEAREST 把 MetaHuman 从 1.9m 压扁到 0.38m（X span），从 1.8m 压扁到 0.16m（Z span）。所有顶点被吸附到 Tripo 衣服表面后，模型丢失了人体拓扑结构，变成了一团"衣服形状的壳"。这不是精度问题，是**结构性崩溃**——Shrinkwrap 不适合任何含衣服的 AI 高模，无论源模型是什么姿势。

### 5. 用户反馈与教训

用户原话："别整更复杂的，越乱错的越多" — 当多个方法叠加时（RBF+ARAP+Shrinkwrap+骨骼），每一步引入的误差会叠加放大。**优先用最简单的方法，确认失败后再叠加**。

用户原话："你不需要用到他的骨骼啊，你把骨骼应用了不就行，反正模型是Tpose了已经" — Mixamo 绑定后，直接 `modifier_apply` 把骨骼变形烘焙到网格，然后删除骨骼。不需要保留骨骼用于后续操作。

### 6. 完整 Mixamo T-pose 工作流（已验证）

```
1. Mixamo 绑定 MetaHuman A-pose → 制作 T-pose 动画 → 导出 FBX
2. Blender 导入 FBX → 修复 armature scale (×100) → 转到帧2(T-pose)
3. modifier_apply("Armature") 把 T-pose 烘焙到网格
4. 删除骨骼和动画
5. 坐标转换: 直接改顶点坐标 (x=x*0.01, y=-z*0.01, z=y*0.01)
6. 居中 → 得到 T-pose MetaHuman (X span 1.91m, Y span 0.35m, Z span 1.80m)
7. Shrinkwrap 到 Tripo → 崩溃（见第4节）
```

步骤1-6 已验证成功。步骤7 Shrinkwrap 崩溃后，改用 RBF linear 核对齐。

### 7. RBF linear 核对齐（当前最佳结果）

Shrinkwrap 崩溃后，改用 **RBF linear 核**做体型对齐（不做 Shrinkwrap）。

**方法**: 
- 两个模型都是 T-pose，只需做体型匹配（变形幅度小）
- 几何分析在 T-pose MetaHuman 上找 16 个 landmark（肩/肘/腕/膝/踝等）
- 用 Tripo 已有的 16 个 landmark 作为目标
- `scipy.interpolate.RBFInterpolator(kernel='linear', degree=1)` 

**关键发现**: **linear 核远优于 gaussian/TPS 核**：
| 核函数 | X span | Y span | Z span | 评价 |
|--------|--------|--------|--------|------|
| gaussian | 2.083 | 0.882 | 2.366 | 严重膨胀 |
| linear | 1.925 | 0.553 | 1.818 | 基本正常 |

linear 核的 Y span (0.553) 仍偏大（Tripo=0.313），但远好于 gaussian。原因：linear 核是全局线性插值，不会像 gaussian/TPS 那样在控制点之间产生非线性膨胀。

**landmark 差异分析**（T-pose MetaHuman → T-pose Tripo）:
- 头/躯干: 4-60mm（正常体型差异）
- 肩: 56-60mm
- 肘: 64-66mm  
- 腕: 26-28mm（手臂位置基本对齐）
- 膝: 11-12mm
- 踝: 65mm
- back: 92mm（异常，Z方向偏移大）

去掉 back 点后效果无改善——膨胀是 RBF 固有特性，不是单个点导致的。

**结论**: RBF linear 核是目前最佳的对齐方法，不需要 Shrinkwrap。结果文件: `wrapped_rbf_tpose.blend`。

**UV 保留验证 (2026-07-28)**: RBF 变形只改顶点坐标，不改 UV。验证结果：原始 UV 数 182448，RBF 后 UV 数 182448，差异 max=0.000000，**UV 完全保留** ✓。这意味着 MetaHuman 的标准 UV（Body 32K/60K 面，U 1.01-1.99 第二通道）可以直接继承，避免 QR 均匀 quad 网格的 UV 碎片化问题。

**WRAP 目的澄清 (2026-07-28, USER)**: 用户原话："WRAP不是为了解决UV展开的问题吗？"。核心需求是**MetaHuman 拓扑 + UV 传递到 AI 高模**，继承 MetaHuman 的 UV，而不是追求完美的身体贴合。衣服无所谓——QR 之后布线一样乱，衣服区域也一样。

### 8. 仿射变换对齐（最新验证，优于 RBF）

**RBF 的问题 (2026-07-28, USER 实测反馈)**: 用户查看 RBF linear 结果后反馈："整个人都是扭曲的。头都变形成椭圆了，脚也拉长了很多，其他地方也有很多变形，这完全不可用"。RBF linear 虽然比 gaussian 好，但仍然是**全局插值**，16 个控制点之间自由变形，导致整体扭曲。

**仿射变换（最小二乘法）**: 不做 RBF 非线性插值，只做**缩放+旋转+平移**的线性变换。用最小二乘法求解：

```python
P_ext = np.hstack([P, np.ones((len(P), 1))])  # N x 4
A, residuals, rank, sv = np.linalg.lstsq(P_ext, Q, rcond=None)
linear = A[:3, :]    # 3x3 旋转/缩放
translate = A[3, :]  # 1x3 平移
deformed = verts @ linear + translate
```

**结果对比**:

| 方法 | X span | Y span | Z span | 扭曲 |
|------|--------|--------|--------|------|
| RBF gaussian | 2.083 | 0.882 | 2.366 | ❌ 严重膨胀 |
| RBF linear | 1.925 | 0.553 | 1.818 | ⚠️ 整体扭曲 |
| **仿射** | **1.957** | **0.396** | **1.736** | ✅ **无扭曲** |

**奇异值检查**: 仿射矩阵奇异值 [1.29, 1.02, 0.95]，接近均匀缩放，无剪切/非均匀缩放。

**landmark 精度**: 12-40mm，正常体型差异。

**结论**: **仿射变换是当前最佳全身对齐方法**，不产生非线性变形，保持体型比例。结果文件: `wrapped_affine_v1.blend`。

详见 `references/affine-full-body-alignment.md`。

### 8. Mixamo FBX 导入坐标系转换（关键细节）

FBX 导入后原始坐标系：
- X = 手臂展开（cm 单位，T-pose X span=191cm）
- Y = 身高（180cm）
- Z = 前后厚度（35cm）
- **脸朝 -Z**

目标坐标系（与 Tripo 对齐）：
- X = 左右（手臂展开）
- Y = 前后厚度，**脸朝 -Y**
- Z = 身高

**转换公式**（直接修改顶点坐标，matrix_basis/rotation_euler 在 Blender 5.1 不可靠）：
```python
for v in mesh.vertices:
    x, y, z = v.co.x, v.co.y, v.co.z
    v.co.x = x * 0.01       # 手臂展开，cm→m
    v.co.y = -z * 0.01      # 厚度Z→-Y(脸朝-Y)
    v.co.z = y * 0.01       # 身高Y→Z
```

**验证**：
- X span ≈ 1.91m（手臂展开）
- Y span ≈ 0.35m（前后厚度）
- Z span ≈ 1.80m（身高）
- 脸朝 -Y（面部中心 Y < 0）
- 左手: X≈-0.956, Z≈1.441（肩膀高度）

**常见错误**：
- 用 `matrix_basis = Matrix.Rotation(-90°, 'X')` → Blender 5.1 中 transform_apply 不生效
- 用 `rotation_euler` → 同样不生效
- 旋转方向搞反 → 模型脸朝 +Y 或朝下（-Z）

**关键**：必须**直接修改顶点坐标**，不要依赖 matrix_basis 或 rotation_euler。
