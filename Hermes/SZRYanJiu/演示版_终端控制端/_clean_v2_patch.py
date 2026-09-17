# -*- coding: utf-8 -*-
"""clean v2: ① 清空后连空目录本体一起删(空壳也算"清不掉") ② 删除失败醒目上报(不再静默) ③ 清 __pycache__.
另: 控制台未补洞 copy 前补 makedirs(clean 可能已删掉 输出/ 目录)."""
import ast
P = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\控制台.py"
s = open(P, encoding="utf-8").read()
R = []
def rep(old, new, tag):
    global s
    assert old in s, f"未匹配: {tag}"
    s = s.replace(old, new, 1); R.append(tag)

rep('''    PROTECT = ("01A_markers_eyelid.blend", "eyelid_contour_manual.json", "iris_3ddfa.json",
               "eyeball_finetune_manual.json", ".gitkeep")
    def _wipe(d):
        cnt = 0
        if not os.path.isdir(d):
            return 0
        for root, dirs, files in os.walk(d, topdown=False):
            for f in files:
                if f in PROTECT or f.startswith("01A_markers_eyelid_备份_"):
                    continue
                try: os.remove(os.path.join(root, f)); cnt += 1
                except Exception: pass
            for dd in dirs:
                try: os.rmdir(os.path.join(root, dd)); cnt += 1
                except Exception: pass
        return cnt
    if target in (None, "all"):
        sel = list(targets.keys())
    elif target in targets:
        sel = [target]
    else:
        print(f"{R}✗ 未知环节: {target} (可选: 01/01a/02/03/04/05/all){W}"); show_hint(); return
    n = 0
    for t in sel:
        n += _wipe(targets[t])                                              # ① 输出/ 递归清空(保留手调文件)
        n += _wipe(os.path.join(os.path.dirname(targets[t]), "_中间"))       # ② _中间/ 一并清(防下游读旧件)
    n += _wipe(os.path.join(BASE, "01a眼窝眼球", "screenshots"))
    import glob as _glob
    for d in [os.path.join(BASE, "01高模修复"), os.path.join(BASE, "01a眼窝眼球"),
              os.path.join(BASE, "01a眼窝眼球", "_中间"),
              os.path.join(BASE, "02QR拓扑"), os.path.join(BASE, "03自动UV"),
              os.path.join(BASE, "04纹理烘焙"), os.path.join(BASE, "05骨骼绑定", "ARP新版测试_20260831")]:
        for pat in ("*.blend1", "01A_markers_eyelid_备份_*.blend"):
            for fp in _glob.glob(os.path.join(d, pat)):
                try: os.remove(fp); n += 1
                except Exception: pass''',
'''    PROTECT = ("01A_markers_eyelid.blend", "eyelid_contour_manual.json", "iris_3ddfa.json",
               "eyeball_finetune_manual.json", ".gitkeep")
    _failed = []
    def _try_rm(fp):
        try:
            os.remove(fp); return 1
        except Exception as _e:
            _failed.append((fp, str(_e))); return 0
    def _wipe(d):
        cnt = 0
        if not os.path.isdir(d):
            return 0
        for root, dirs, files in os.walk(d, topdown=False):
            for f in files:
                if f in PROTECT or f.startswith("01A_markers_eyelid_备份_"):
                    continue
                cnt += _try_rm(os.path.join(root, f))
            for dd in dirs:
                try: os.rmdir(os.path.join(root, dd)); cnt += 1
                except Exception: pass
        # 2026-09-17: 清空后连空目录本体也删(用户直接看文件夹, 空壳也算"清不掉"); 含手调文件的目录自动保留
        try:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d); cnt += 1
        except Exception:
            pass
        return cnt
    if target in (None, "all"):
        sel = list(targets.keys())
    elif target in targets:
        sel = [target]
    else:
        print(f"{R}✗ 未知环节: {target} (可选: 01/01a/02/03/04/05/all){W}"); show_hint(); return
    n = 0
    for t in sel:
        n += _wipe(targets[t])                                              # ① 输出/ 递归清空(保留手调文件)
        n += _wipe(os.path.join(os.path.dirname(targets[t]), "_中间"))       # ② _中间/ 一并清(防下游读旧件)
    n += _wipe(os.path.join(BASE, "01a眼窝眼球", "screenshots"))
    import glob as _glob, shutil as _sh
    for d in [os.path.join(BASE, "01高模修复"), os.path.join(BASE, "01a眼窝眼球"),
              os.path.join(BASE, "01a眼窝眼球", "_中间"),
              os.path.join(BASE, "02QR拓扑"), os.path.join(BASE, "03自动UV"),
              os.path.join(BASE, "04纹理烘焙"), os.path.join(BASE, "05骨骼绑定", "ARP新版测试_20260831")]:
        for pat in ("*.blend1", "01A_markers_eyelid_备份_*.blend"):
            for fp in _glob.glob(os.path.join(d, pat)):
                n += _try_rm(fp)
    for d in [os.path.join(BASE, "01高模修复"), os.path.join(BASE, "01a眼窝眼球"),
              os.path.join(BASE, "02QR拓扑"), os.path.join(BASE, "03自动UV"),
              os.path.join(BASE, "04纹理烘焙"), os.path.join(BASE, "05骨骼绑定")]:
        for pc in _glob.glob(os.path.join(d, "**", "__pycache__"), recursive=True):
            try: _sh.rmtree(pc); n += 1
            except Exception: pass''', "1 clean v2")

rep('''    print(f"\\n{G}★ 清理完成, 共删除 {n} 项{W}")''',
'''    print(f"\\n{G}★ 清理完成, 共删除 {n} 项{W}")
    if _failed:
        print(f"{R}⚠ {len(_failed)} 项删除失败(多半被占用: 请在 Blender 里关掉这些文件后重跑 clean){W}")
        for fp, _e in _failed[:8]:
            print(f"  {D}· {os.path.relpath(fp, BASE)}{W}")''', "2 失败上报")

rep('''        if os.path.exists(_pre_src):
            _sh.copy2(_pre_src, _pre)''',
'''        if os.path.exists(_pre_src):
            os.makedirs(os.path.dirname(_pre), exist_ok=True)
            _sh.copy2(_pre_src, _pre)''', "3 未补洞makedirs")

ast.parse(s)
open(P, "w", encoding="utf-8").write(s)
print("clean v2 已应用:", R, flush=True)
