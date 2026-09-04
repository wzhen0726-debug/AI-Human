"""数字人资产管线 — 终端控制端
真跑模式: 每个命令真实调用 Blender 处理, 实时输出处理数据。
命令: 01 / 01a / 02 / 03 / 04 / 05 / all / status / help / quit
"""
import os, sys, time, shutil, subprocess, io

BASE = os.path.dirname(os.path.abspath(__file__))
DELIVERY = os.path.join(BASE, "交付")
BLENDER = r"D:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
SRC = os.path.join(BASE, "原始文件")

# ANSI
G, Y, C, R, B, D, W = "\033[32m", "\033[33m", "\033[36m", "\033[31m", "\033[34m", "\033[2m", "\033[0m"
os.system("")  # 启用Windows终端ANSI

def banner():
    print(f"""
{C}╔══════════════════════════════════════════════════════════╗
║        数字人资产生产管线 · 终端控制端  v1.0             ║
║        Blender 5.1 · ARP · QuadRemesher · Mixamo         ║
╚══════════════════════════════════════════════════════════╝{W}
  {G}01 {W}高模修复与黏连检测      {D}raw_model.glb → 修复后高模{W}
  {G}01a{W} 眼窝重建与眼球摆入      {D}眼窝开孔(杏仁眼裂) + 眼球定位{W}
  {G}02 {W}QuadRemesher 拓扑重建   {D}117万面 → 14万quad 均匀四边面{W}
  {G}03 {W}自动UV展开              {D}Smart Project 少接缝无碎岛{W}
  {G}04 {W}纹理烘焙                {D}4K Diffuse + Normal{W}
  {G}05 {W}骨骼绑定与动作重定向    {D}55骨Mixamo骨架 + 走/跑/跳{W}
  {G}all{W} 全流程顺序执行          {G}status{W} 查看产物状态  {G}quit{W} 退出
""")

def run_blender(script, tag, cwd=None):
    """运行Blender脚本, 实时流式输出日志"""
    t0 = time.time()
    print(f"\n{B}┌─[{tag}]─────────────────────────────────────────{W}")
    print(f"{D}│ 引擎: Blender 5.1  脚本: {os.path.basename(script)}{W}")
    if not os.path.exists(script):
        print(f"{R}│ ✗ 脚本不存在: {script}{W}")
        return False
    log_dir = os.path.join(BASE, "logs"); os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{tag}.txt")
    log_f = io.open(log_path, 'w', encoding='utf-8')
    n_lines = 0
    p = subprocess.Popen([BLENDER, '-b', '--python', script],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         cwd=cwd or os.path.dirname(script),
                         text=True, encoding='utf-8', errors='ignore')
    for line in p.stdout:
        log_f.write(line); n_lines += 1
        s = line.rstrip()
        if not s: continue
        # 过滤纯噪声行(寄存器/插件警告), 突出数据行
        if any(k in s for k in ("register_class", "Registered", "register()", "WARN", "Warning")):
            continue
        prefix = f"{D}│{W} "
        if any(k in s for k in ("ERROR", "Error", "Traceback")): prefix = f"{R}│{W} "
        elif any(k in s for k in ("DONE", "Saved", "已保存", "保存完成", "✓", "PASS")): prefix = f"{G}│{W} "
        print(prefix + s)
    p.wait(); log_f.close()
    el = time.time() - t0
    ok = (p.returncode == 0)
    print(f"{B}└─ {('✓ 完成' if ok else '✗ 失败')}  耗时 {el:.1f}s  日志 {n_lines}行 → logs/{tag}.txt{W}")
    return ok

def stat_blend(blend, label):
    """打印blend内网格统计数据(顶点/面/对象)"""
    code = (
        "import bpy\n"
        "ms=[o for o in bpy.data.objects if o.type=='MESH']\n"
        f"print('STAT|'+str(len(ms)))\n"
        "for m in sorted(ms,key=lambda o:-len(o.data.vertices))[:3]:\n"
        "    print(f'DATA|{m.name}|{len(m.data.vertices):,}|{len(m.data.polygons):,}')\n"
    )
    r = subprocess.run([BLENDER, '-b', blend, '--python-expr', code],
                       capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=300)
    for line in r.stdout.splitlines():
        if line.startswith('STAT|'):
            print(f"   {Y}对象数: {line.split('|')[1]} 个网格{W}")
        elif line.startswith('DATA|'):
            _, name, v, f = line.split('|')
            print(f"   {Y}{name}: {v} 顶点 / {f} 面{W}")

