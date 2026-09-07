"""数字人资产管线 — 终端控制端 v2.0 (录屏汇报版)
真跑模式: 每命令真实调用 Blender 5.1 处理。
特性: ①单行动态进度(旋转符+进度条+%+用时+实时数据, 原地刷新不刷屏)
      ②每环节清屏(终端最干净, 历史存 logs/)
      ③打点环节自动开 Blender GUI 手动微调, 关窗即继续
      ④05 打点自动弹出《点位指南.md》
命令: 01 / 01a / 02 / 03 / 04 / 05 / all / status / help / quit
环境变量: DEMO_SKIP_GUI=1 跳过GUI手动调整(用现有点位, 供自动化测试)
"""
import os, sys, time, shutil, subprocess, io, re, threading, queue

BASE = os.path.dirname(os.path.abspath(__file__))
DELIVERY = os.path.join(BASE, "交付")
BLENDER = r"D:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
SRC = os.path.join(BASE, "原始文件")
LOGS = os.path.join(BASE, "logs")
os.makedirs(LOGS, exist_ok=True)
SKIP_GUI = bool(os.environ.get("DEMO_SKIP_GUI"))

G, Y, C, R, B, D, W = "\033[32m", "\033[33m", "\033[36m", "\033[31m", "\033[34m", "\033[2m", "\033[0m"
BOLD = "\033[1m"
os.system("")  # 启用Windows终端ANSI
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# 01a / 05 关键脚本目录
S01A = os.path.join(DELIVERY, "01A眼窝与眼球", "scripts")
M01A = os.path.join(DELIVERY, "01A眼窝与眼球", "models")
S05 = os.path.join(DELIVERY, "05骨骼绑定", "ARP新版测试_20260831", "scripts")
B05 = os.path.join(DELIVERY, "05骨骼绑定", "ARP新版测试_20260831")

NOISE = ("register_class", "Registered", "register()", "WARN", "Warning", "bpy_types",
         "better_fbx", "Traceback", 'File "', "Exception in module", "Zen UV", "MACHIN3",
         "B2RUVL", "Unregister", "Blender quit", "Read blend", "addon_utils", "User property",
         "Reloading", "Extra Pies", "ARP首选", "更新骨架", "factory", "INFO: Data are",
         "blender.exe", "ModuleNotFound", "    ~~~", "import bpy", "self.", "mod.register")

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def fmt_time(s):
    m, sec = divmod(int(s), 60)
    return f"{m:02d}:{sec:02d}"

def is_noise(s):
    t = s.strip()
    if not t: return True
    return any(k in s for k in NOISE)

def clean(s):
    """去除ANSI/前缀, 截断为状态文本"""
    s = re.sub(r'\033\[[0-9;]*m', '', s).strip()
    s = s.lstrip('│> ').strip()
    return s

def banner():
    print(f"""
{C}{BOLD}╔══════════════════════════════════════════════════════════════╗
║          数字人资产生产管线 · 终端控制端  v2.0               ║
║          Blender 5.1 · ARP · QuadRemesher · Mixamo           ║
╚══════════════════════════════════════════════════════════════╝{W}
  {G}01 {W} 高模修复与黏连检测     {D}raw_model.glb → 修复后高模 (~2分){W}
  {G}01a{W} 眼窝重建与眼球摆入     {D}半自动打点 → 眼窝 → 眼球 (~6分, 含手动){W}
  {G}02 {W} QuadRemesher 拓扑重建  {D}117万面 → 14万quad (~2分){W}
  {G}03 {W} 自动UV展开             {D}Smart Project 少接缝无碎岛 (~10秒){W}
  {G}04 {W} 纹理烘焙               {D}4K Diffuse + Normal (~30秒){W}
  {G}05 {W} 骨骼绑定与动作重定向   {D}打点 → 55骨 → 走/跑/跳 (~8分, 含手动){W}
  {G}all{W} 全流程顺序执行         {G}status{W} 产物状态   {G}quit{W} 退出
""")

