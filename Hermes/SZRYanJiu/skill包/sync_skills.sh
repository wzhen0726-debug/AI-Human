#!/bin/bash
# skill包同步脚本: 在 Hermes 真实skill目录 与 项目skill包目录 之间双向拷贝
# 用法: bash sync_skills.sh out  → Hermes→项目(AI更新后)
#       bash sync_skills.sh in   → 项目→Hermes(恢复/换设备后)

SKILL_ROOT="C:/Users/Liyunzhong/AppData/Local/hermes/skills"
PKG="E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/skill包"

SKILLS=(
  "mlops/blender-digital-human-pipeline"
  "3d/blender-body-wrap"
  "3d/blender-head-retopology"
  "3d/blender-uv-texture-baking"
  "3d/glb-inspect-and-report"
  "software-development/error-first-root-cause"
)

if [ "$1" = "out" ]; then
  SRC="$SKILL_ROOT"; DST="$PKG"; echo "方向: Hermes → 项目skill包"
elif [ "$1" = "in" ]; then
  SRC="$PKG"; DST="$SKILL_ROOT"; echo "方向: 项目skill包 → Hermes"
else
  echo "用法: bash sync_skills.sh [out|in]"; exit 1
fi

for s in "${SKILLS[@]}"; do
  if [ -d "$SRC/$s" ]; then
    mkdir -p "$DST/$(dirname "$s")"
    rm -rf "$DST/$s"
    cp -r "$SRC/$s" "$DST/$s"
    echo "  同步: $s"
  else
    echo "  跳过(不存在): $s"
  fi
done
echo "完成。总文件数: $(find "$PKG" -type f -not -name 'sync_skills.sh' | wc -l)"
