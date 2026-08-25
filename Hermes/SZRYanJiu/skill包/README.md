# 数字人项目 Skill 包（解压版，随时同步）

**位置**: `E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\skill包\`
**来源**: `C:\Users\Liyunzhong\AppData\Local\hermes\skills\`（Hermes Agent 真实 skill 目录）
**更新方式**: AI 随时更新（用户要求：不用打包，解压用，新 skill 随时加入）

## 目录结构（212 个文件，1.8M）

```
skill包/
├── mlops/blender-digital-human-pipeline/   ← 主管线(133文件, 含全部踩坑)
├── 3d/blender-body-wrap/                    ← wrap失败档案
├── 3d/blender-head-retopology/              ← 头部重拓扑
├── 3d/blender-uv-texture-baking/            ← UV+烘焙
├── 3d/glb-inspect-and-report/               ← GLB检查
├── software-development/error-first-root-cause/  ← 错误处理流程
└── sync_skills.sh                           ← 同步脚本(双向)
```

## 跨设备使用

把整个 `skill包` 目录拷到新设备的
`C:\Users\<用户名>\AppData\Local\hermes\skills\`（覆盖合并即可，
分类目录 3d/ mlops/ software-development/ 与 Hermes 原生结构一致）。

## 同步脚本用法

- **AI 更新后 → 拷贝到项目**：`bash sync_skills.sh out`
- **从项目 → 拷贝回 Hermes**：`bash sync_skills.sh in`

（用户自己拷贝时可忽略此脚本，直接整目录复制即可）