def deliver(src, dst_dir, tag):
    """复制产物到输出文件夹"""
    os.makedirs(dst_dir, exist_ok=True)
    if not os.path.exists(src):
        print(f"{R}   ✗ 产物缺失: {os.path.basename(src)}{W}"); return False
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    sz = os.path.getsize(dst)/1024/1024
    print(f"   {G}✓ 交付: {dst_dir.replace(BASE,'').strip(os.sep)}{os.sep}{os.path.basename(dst)} ({sz:.1f}MB){W}")
    return True

def check(name):
    return os.path.exists(os.path.join(DELIVERY, name))

# ============ 各环节 ============
def step_01():
    print(f"\n{Y}▶ 环节01: 高模修复与黏连检测{W}")
    glb = os.path.join(SRC, "raw_model.glb")
    if not os.path.exists(glb):
        print(f"{R}✗ 缺少原始文件: 原始文件/raw_model.glb{W}"); return False
    print(f"   输入: raw_model.glb ({os.path.getsize(glb)/1024/1024:.1f}MB)")
    out_blend = os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_highpoly_repair.blend")
    script = os.path.join(DELIVERY, "01高模修复与黏连检测", "scripts", "run_repair.py")
    # run_repair 支持 -- <input> <output> 传参
    print(f"{B}┌─[01_修复]─────────────────────────────────────────{W}")
    p = subprocess.Popen([BLENDER, '-b', '--factory-startup', '--python', script, '--', glb, out_blend],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding='utf-8', errors='ignore')
    n = 0
    for line in p.stdout:
        s = line.rstrip()
        if s and not any(k in s for k in ("register_class", "Registered", "WARN")):
            print(f"{D}│{W} " + s); n += 1
    p.wait()
    print(f"{B}└─ {'✓' if p.returncode==0 else '✗'} 完成{W}")
    if p.returncode != 0: return False
    stat_blend(out_blend, "01")
    return deliver(out_blend, os.path.join(BASE, "01高模修复", "输出"), "01")

def step_01a():
    print(f"\n{Y}▶ 环节01a: 眼窝重建与眼球摆入{W}")
    if not check("01高模修复与黏连检测/models/01_highpoly_repair.blend"):
        print(f"{R}✗ 缺少输入, 先运行 01{W}"); return False
    s01a = os.path.join(DELIVERY, "01A眼窝与眼球", "scripts")
    if not run_blender(os.path.join(s01a, "run_eye_socket.py"), "01a_眼窝"): return False
    if not run_blender(os.path.join(s01a, "run_eyeball.py"), "01a_眼球"): return False
    if not run_blender(os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "rim_pre_sharpen.py"), "01a_rim锐化"): return False
    m = os.path.join(DELIVERY, "01A眼窝与眼球", "models")
    outd = os.path.join(BASE, "01a眼窝眼球", "输出")
    ok = all([
        deliver(os.path.join(m, "01_1_eye_socket.blend"), outd, "01a"),
        deliver(os.path.join(m, "01_2_eyeball_placed.blend"), outd, "01a"),
        deliver(os.path.join(m, "01_1_eye_socket_rim_sharp.blend"), outd, "01a"),
    ])
    return ok

