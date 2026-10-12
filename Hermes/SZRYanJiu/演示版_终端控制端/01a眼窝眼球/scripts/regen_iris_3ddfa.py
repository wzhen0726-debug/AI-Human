# -*- coding: utf-8 -*-
"""01a 前置步(2026-10-12 集成): 渲染→3DDFA-V3 推理→反投影 → 动态生成 iris_3ddfa.json.

根因/背景: iris_3ddfa.json 原为离线冻结产物; 高模换代后不重生成则眼区语义锚过期
(实测对当前 01 blend R 眼中心偏 4.6mm)。本步按来源 blend md5 门控: 匹配则跳过, 不匹配重生成。
口径与历史逐值一致(跟进验证: 对交付版 blend 复现偏差 0.000mm; 见 scratch/dddfa_followup/REPORT.md)。

用法(宿主 python, 非 Blender 内):
  python regen_iris_3ddfa.py [--blend <01 blend>] [--out <json>] [--force]
env:
  EYE_3DDFA_REGEN=0      → 直接跳过(回退历史离线 json 行为)
  EYE_3DDFA_ROOT         → 3DDFA-V3 仓库根(默认=仓库相对路径 ../../3DDFA-V3)
  EYE_DDFA_JSON          → 输出 json 路径(默认 01a眼窝眼球/3ddfa/iris_3ddfa.json)
  EYE_3DDFA_DEVICE       → cpu(默认)/cuda
副作用纪律: 不改 3DDFA-V3 目录(只读); 旧 json 备份到 logs/_3ddfa_regen/; 中间件落 logs/_3ddfa_regen/<ts>/。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))          # 演示版_终端控制端
SZR = os.path.abspath(os.path.join(ROOT, ".."))                 # SZRYanJiu
BLENDER = r"D:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
DDFA_ROOT = os.environ.get("EYE_3DDFA_ROOT") or os.path.join(SZR, "3DDFA-V3")
VENV_PY = os.path.join(DDFA_ROOT, ".venv", "Scripts", "python.exe")
OUT_JSON = os.environ.get("EYE_DDFA_JSON") or os.path.join(ROOT, "01a眼窝眼球", "3ddfa", "iris_3ddfa.json")
DEFAULT_BLEND = os.path.join(ROOT, "01高模修复", "输出", "01_highpoly_repair.blend")
WORK = os.path.join(ROOT, "logs", "_3ddfa_regen")


def md5_file(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, cwd=None, strip_pypath=True):
    env = {k: v for k, v in os.environ.items() if not (strip_pypath and k.upper() == "PYTHONPATH")}
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[3ddfa-regen] 命令失败 rc={r.returncode}: {cmd}\nSTDOUT尾:\n{r.stdout[-2000:]}\nSTDERR尾:\n{r.stderr[-2000:]}")
        sys.exit(1)
    return r.stdout


def main():
    args = sys.argv[1:]
    blend = DEFAULT_BLEND
    force = "--force" in args
    if "--blend" in args:
        blend = args[args.index("--blend") + 1]
    if "--out" in args:
        globals()["OUT_JSON"] = args[args.index("--out") + 1]
    if os.environ.get("EYE_3DDFA_REGEN", "1").strip() == "0":
        print("[3ddfa-regen] EYE_3DDFA_REGEN=0 → 跳过(沿用现有 json)")
        print("REGEN_DONE")
        return
    if not os.path.exists(blend):
        print(f"[3ddfa-regen] ✗ 输入 blend 不存在: {blend}")
        sys.exit(1)
    bmd5 = md5_file(blend)
    if os.path.exists(OUT_JSON) and not force:
        try:
            old = json.load(open(OUT_JSON, encoding="utf-8"))
            if old.get("source_blend_md5") == bmd5:
                print(f"[3ddfa-regen] json 来源 md5 匹配({bmd5[:8]}…) → 跳过重生成")
                print("REGEN_DONE")
                return
        except Exception:
            pass
    ts = time.strftime("%Y%m%d_%H%M%S")
    wd = os.path.join(WORK, ts)
    os.makedirs(wd, exist_ok=True)
    print(f"[3ddfa-regen] 开始: blend={os.path.basename(blend)} md5={bmd5[:8]}… → {wd}")

    # 1) 渲染正脸(Blender, 口径同 render_front_for_3ddfa: ORTHO 0.40 / aim_z=88% / Workbench TEXTURE)
    run([BLENDER, "-b", "--factory-startup", "-noaudio", "--python-exit-code", "1",
         "--python", os.path.join(HERE, "_3ddfa_render_front.py"), "--", blend, wd])
    # 2) 3DDFA 推理(venv; cwd=仓库根; 剥 PYTHONPATH)
    run([VENV_PY, "demo.py", "-i", wd, "-s", os.path.join(wd, "results"),
         "--device", os.environ.get("EYE_3DDFA_DEVICE", "cpu"), "--backbone", "resnet50"],
        cwd=DDFA_ROOT)
    npy = os.path.join(wd, "results", "face_front", "face_front.npy")
    if not os.path.exists(npy):
        # demo.py 输出位置随 -i/-s 组合变化(实测: 也可能直接落在 wd 顶层) → 搜索定位
        import glob as _g
        hits = _g.glob(os.path.join(wd, "**", "face_front.npy"), recursive=True)
        if not hits:
            print(f"[3ddfa-regen] ✗ 推理输出缺失: {wd} 下无 face_front.npy")
            sys.exit(1)
        npy = hits[0]
        print(f"[3ddfa-regen] npy 定位: {os.path.relpath(npy, wd)}")
    # 3) 反投影(Blender; 9射线法线投票, 口径同 backproject_3ddfa)
    tmp_json = os.path.join(wd, "iris_new.json")
    run([BLENDER, "-b", "--factory-startup", "-noaudio", "--python-exit-code", "1",
         "--python", os.path.join(HERE, "_3ddfa_backproject.py"), "--",
         blend, os.path.join(wd, "cam_params.json"), npy, tmp_json])
    d = json.load(open(tmp_json, encoding="utf-8"))
    if "L" not in d or "R" not in d:
        print("[3ddfa-regen] ✗ 反投影缺眼(射线未命中) → 不写 json")
        sys.exit(1)
    d["source_blend_md5"] = bmd5
    d["generated_at"] = ts
    d["generator"] = "regen_iris_3ddfa.py(3DDFA-V3 反投影, 口径同交付版)"
    # 备份旧 json 再写
    if os.path.exists(OUT_JSON):
        bk = os.path.join(WORK, f"iris_3ddfa.pre_regen_{ts}.json")
        shutil.copy2(OUT_JSON, bk)
        print(f"[3ddfa-regen] 旧 json 已备份: {bk}")
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    cL, cR = d["L"]["center_3d"], d["R"]["center_3d"]
    import math
    print(f"[3ddfa-regen] 已写 {OUT_JSON}: L=({cL[0]*1000:.2f},{cL[1]*1000:.2f},{cL[2]*1000:.2f})mm "
          f"R=({cR[0]*1000:.2f},{cR[1]*1000:.2f},{cR[2]*1000:.2f})mm 眼间距={math.dist(cL, cR)*1000:.2f}mm")
    print("REGEN_DONE")


main()
