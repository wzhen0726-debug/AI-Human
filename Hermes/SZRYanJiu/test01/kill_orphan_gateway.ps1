# Hermes 孤儿 gateway 清理脚本
# 由 kill_orphan_gateway.bat 调用，也可独立运行：
#   powershell -NoProfile -ExecutionPolicy Bypass -File kill_orphan_gateway.ps1

$ErrorActionPreference = 'SilentlyContinue'

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Hermes orphan gateway cleaner" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$killed = 0
$skipped = 0

Write-Host "[1/2] Scanning all python.exe processes..."
Write-Host ""

# 找所有命令行含 "gateway run" 的 python.exe
$gateways = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'gateway run' }

foreach ($proc in $gateways) {
    $pid_ = $proc.ProcessId
    $ppid = $proc.ParentProcessId

    # 检查父进程是否还活着
    $parent = Get-Process -Id $ppid -ErrorAction SilentlyContinue

    if ($parent) {
        $parentName = $parent.ProcessName
        if ($parentName -eq 'Hermes') {
            Write-Host "[SKIP] PID $pid_ parent $ppid is active Hermes.exe - safe to keep" -ForegroundColor Yellow
            $skipped++
        } else {
            Write-Host "[KILL] PID $pid_ parent $ppid is '$parentName' - orphan gateway" -ForegroundColor Red
            Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
            if ($?) { $killed++ } else { Write-Host "       FAILED to kill PID $pid_" -ForegroundColor Red }
        }
    } else {
        Write-Host "[KILL] PID $pid_ parent $ppid is dead - orphan gateway" -ForegroundColor Red
        Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
        if ($?) { $killed++ } else { Write-Host "       FAILED to kill PID $pid_" -ForegroundColor Red }
    }
}

Write-Host ""
Write-Host "[2/2] Done"
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Result: killed $killed, skipped $skipped" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if ($killed -gt 0) {
    Write-Host "OK Cleanup done. You can retry the update now." -ForegroundColor Green
} elseif ($skipped -gt 0) {
    Write-Host "WARN Only active Hermes backend found, no orphan gateway." -ForegroundColor Yellow
    Write-Host "     If update still fails, check for other Hermes windows running." -ForegroundColor Yellow
} else {
    Write-Host "INFO No gateway processes found." -ForegroundColor Gray
}

Write-Host ""
Read-Host "Press Enter to exit"