# ============ 单行动态进度运行器 ============
def run_bg(cmd, tag, label, cwd=None, done_mark=None):
    """运行命令, 单行动态进度(旋转符+进度条+%+用时+实时数据), 原地刷新不刷屏。
    详细日志写入 logs/{tag}.txt。返回 True/False(结合done_mark判定真成功)。"""
    log_path = os.path.join(LOGS, f"{tag}.txt")
    q = queue.Queue()
    def reader():
        with io.open(log_path, 'w', encoding='utf-8') as lf:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 cwd=cwd, text=True, encoding='utf-8', errors='ignore')
            for line in p.stdout:
                lf.write(line)
                q.put(line.rstrip())
            p.wait()
            q.put(("__EXIT__", p.returncode))
    th = threading.Thread(target=reader, daemon=True); th.start()

    t0 = time.time(); pct = None; status = label; ret = None; n = 0; anim = 0
    while True:
        try:
            while True:
                item = q.get_nowait()
                if isinstance(item, tuple) and item[0] == "__EXIT__":
                    ret = item[1]; break
                n += 1
                s = item
                m = re.search(r'[Pp]rogress[:\s]+(\d+)\s*%', s)
                if m: pct = int(m.group(1))
                if not is_noise(s):
                    cs = clean(s)
                    if cs: status = cs
        except queue.Empty:
            pass
        if ret is not None: break
        el = time.time() - t0
        spin = SPINNER[anim % len(SPINNER)]; anim += 1
        if pct is not None:
            filled = int(pct / 100 * 22)
            bar = "█" * filled + "░" * (22 - filled); pcts = f"{pct:3d}%"
        else:
            pos = anim % 19
            bar = "░" * pos + "▓▓▓" + "░" * (19 - pos); pcts = " ·· "
        line = f"\r{C}{spin}{W} [{C}{bar}{W}] {Y}{pcts}{W} {status[:36]:<36} {D}{fmt_time(el)}{W}  "
        sys.stdout.write(line); sys.stdout.flush()
        time.sleep(0.1)
    th.join(timeout=2)
    sys.stdout.write("\r" + " " * 110 + "\r"); sys.stdout.flush()
    el = time.time() - t0
    # 真实成功 = 退出码0 且 (无done_mark 或 日志含done_mark)
    log_txt = io.open(log_path, encoding='utf-8', errors='ignore').read() if os.path.exists(log_path) else ""
    ok = (ret == 0) and (done_mark is None or done_mark in log_txt)
    if ok:
        print(f"  {G}✓{W} {label}  {D}{fmt_time(el)} · {n}行日志{W}")
    else:
        reason = "退出码非0" if ret != 0 else f"缺完成标记{done_mark}"
        print(f"  {R}✗ {label} 失败({reason}) — 详见 logs/{tag}.txt{W}")
    return ok

def run_blender(script, tag, label, done_mark=None, args=None, cwd=None):
    cmd = [BLENDER, '-b', '--python', script]
    if args: cmd += ['--'] + args
    return run_bg(cmd, tag, label, cwd=cwd or os.path.dirname(script), done_mark=done_mark)

# ============ GUI 手动调整 ============
def gui_adjust(blend, prompt, md=None):
    """打开Blender GUI让用户手动微调点位, 关闭窗口后继续。md非空则先弹出说明。"""
    if md and os.path.exists(md):
        try:
            os.startfile(md)
            print(f"  {C}📄 已弹出点位说明: {os.path.basename(md)}{W}")
        except Exception as e:
            print(f"  {D}(点位说明打开失败: {e}){W}")
    if SKIP_GUI:
        print(f"  {D}[DEMO_SKIP_GUI] 跳过手动调整, 使用现有点位{W}")
        return True
    if not os.path.exists(blend):
        print(f"  {R}✗ 待调整文件不存在: {blend}{W}"); return False
    print(f"\n  {Y}{BOLD}▶ {prompt}{W}")
    print(f"  {D}即将打开 Blender GUI。调整点位后 Ctrl+S 保存, 关闭窗口即自动继续。{W}")
    try:
        input(f"  {C}按回车打开 Blender 进行手动调整…{W}")
    except (EOFError, KeyboardInterrupt):
        print(); return True
    glog = io.open(os.path.join(LOGS, "gui_adjust.txt"), 'w', encoding='utf-8')
    subprocess.run([BLENDER, blend], stdout=glog, stderr=subprocess.STDOUT)
    glog.close()
    print(f"  {G}✓ GUI 调整完成, 管线继续{W}")
    return True

