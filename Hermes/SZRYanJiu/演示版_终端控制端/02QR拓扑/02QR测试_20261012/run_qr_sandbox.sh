#!/usr/bin/env bash
# ============================================================
# 02QR 独立沙箱测试跑腿（2026-10-12 建）
#
# 原理：02_qr_auto.py 支持 QR_OUT_ROOT 重定向 —— 所有【写】产物
#       落入 <QR_OUT_ROOT>/02QR拓扑/...，绝不碰正式 _中间/输出。
# 用法：
#   bash run_qr_sandbox.sh                                  # 基线复现
#   QR_SET_FreezeBorders=1 bash run_qr_sandbox.sh           # 注入旋钮
#   QR_IN_BLEND="D:/x/custom.blend" bash run_qr_sandbox.sh  # 自定义输入
#   QR_DRAW_RETRY=0 bash run_qr_sandbox.sh                  # 单抽
#
# 约束：QR 引擎全局串行（共享 %TEMP%\Exoside\...\QRTemp）
#       —— 不要与正式管线/控制台同时跑。
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PIPE="E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端"
BLENDER="D:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
SC="$PIPE/02QR拓扑/scripts/02_qr_auto.py"
TS="$(date +%Y%m%d_%H%M%S)"
RUN="$HERE/沙箱/run_$TS"
mkdir -p "$RUN"

# 关键: 传给 Blender(原生程序) 的环境变量必须是 Windows 形式路径
#   (MSYS 的 /e/... 到了原生侧会被解析成 E:\e\... 怪路径 → 首次踩坑 20261012)
if command -v cygpath >/dev/null 2>&1; then
    RUN_WIN="$(cygpath -m "$RUN")"
else
    RUN_WIN="E:${RUN#/e}"
fi

echo "[02QR测试] 输出沙箱: $RUN"
echo "[02QR测试] 沙箱(Win): $RUN_WIN"
echo "[02QR测试] 输入: ${QR_IN_BLEND:-（默认 01a 当前高模 _中间/01_1_eye_socket_qr.blend）}"
echo "[02QR测试] 旋钮: $(env | grep -E '^QR_' | tr '\n' ' ' || true)"

# QR_OUT_ROOT → 本 run 目录（02_qr_auto.py 全部写操作被重定向到此处）
env QR_OUT_ROOT="$RUN_WIN" \
    "$BLENDER" -b --python-exit-code 1 --python "$SC" \
    > "$RUN/run.log" 2>&1 || {
        echo "[02QR测试] ✗ 退出码非0，查看日志: $RUN/run.log"; exit 1; }

echo "[02QR测试] ✓ 完成"
echo "  产物: $RUN/02QR拓扑/输出/  与  $RUN/02QR拓扑/_中间/"
echo "  日志: $RUN/run.log"