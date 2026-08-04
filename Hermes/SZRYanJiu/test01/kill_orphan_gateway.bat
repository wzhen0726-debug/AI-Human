@echo off
REM 一键清理 Hermes 孤儿 gateway 进程
REM 用途：Hermes 更新前杀掉所有残留的 "gateway run" python 进程
REM 安全：不会杀当前桌面 app 的 serve 后端（父进程是活跃 Hermes.exe）
REM
REM 这个 .bat 只是包装器，实际逻辑在 kill_orphan_gateway.ps1

setlocal

set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%kill_orphan_gateway.ps1"

if not exist "%PS1%" (
    echo ERROR: kill_orphan_gateway.ps1 not found in %SCRIPT_DIR%
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
endlocal