# ============ 产物统计 / 交付 ============
def stat_blend(blend):
    """返回(对象数, [(名,顶点,面)…]) 用于摘要"""
    code = ("import bpy\nms=[o for o in bpy.data.objects if o.type=='MESH']\n"
            "print('STAT|'+str(len(ms)))\n"
            "for m in sorted(ms,key=lambda o:-len(o.data.vertices))[:2]:\n"
            "    print(f'DATA|{m.name}|{len(m.data.vertices):,}|{len(m.data.polygons):,}')\n")
    try:
        r = subprocess.run([BLENDER, '-b', blend, '--python-expr', code],
                           capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=300)
    except Exception:
        return None, []
    nobj = None; rows = []
    for line in r.stdout.splitlines():
        if line.startswith('STAT|'): nobj = line.split('|')[1]
        elif line.startswith('DATA|'):
            _, nm, v, f = line.split('|'); rows.append((nm, v, f))
    return nobj, rows

def deliver(src, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    if not os.path.exists(src):
        print(f"  {R}✗ 产物缺失: {os.path.basename(src)}{W}"); return False
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    sz = os.path.getsize(dst) / 1024 / 1024
    rel = os.path.relpath(dst, BASE)
    print(f"  {G}✓ 交付{W} {rel} {D}({sz:.1f}MB){W}")
    return True

def check(rel):
    return os.path.exists(os.path.join(DELIVERY, rel))

def summary(title, ok, t0, lines):
    el = (time.time() - t0) / 60
    mark = f"{G}★ 完成{W}" if ok else f"{R}✗ 失败{W}"
    print(f"\n{B}{'─'*56}{W}")
    print(f"{BOLD}{title} {mark}  {D}用时 {el:.1f} 分钟{W}")
    for ln in lines: print("  " + ln)
    print(f"{B}{'─'*56}{W}")

# ============ 各环节 ============
def step_01():
    clear()
    print(f"{Y}{BOLD}▶ 环节 01 · 高模修复与黏连检测{W}\n")
    t0 = time.time()
    glb = os.path.join(SRC, "raw_model.glb")
    if not os.path.exists(glb):
        print(f"{R}✗ 缺少原始文件 raw_model.glb{W}"); return False
    out = os.path.join(DELIVERY, "01高模修复与黏连检测", "models", "01_highpoly_repair.blend")
    script = os.path.join(DELIVERY, "01高模修复与黏连检测", "scripts", "run_repair.py")
    ok = run_blender(script, "01", f"高模修复+黏连检测", args=[glb, out])
    lines = []
    if ok:
        nobj, rows = stat_blend(out)
        for nm, v, f in rows: lines.append(f"{D}网格{W} {nm[:28]} {Y}{v}顶点 / {f}面{W}")
        deliver(out, os.path.join(BASE, "01高模修复", "输出"))
    summary("环节 01 高模修复", ok, t0, lines)
    return ok

def step_01a():
    clear()
    print(f"{Y}{BOLD}▶ 环节 01a · 眼窝重建与眼球摆入 (半自动打点){W}\n")
    t0 = time.time()
    if not check("01高模修复与黏连检测/models/01_highpoly_repair.blend"):
        print(f"{R}✗ 缺少输入, 先运行 01{W}"); return False
    # 1. 自动放睑缘标记点(右眼12点)
    if not run_blender(os.path.join(S01A, "place_eyelid_markers.py"), "01a_1_放点", "放置眼睑缘标记点(右眼12点)"):
        summary("环节 01a", False, t0, []); return False
    # 2. GUI 手动微调标记点
    markers_blend = os.path.join(M01A, "01A_markers_eyelid.blend")
    gui_adjust(markers_blend, "手动微调眼裂轮廓标记点 (右眼12点, 吸附在眼睑缘)")
    # 3. 镜像右→左 + 读取生成轮廓json
    if not run_blender(os.path.join(S01A, "mirror_markers.py"), "01a_2_镜像", "镜像标记点 右眼→左眼"):
        summary("环节 01a", False, t0, []); return False
    if not run_blender(os.path.join(S01A, "read_eyelid_markers.py"), "01a_3_读取", "读取标记点→样条加密72点轮廓"):
        summary("环节 01a", False, t0, []); return False
    # 4. 眼窝制作
    if not run_blender(os.path.join(S01A, "run_eye_socket.py"), "01a_4_眼窝", "眼窝开孔+封碗+内圆角(v48)"):
        summary("环节 01a", False, t0, []); return False
    # 5. 眼球摆入(Eye.fbx)
    if not run_blender(os.path.join(S01A, "run_eyeball_v2.py"), "01a_5_眼球", "眼球摆入(Eye.fbx)+Hazel上色"):
        summary("环节 01a", False, t0, []); return False
    # 6. rim预锐化(供02 QR)
    if not run_blender(os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "rim_pre_sharpen.py"),
                       "01a_6_rim", "rim预锐化(倒角让QR检测折角)"):
        summary("环节 01a", False, t0, []); return False
    lines = [f"{D}眼窝{W} inward_fillet 内圆角定案", f"{D}眼球{W} Eye.fbx 663顶点 · Hazel色 · 角膜自动测量"]
    outd = os.path.join(BASE, "01a眼窝眼球", "输出")
    ok = all([deliver(os.path.join(M01A, "01_1_eye_socket.blend"), outd),
              deliver(os.path.join(M01A, "01_2_eyeball_placed.blend"), outd),
              deliver(os.path.join(M01A, "01_1_eye_socket_rim_sharp.blend"), outd)])
    summary("环节 01a 眼窝与眼球", ok, t0, lines)
    return ok

