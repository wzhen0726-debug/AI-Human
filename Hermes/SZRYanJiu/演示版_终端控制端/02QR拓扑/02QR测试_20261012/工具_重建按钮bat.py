# -*- coding: utf-8 -*-
"""重建『按钮_跑02QR沙箱测试.bat』—— 全 ASCII 内容 + CRLF 换行 + chcp 65001。

原因（2026-10-12 实测坑）：首版 .bat 是 UTF-8 + LF 换行，在中文 Windows 的
cmd 下出现乱码并把行解析碎掉（'bash.exe' 不是内部或外部命令 等）。
根治 = 提高稳健性而不是赌编码：
  1) .bat 本体全 ASCII（任何代码页下不破坏解析、不产生乱码）
  2) CRLF 换行（cmd 批处理的硬要求）
  3) chcp 65001 —— 让被调用的 git-bash 的 UTF-8 中文输出正确显示
运行：python 工具_重建按钮bat.py
"""
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "按钮_跑02QR沙箱测试.bat")

lines = [
    "@echo off",
    "chcp 65001 >nul",
    "setlocal",
    "title 02QR sandbox test (formal outputs untouched)",
    "echo ============================================",
    "echo  02QR sandbox test - QR step only, V2 data as-is",
    "echo  Products go to the sandbox run folder;",
    "echo  formal outputs are never touched.",
    "echo ============================================",
    "echo.",
    'set "BASH=D:\\Program Files\\Git\\bin\\bash.exe"',
    'if not exist "%BASH%" set "BASH=D:\\Program Files\\Git\\usr\\bin\\bash.exe"',
    'if not exist "%BASH%" set "BASH=bash"',
    'pushd "%~dp0"',
    '"%BASH%" -c "bash ./run_qr_sandbox.sh"',
    'set "RC=%ERRORLEVEL%"',
    "popd",
    "echo.",
    'if not "%RC%"=="0" echo [WARN] exit code %RC% - check run.log in the newest run folder',
    "echo ---- Done. Products in the newest sandbox run_* folder. Press any key to close ----",
    "pause >nul",
]

data = "\r\n".join(lines) + "\r\n"
with open(PATH, "w", encoding="ascii", newline="") as f:
    f.write(data)

# 校验
raw = open(PATH, "rb").read()
print("写入:", PATH)
print("字节数:", len(raw))
print("CRLF 数:", raw.count(b"\r\n"), "(应为 %d)" % len(lines))
print("最大字节值:", max(raw), "(应 < 128, 即纯 ASCII)")
assert raw.count(b"\r\n") == len(lines), "换行数不符"
assert max(raw) < 128, "含非 ASCII 字节"
print("OK")