def step_02():
    print(f"\n{Y}▶ 环节02: QuadRemesher 拓扑重建{W}")
    if not check("01A眼窝与眼球/models/01_1_eye_socket_rim_sharp.blend"):
        print(f"{R}✗ 缺少输入, 先运行 01a{W}"); return False
    if not run_blender(os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "02_qr_auto.py"), "02_QR拓扑"): return False
    if not run_blender(os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "rim_bevel.py"), "02_rim倒角"): return False
    outd = os.path.join(BASE, "02QR拓扑", "输出")
    return all([
        deliver(os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend"), outd, "02"),
        deliver(os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_bevel.blend"), outd, "02"),
    ])

def step_03():
    print(f"\n{Y}▶ 环节03: 自动UV展开{W}")
    if not check("02QuadRemesher拓扑/02_qr_150k_rim_bevel.blend"):
        print(f"{R}✗ 缺少输入, 先运行 02{W}"); return False
    if not run_blender(os.path.join(DELIVERY, "03自动UV_rim_bevel", "scripts", "03_auto_uv_apply_bevel.py"), "03_UV"): return False
    return deliver(os.path.join(DELIVERY, "03自动UV_rim_bevel", "03_auto_uv.blend"),
                   os.path.join(BASE, "03自动UV", "输出"), "03")

def step_04():
    print(f"\n{Y}▶ 环节04: 纹理烘焙 (4K){W}")
    if not check("03自动UV_rim_bevel/03_auto_uv.blend"):
        print(f"{R}✗ 缺少输入, 先运行 03{W}"); return False
    if not run_blender(os.path.join(DELIVERY, "04纹理烘焙", "scripts", "04_bake.py"), "04_烘焙"): return False
    o = os.path.join(DELIVERY, "04纹理烘焙")
    outd = os.path.join(BASE, "04纹理烘焙", "输出")
    return all([
        deliver(os.path.join(o, "04_bake.blend"), outd, "04"),
        deliver(os.path.join(o, "04_diffuse_4k.png"), outd, "04"),
        deliver(os.path.join(o, "04_normal_4k.png"), outd, "04"),
    ])

def step_05():
    print(f"\n{Y}▶ 环节05: 骨骼绑定与动作重定向{W}")
    if not check("04纹理烘焙/04_bake.blend"):
        print(f"{R}✗ 缺少输入, 先运行 04{W}"); return False
    base05 = os.path.join(DELIVERY, "05骨骼绑定", "ARP新版测试_20260831")
    r = subprocess.run([sys.executable, os.path.join(base05, "scripts", "run_all.py")],
                       cwd=base05)
    if r.returncode != 0:
        print(f"{R}✗ 05管线失败, 见 {base05}/logs/{W}"); return False
    outd = os.path.join(BASE, "05骨骼绑定", "输出")
    return all([
        deliver(os.path.join(base05, "03_骨骼绑定.blend"), outd, "05"),
        deliver(os.path.join(base05, "03_mixamo_rest.blend"), outd, "05"),
        deliver(os.path.join(base05, "04_动作测试.blend"), outd, "05"),
    ])

def status():
    print(f"\n{Y}═══ 产物状态 ═══{W}")
    items = [
        ("01 高模修复", "01高模修复与黏连检测/models/01_highpoly_repair.blend"),
        ("01a 眼窝", "01A眼窝与眼球/models/01_1_eye_socket.blend"),
        ("01a 眼球", "01A眼窝与眼球/models/01_2_eyeball_placed.blend"),
        ("02 QR拓扑", "02QuadRemesher拓扑/02_qr_150k.blend"),
        ("03 UV", "03自动UV_rim_bevel/03_auto_uv.blend"),
        ("04 烘焙", "04纹理烘焙/04_bake.blend"),
        ("05 绑定", "05骨骼绑定/ARP新版测试_20260831/03_骨骼绑定.blend"),
        ("05 动作", "05骨骼绑定/ARP新版测试_20260831/04_动作测试.blend"),
    ]
    for label, rel in items:
        p = os.path.join(DELIVERY, rel)
        if os.path.exists(p):
            sz = os.path.getsize(p)/1024/1024
            t = time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))
            print(f"  {G}●{W} {label:<12} {sz:7.1f}MB  {t}")
        else:
            print(f"  {D}○{W} {label:<12} {D}未生成{W}")

STEPS = {"01": step_01, "01a": step_01a, "02": step_02, "03": step_03,
         "04": step_04, "05": step_05}

def main():
    banner()
    while True:
        try:
            cmd = input(f"{C}管线 > {W}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if cmd in ("quit", "exit", "q"): break
        elif cmd in ("help", "?"): banner()
        elif cmd == "status": status()
        elif cmd == "all":
            t0 = time.time()
            for c in ["01", "01a", "02", "03", "04", "05"]:
                if not STEPS[c]():
                    print(f"{R}✗ 环节{c}失败, 全流程中止{W}"); break
            else:
                print(f"\n{G}★ 全流程完成, 总耗时 {(time.time()-t0)/60:.1f} 分钟{W}")
                status()
        elif cmd in STEPS:
            t0 = time.time()
            if STEPS[cmd]():
                print(f"\n{G}★ 环节{cmd}完成, 耗时 {(time.time()-t0)/60:.1f} 分钟{W}")
        else:
            print(f"{D}未知命令: {cmd} (输入 help 查看){W}")
    print(f"{D}再见。{W}")

if __name__ == "__main__":
    main()