def step_02():
    clear()
    print(f"{Y}{BOLD}▶ 环节 02 · QuadRemesher 拓扑重建{W}\n")
    t0 = time.time()
    if not check("01A眼窝与眼球/models/01_1_eye_socket_rim_sharp.blend"):
        print(f"{R}✗ 缺少输入, 先运行 01a{W}"); return False
    if not run_blender(os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "02_qr_auto.py"),
                       "02_QR", "QuadRemesher 自动拓扑(目标14万quad)"):
        summary("环节 02", False, t0, []); return False
    if not run_blender(os.path.join(DELIVERY, "02QuadRemesher拓扑", "scripts", "rim_bevel.py"),
                       "02_bevel", "rim倒角(低模眼睑缘锐化)"):
        summary("环节 02", False, t0, []); return False
    qr = os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k.blend")
    lines = []
    nobj, rows = stat_blend(qr)
    for nm, v, f in rows: lines.append(f"{D}低模{W} {nm[:28]} {Y}{v}顶点 / {f}面{W}")
    outd = os.path.join(BASE, "02QR拓扑", "输出")
    ok = all([deliver(qr, outd),
              deliver(os.path.join(DELIVERY, "02QuadRemesher拓扑", "02_qr_150k_rim_bevel.blend"), outd)])
    summary("环节 02 QR拓扑", ok, t0, lines)
    return ok

def step_03():
    clear()
    print(f"{Y}{BOLD}▶ 环节 03 · 自动UV展开{W}\n")
    t0 = time.time()
    if not check("02QuadRemesher拓扑/02_qr_150k_rim_bevel.blend"):
        print(f"{R}✗ 缺少输入, 先运行 02{W}"); return False
    if not run_blender(os.path.join(DELIVERY, "03自动UV_rim_bevel", "scripts", "03_auto_uv_apply_bevel.py"),
                       "03_UV", "应用倒角 + Smart UV Project"):
        summary("环节 03", False, t0, []); return False
    out = os.path.join(DELIVERY, "03自动UV_rim_bevel", "03_auto_uv.blend")
    ok = deliver(out, os.path.join(BASE, "03自动UV", "输出"))
    summary("环节 03 自动UV", ok, t0, [f"{D}UV范围{W} 少接缝无碎岛(66°角度限制)"])
    return ok

def step_04():
    clear()
    print(f"{Y}{BOLD}▶ 环节 04 · 纹理烘焙 (4K){W}\n")
    t0 = time.time()
    if not check("03自动UV_rim_bevel/03_auto_uv.blend"):
        print(f"{R}✗ 缺少输入, 先运行 03{W}"); return False
    if not run_blender(os.path.join(DELIVERY, "04纹理烘焙", "scripts", "04_bake.py"),
                       "04_烘焙", "烘焙 4K Diffuse + Normal"):
        summary("环节 04", False, t0, []); return False
    o = os.path.join(DELIVERY, "04纹理烘焙"); outd = os.path.join(BASE, "04纹理烘焙", "输出")
    ok = all([deliver(os.path.join(o, "04_bake.blend"), outd),
              deliver(os.path.join(o, "04_diffuse_4k.png"), outd),
              deliver(os.path.join(o, "04_normal_4k.png"), outd)])
    summary("环节 04 纹理烘焙", ok, t0, [f"{D}贴图{W} 4096×4096 Diffuse + Normal"])
    return ok

