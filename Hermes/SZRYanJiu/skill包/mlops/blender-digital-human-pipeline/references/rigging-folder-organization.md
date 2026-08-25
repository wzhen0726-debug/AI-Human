# 05骨骼绑定文件夹组织规范 (2026-08-25整理定案)

## 两套流程必须分离（用户明确要求）
> "需要分清 半自动打点 跟 骨骼绑定后 两套文件"

```
05骨骼绑定/
├── A_半自动打点/        ← 打点阶段: 06_rig_markers.blend + joints_measured.json
│                          + mixamo_reference.json + 测量/模板/镜像脚本
├── B_骨骼绑定/          ← 绑定阶段: 06_rig_final.blend/.glb + rig_from_markers.py
├── C_诊断工具/          ← 分析/参考图/验证脚本(重复点检查/肩点参考图等)
├── README.md            ← 两套流程说明 + 运行顺序
├── logs/                ← 运行日志(不入git)
└── screenshots/         ← 参考图
```

## 目录分工原则
- **A** 只放"用户打点前要动的东西"：模板、测量数据、镜像脚本
- **B** 只放"绑定生成产物和生成脚本"：最终rig、权重、GLB、生成脚本
- **C** 只放"诊断/参考/验证"：不直接参与流程的辅助工具

## 脚本路径规则（移动到子目录后）
脚本内 `BASE` 仍用三层上溯到交付根：
```python
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
但输出路径要带上新子目录名，如 `"05骨骼绑定", "A_半自动打点", "06_rig_markers.blend"`。
`rig_from_markers.py` 用命令行参数 `--markers`/`--output`，无参时兜底到A/B目录。

## 历史背景
该文件夹最初在Zed里创建，内容混放怕冲突；停用Zed后按本规范重新归位分组。
.blend/.glb 被gitignore，脚本和json入库。
