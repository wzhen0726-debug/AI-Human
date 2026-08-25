# Mixamo 绑定 MetaHuman 经验

> 2026-07-28 用户实测：Mixamo 可以绑定 A-pose MetaHuman，并可制作 T-pose 姿态动画。
> 本文档修正之前"Mixamo 不支持 A-pose"的错误说法。

---

## 实测结论

| 项目 | 结果 |
|------|------|
| Mixamo 绑定 A-pose | ✅ 支持 |
| Mixamo 制作 T-pose 动画 | ✅ 支持 |
| 导出格式 | FBX (含骨骼+权重+动画) |
| 骨骼数量 | 65 根 (Mixamo 标准骨骼) |

## 用户提供的文件

- **路径**: `原始模型/Metahuman低模/T-Pose.fbx`
- **内容**: MetaHuman Body (32,334 verts) + Head (24,414 verts) + Mixamo 骨骼 (65 根) + T-pose 姿态
- **骨骼命名**: `mixamorig:Hips`, `mixamorig:Spine`, `mixamorig:LeftShoulder`, `mixamorig:LeftArm`, etc.

## 修正之前的错误说法

之前文档中"Mixamo 要求 T-pose，MetaHuman 使用 A-pose，所以 Mixamo 不支持"的说法是**错误的**。

实际情况：
- Mixamo 可以绑定 A-pose 模型
- Mixamo 提供姿势调整功能，可以把 A-pose 转成 T-pose 动画
- 用户已成功在 Mixamo 中完成 MetaHuman A-pose 绑定并制作 T-pose 姿态

## 教训

**不要凭假设写文档，先让用户实测或自己实测。**

用户原话："下次这种问题，你自己调研不到位，可以让我去实测"

## 使用建议

1. **优先用用户提供的 Mixamo 绑定文件**，不要重复绑定
2. **FBX 导入后检查骨骼位置**，确认是否为 T-pose
3. **Mixamo 骨骼很小**（Hips head/tail 几乎重合），可能需要调整骨骼尺寸或检查缩放
4. **网格 bbox 检查**：X span >1.5m 才是 T-pose（A-pose 约 1.16m）

## 待解决问题

- FBX 导入后骨骼位置异常（Hips head=(0,0,0.010), tail=(0,0,0.011)），几乎是一个点
- 网格 bbox X span 1.159m（仍是 A-pose），说明 T-pose 动画未生效或未正确应用
- 需要检查动画数据或姿势关键帧
