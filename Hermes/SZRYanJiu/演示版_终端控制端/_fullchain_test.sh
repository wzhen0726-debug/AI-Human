#!/bin/bash
# 全流程测试链 2026-09-16
# 阶段: 01修复 → 01A眼窝+眼球 → 02QR+碗 → [交接] → 03UV → [交接] → 04烘焙
# 每阶段: 记录时间/退出码/关键日志; 失败即停并记录
BL="/d/Program Files/Blender Foundation/Blender 5.1/blender.exe"
D="E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端"
cd "$D" || exit 9
LOG="$D/logs/_全流程测试_20260916.log"
: > "$LOG"
say() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
stage() {  # $1=名称  $2=workdir  $3=script  $4...=额外参数
    local name="$1"; shift; local wd="$1"; shift; local sc="$1"; shift
    say "===== 阶段开始: $name"
    local t0=$(date +%s)
    ( cd "$wd" && timeout 14400 "$BL" -b --factory-startup --python "$sc" "$@" > "/tmp/stage_${name}.log" 2>&1 )
    local rc=$?
    local t1=$(date +%s)
    say "阶段结束: $name  退出码=$rc  用时=$(( (t1-t0)/60 ))分$(( (t1-t0)%60 ))秒"
    echo "----- $name 日志尾部 -----" >> "$LOG"
    tail -25 "/tmp/stage_${name}.log" >> "$LOG"
    echo "-------------------------" >> "$LOG"
    if [ $rc -ne 0 ]; then
        say "!! 阶段 $name 失败(退出码 $rc), 链条中止"
        return $rc
    fi
    return 0
}

say "全流程测试开始; Blender=$(basename "$BL")"
say "git头: $(git -C "$D" rev-parse --short HEAD 2>/dev/null)"

# 1) 01 高模修复
stage "01修复" "交付/01高模修复与黏连检测/scripts" "run_repair.py" -- "$D/原始文件/raw_model.glb" "$D/01高模修复/输出/01_highpoly_repair.blend" || exit 1
ls -l --time-style="+%H:%M" "$D/01高模修复/输出/01_highpoly_repair.blend" | tee -a "$LOG"

# 2) 01A 眼窝
stage "01A眼窝" "交付/01A眼窝与眼球/scripts" "run_eye_socket.py" || exit 2
# 3) 01A 眼球
stage "01A眼球" "交付/01A眼窝与眼球/scripts" "run_eyeball_v2.py" || exit 3
ls -l --time-style="+%H:%M" "$D/01a眼窝眼球/输出/"*.blend | tee -a "$LOG"

# 4) 02 QR
stage "02QR" "交付/02QuadRemesher拓扑/scripts" "02_qr_auto.py" || exit 4
# 5) 02 碗
stage "02碗" "交付/02QuadRemesher拓扑/scripts" "02qr_socket_cup.py" || exit 5
ls -l --time-style="+%H:%M" "$D/02QR拓扑/输出/"*.blend | tee -a "$LOG"

# 交接: 把最终02产物拷进交付(03的读入口)
cp -f "$D/02QR拓扑/输出/02_qr_150k_socket.blend" "$D/交付/02QuadRemesher拓扑/02_qr_150k.blend"
say "交接: 02_qr_150k_socket.blend → 交付/02QuadRemesher拓扑/02_qr_150k.blend"

# 6) 03 UV
stage "03UV" "交付/03自动UV/scripts" "03_auto_uv.py" || exit 6
# 交接: 03产物 → 交付
cp -f "$D/03自动UV/输出/03_auto_uv.blend" "$D/交付/03自动UV/03_auto_uv.blend"
say "交接: 03_auto_uv.blend → 交付/03自动UV/"
ls -l --time-style="+%H:%M" "$D/03自动UV/输出/"*.blend 2>/dev/null | tee -a "$LOG"

# 7) 04 烘焙
stage "04烘焙" "交付/04纹理烘焙/scripts" "04_bake.py" || exit 7
ls -l --time-style="+%H:%M" "$D/04纹理烘焙/输出/" 2>/dev/null | tee -a "$LOG"

say "全流程测试完成: 01→01A→02→03→04 全部通过"
say "git状态(应无意外改动):"
git -C "$D" status --short 2>/dev/null | head -20 | tee -a "$LOG"
say "FULLCHAIN_DONE"
