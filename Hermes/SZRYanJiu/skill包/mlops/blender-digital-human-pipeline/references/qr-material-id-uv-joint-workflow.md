# QR + UV Joint Workflow — Material ID Guided Retopology & Auto-Seam

> 核心思路：在 QuadRemesher 阶段预埋语义边界（Material ID），让 QR 的 edge flow 沿材质边界走，拓扑后自动将材质边界转为 UV 接缝。解决 QR 均匀网格无法自动检测接缝的痛点。

## 为什么有效

| 传统流程 | 联合流程 |
|---------|---------|
| QR → 手动打 6501 条接缝 | QR 时预埋 Material ID → 自动转 ~200-500 条接缝 |
| QR 均匀法线 ~1-2°，无法自动检测 | Material ID 提供语义边界，不依赖法线 |
| 1145 个碎片岛 | 50-100 个语义岛，利用率更高 |
| 接缝位置不可控 | 接缝沿衣服/身体/头发自然边界 |

## 三步流程

### Step 1: 高模预处理 — Material ID 标记

在 QR 之前，将高模顶点按语义分组并分配 Material ID：

```python
import bpy, bmesh
from mathutils import Vector

def assign_material_ids(obj):
    """基于曲率和位置自动分配材质ID"""
    mesh = obj.data
    bm = bmesh.new(); bm.from_mesh(mesh)
    
    # 创建材质槽
    mats = {
        'body': 0,      # 皮肤
        'clothes': 1,   # 衣服
        'hair': 2,      # 头发
        'eyes': 3,      # 眼球
    }
    for name in mats:
        mat = bpy.data.materials.new(name)
        obj.data.materials.append(mat)
    
    # 规则分类（可根据模型调整）
    for f in bm.faces:
        c = f.calc_center_median()
        n = f.normal
        
        # 眼球：高曲率 + 头部区域 + 小尺寸
        if c.z > 0.85 and abs(c.x) < 0.05 and c.y < -0.02:
            f.material_index = mats['eyes']
        # 头发：头顶 + 高曲率
        elif c.z > 0.90 and n.z > 0.3:
            f.material_index = mats['hair']
        # 衣服：躯干/四肢，非皮肤色区域（可通过顶点色或纹理判断）
        elif c.z < 0.85 and c.z > 0.10:
            # 简单规则：假设衣服覆盖躯干，身体暴露四肢末端
            if abs(c.x) < 0.15 and c.y < -0.01:
                f.material_index = mats['clothes']
            else:
                f.material_index = mats['body']
        else:
            f.material_index = mats['body']
    
    bm.to_mesh(mesh); bm.free()
    mesh.update()
    print(f"Material IDs assigned: {len(obj.data.materials)} materials")
```

**更精确的方法**：如果高模有顶点色或纹理，用颜色聚类（K-means）自动分组。

### Step 2: QuadRemesher — Material ID 引导

```python
qr = bpy.context.scene.qremesher
qr.target_count = 100000        # 100K quads = ~200K triangles
qr.use_materials = True         # 关键：edge flow 沿材质边界
qr.use_normals = True           # 辅助：也考虑法线
qr.use_vertex_color = False     # 可选：用顶点色控制密度
qr.autodetect_hard_edges = True
qr.adaptive_size = 50.0
qr.adapt_quad_count = True
qr.symmetry_y = True            # T-pose 左右对称

bpy.ops.qremesher.remesh()

# 异步等待完成（poll progress.txt）
import os, time
temp_dir = os.path.expanduser(r'~/AppData/Local/Temp/Exoside/QuadRemesher/Blender')
progress_file = os.path.join(temp_dir, 'progress.txt')
for i in range(300):
    time.sleep(1)
    if os.path.exists(progress_file):
        with open(progress_file) as f:
            if float(f.read().strip()) >= 2.0:
                break
```

**关键参数**：
- `use_materials=True`：QR 会尽量让 quad 边界沿材质 ID 边界走
- `use_normals=True`：在材质边界基础上，进一步沿法线突变调整
- `symmetry_y=True`：保持左右对称（T-pose）

### Step 3: 拓扑后 UV 接缝自动生成

```python
def auto_seam_from_materials(obj):
    """将材质边界边自动标记为 UV 接缝"""
    mesh = obj.data
    bm = bmesh.new(); bm.from_mesh(mesh)
    
    # 找到材质边界边（相邻面材质ID不同）
    seam_edges = []
    for e in bm.edges:
        if len(e.link_faces) == 2:
            f1, f2 = e.link_faces
            if f1.material_index != f2.material_index:
                seam_edges.append(e)
    
    # 标记接缝
    for e in seam_edges:
        e.seam = True
    
    # 补充 X=0 对称轴接缝
    for e in bm.edges:
        v1, v2 = e.verts
        if abs(v1.co.x) < 0.001 and abs(v2.co.x) < 0.001:
            e.seam = True
    
    bm.to_mesh(mesh); bm.free()
    mesh.update()
    print(f"Auto-marked {len(seam_edges)} material boundary seams + symmetry seam")

# UV 展开
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.001)

# 背景模式必须开启 sync
bpy.context.scene.tool_settings.use_uv_select_sync = True
bpy.ops.uv.average_islands_scale()
bpy.ops.uv.pack_islands(rotate=True, margin=0.005)
bpy.ops.object.mode_set(mode='OBJECT')
```

## 预期效果对比

| 指标 | 传统手动 5 接缝 | Material ID 联合 |
|------|---------------|-----------------|
| 接缝数 | 6501 | 200-500 |
| 岛数 | 1145 | 50-100 |
| 接缝位置 | 背中线+手臂+腿 | 衣服/身体/头发自然边界 |
| 利用率 | 60-70% | 70-85% |
| 自动化程度 | 半自动 | 全自动 |

## 注意事项

1. **Material ID 划分粒度**：粗分（身体/衣服/头发/眼球 4 类）即可，过细会增加 QR 处理时间
2. **衣服/身体边界**：如果衣服和身体是同一材质，需通过顶点色或纹理颜色区分
3. **QR 面数**：Material ID 边界会增加 QR 的计算量，target_count 可能需要降低 10-20%
4. **验证**：QR 后检查材质边界是否清晰（`len(e.link_faces) == 2` 且材质不同），模糊边界需手动补充

## 与之前 UV 调研的关系

- 之前结论：QR 均匀网格是"自动 UV 克星"，所有法线检测失效
- 本方案：不依赖法线，用 Material ID 提供语义边界
- 兼容性：可与 ZEN UV `auto_uv_unwrap` 或 Blender ANGLE_BASED 结合使用

## 代码模板

完整可运行脚本见 `scripts/qr_uv_joint_pipeline.py`（待创建）。