def step_05():
    clear()
    print(f"{Y}{BOLD}▶ 环节 05 · 骨骼绑定与动作重定向{W}\n")
    t0 = time.time()
    if not check("04纹理烘焙/04_bake.blend"):
        print(f"{R}✗ 缺少输入, 先运行 04{W}"); return False
    # 1. AI自动打点(17关节)
    if not run_blender(os.path.join(S05, "step1_ai_markers.py"), "05_1_打点",
                       "ARP AI 自动打点(17关节标记)", done_mark="STEP1_DONE"):
        summary("环节 05", False, t0, []); return False
    # 2. 弹出点位指南 + GUI手动微调
    md = os.path.join(B05, "点位指南.md")
    gui_adjust(os.path.join(B05, "01_AI打点.blend"),
               "手动微调17个关节标记点 (镜像约束自动同步左右)", md=md)
    # 3. go_detect 生成参考骨架
    if not run_blender(os.path.join(S05, "step2_go_detect.py"), "05_2_detect",
                       "ARP go_detect 生成参考骨架", done_mark="STEP2_DONE"):
        summary("环节 05", False, t0, []); return False
    # 4. 提取55骨+权重+眼球+行走
    if not run_blender(os.path.join(S05, "step3_to_7_rig_and_walk.py"), "05_3_绑定",
                       "提取55骨Mixamo骨架+自动权重+并眼球", done_mark="STEPS_3_TO_7_DONE"):
        summary("环节 05", False, t0, []); return False
    # 5. rest归一化
    if not run_blender(os.path.join(S05, "normalize_rest.py"), "05_4_归一化",
                       "骨架rest朝向归一化为Mixamo标准", done_mark="NORMALIZE_DONE"):
        summary("环节 05", False, t0, []); return False
    # 6. 动作重定向
    if not run_blender(os.path.join(S05, "retarget_mixamo.py"), "05_5_重定向",
                       "Mixamo动作重定向(走/跑/跳)", done_mark="RETARGET_DONE"):
        summary("环节 05", False, t0, []); return False
    rig = os.path.join(B05, "03_骨骼绑定.blend")
    lines = []
    nobj, rows = stat_blend(rig)
    lines.append(f"{D}骨架{W} 55骨 Mixamo命名 · 24对对称 · 眼球蒙皮Head")
    lines.append(f"{D}动作{W} 走36帧/跑20帧/跳31帧 · 帧数按参考原样")
    outd = os.path.join(BASE, "05骨骼绑定", "输出")
    ok = all([deliver(rig, outd),
              deliver(os.path.join(B05, "03_mixamo_rest.blend"), outd),
              deliver(os.path.join(B05, "04_动作测试.blend"), outd)])
    summary("环节 05 骨骼绑定与动作", ok, t0, lines)
    return ok

def status():
    print(f"\n{Y}{BOLD}═══ 产物状态 ═══{W}")
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
            sz = os.path.getsize(p) / 1024 / 1024
            t = time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))
            print(f"  {G}●{W} {label:<12} {sz:7.1f}MB  {D}{t}{W}")
        else:
            print(f"  {D}○ {label:<12} 未生成{W}")
    print()

STEPS = {"01": step_01, "01a": step_01a, "02": step_02, "03": step_03, "04": step_04, "05": step_05}

def main():
    banner()
    while True:
        try:
            cmd = input(f"{C}{BOLD}管线 > {W}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if cmd in ("quit", "exit", "q"): break
        elif cmd in ("help", "?"): clear(); banner()
        elif cmd == "status": status()
        elif cmd == "all":
            t0 = time.time(); allok = True
            for c in ["01", "01a", "02", "03", "04", "05"]:
                if not STEPS[c]():
                    print(f"\n{R}✗ 环节{c}失败, 全流程中止{W}"); allok = False; break
                if c != "05":
                    try: input(f"{D}  (回车继续下一环节){W}")
                    except (EOFError, KeyboardInterrupt): pass
            clear()
            if allok:
                print(f"\n{G}{BOLD}★ 全流程完成, 总耗时 {(time.time()-t0)/60:.1f} 分钟{W}")
            status()
        elif cmd in STEPS:
            STEPS[cmd]()
        else:
            print(f"{D}未知命令: {cmd} (输入 help 查看){W}")
    print(f"{D}再见。{W}")

if __name__ == "__main__":
    main()
