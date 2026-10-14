@echo off
chcp 65001 >nul
setlocal
title 02QR sandbox test (formal outputs untouched)
echo ============================================
echo  02QR sandbox test - QR step only, V2 data as-is
echo  Products go to the sandbox run folder;
echo  formal outputs are never touched.
echo ============================================
echo.
set "BASH=D:\Program Files\Git\bin\bash.exe"
if not exist "%BASH%" set "BASH=D:\Program Files\Git\usr\bin\bash.exe"
if not exist "%BASH%" set "BASH=bash"
pushd "%~dp0"
"%BASH%" -c "bash ./run_qr_sandbox.sh"
set "RC=%ERRORLEVEL%"
popd
echo.
if not "%RC%"=="0" echo [WARN] exit code %RC% - check run.log in the newest run folder
echo ---- Done. Products in the newest sandbox run_* folder. Press any key to close ----
pause >nul
