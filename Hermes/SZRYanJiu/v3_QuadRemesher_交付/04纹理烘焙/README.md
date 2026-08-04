# 步骤04：纹理烘焙

**日期**: 2026-07-31  |  **状态**: 已验证通过

---

## 功能

将 01 修复后的高模（193 万面）的贴图细节，烘焙到 03 UV 展开后的低模（23.5 万面）上，输出 Diffuse + Normal 双贴图。

## 流程

1. **加载低模**（03_auto_uv.blend，已展开 UV）
2. **导入高模**（01_highpoly_repair.blend）
3. **替换高模贴图**为修复版（01_original_tex_fixed.png）
4. **Cycles 烘焙 Diffuse**（4K，Selected to Active，cage_extrusion=0.01，max_ray_distance=0.05）
5. **Cycles 烘焙 Normal**（4K，同参数）
6. **导出 FBX**（含贴图，供 Mixamo 绑定）

## 脚本

`scripts/04_bake.py`

## 输入/输出

| 项目 | 路径 |
|------|------|
| 低模 | `03自动UV/03_auto_uv.blend` |
| 高模 | `01高模修复与黏连检测/models/01_highpoly_repair.blend` |
| Diffuse | `04纹理烘焙/04_diffuse_4k.png` (11.3 MB) |
| Normal | `04纹理烘焙/04_normal_4k.png` (6.8 MB) |
| 场景 | `04纹理烘焙/04_bake.blend` (8.8 MB) |
| FBX | `04纹理烘焙/05_for_mixamo.fbx` (26.8 MB) |

## 验证结果

| 文件 | 大小 | 状态 |
|------|------|------|
| 04_diffuse_4k.png | 9.7 MB | ✅ |
| 04_normal_4k.png | 5.9 MB | ✅ |
| 04_bake.blend | 8.6 MB | ✅ |
| 05_for_mixamo.fbx | 24.4 MB | ✅ |

## Blender 5.1 兼容性修复

- `bpy.ops.object.bake(type='DIFFUSE')` 不使用 `save_mode='EXTERNAL'`（避免路径问题）
- `NodeLinks.remove()` 只接受 1 个参数，需分两次遍历删除（详见 01 操作手册难题 8）
