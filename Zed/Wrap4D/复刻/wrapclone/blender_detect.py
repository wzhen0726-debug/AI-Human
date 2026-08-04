"""检测本机 Blender 安装路径.

版本策略: 优先使用 Blender 5.2 (本机 hermes 代理独占使用 5.1 的 MCP 端口,
为避免干扰, PyWrap 协同固定走 5.2). 可用环境变量覆盖:
    PYWRAP_BLENDER  指定 blender.exe 完整路径 (最高优先级)
    BLENDER_PATH    同上 (兼容通用约定)
"""

from __future__ import annotations

import glob
import os
import shutil

PREFERRED_VERSION = "5.2"

CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
    r"C:\Program Files (x86)\Blender Foundation\Blender *\blender.exe",
    r"D:\Program Files\Blender Foundation\Blender *\blender.exe",
    r"D:\Blender Foundation\Blender *\blender.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Blender Foundation\Blender *\blender.exe"),
]


def _version_of(path: str) -> tuple:
    try:
        return tuple(int(x) for x in
                     os.path.basename(os.path.dirname(path)).split()[-1].split("."))
    except Exception:
        return (0,)


def find_blender(preferred: str = PREFERRED_VERSION) -> str | None:
    for env in ("PYWRAP_BLENDER", "BLENDER_PATH"):
        p = os.environ.get(env)
        if p and os.path.isfile(p):
            return p
    on_path = shutil.which("blender")
    if on_path and f"Blender {preferred}" in on_path:
        return on_path
    found = []
    for pat in CANDIDATES:
        found.extend(glob.glob(pat))
    if not found:
        return on_path  # PATH 上的任意版本兜底
    # 优先精确匹配首选版本, 其次最高版本
    for p in found:
        if f"Blender {preferred}" in os.path.basename(os.path.dirname(p)):
            return p
    return sorted(found, key=_version_of)[-1]


def blender_headless_args() -> list[str]:
    """后台调用 Blender 的标准参数: 不加载用户插件/配置, 避免干扰其他实例."""
    return ["-b", "--factory-startup"]
