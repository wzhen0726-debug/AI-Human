# -*- coding: utf-8 -*-
"""行尾修复: 今天编辑过、且CRLF全部丢失(0 CRLF但有LF)的 .py/.md 恢复 CRLF。
跳过: 输出/ _备份/ logs/ skill包/(由Hermes侧LF同步, 不干预)/ 混合行尾既有文件。"""
import os, time

BASE = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu"
TODAY = time.strftime("%Y-%m-%d")
ROOTS = [os.path.join(BASE, "演示版_终端控制端"),
         os.path.join(BASE, "方案md记录"),
         os.path.join(BASE, "v3_QuadRemesher_交付")]
SKIP_DIRS = ("输出", "_备份", "logs", "_中间", "skill包", "screenshots", "models", "scripts_", "原始文件")

fixed = []
for root in ROOTS:
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if not fn.endswith((".py", ".md")):
                continue
            p = os.path.join(dp, fn)
            try:
                st = os.stat(p)
                if time.strftime("%Y-%m-%d", time.localtime(st.st_mtime)) != TODAY:
                    continue
                b = open(p, "rb").read()
                crlf = b.count(b"\r\n"); lone = b.count(b"\n") - crlf
                if crlf == 0 and lone > 0:
                    open(p, "wb").write(b.replace(b"\n", b"\r\n"))
                    fixed.append((os.path.relpath(p, BASE), lone))
            except Exception as e:
                print("  ! ", p, e)
print(f"修复 {len(fixed)} 个文件 (CRLF恢复):")
for r, n in fixed:
    print(f"   {r}  ({n}行)")
