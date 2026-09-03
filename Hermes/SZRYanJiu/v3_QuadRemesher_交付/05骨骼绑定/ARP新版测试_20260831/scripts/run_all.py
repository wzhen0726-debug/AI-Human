"""ARP骨骼绑定 程序化管线 — 统一入口 (2026-09-01)
用法: python run_all.py [起始步骤1~3]   (直接用系统python, 内部自动调Blender)
      python run_all.py 3   ← 从步骤3(建骨+行走)续跑
步骤: 1=AI打点 2=go_detect 3~7=建骨+权重+行走(在step3脚本内连续)
步骤1后建议用户在GUI确认01点位再继续。
产物: 01_AI打点.blend / 02_go_detect骨架.blend / 03_骨骼绑定.blend / 04_动作测试.blend
自检: qa_rig.py(骨架对称/连贯/权重) qa_walk.py(行走起伏) — 跑完自动执行"""
import subprocess, sys, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831"
BLENDER = r"D:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
LOGS = os.path.join(BASE, "logs")
os.makedirs(LOGS, exist_ok=True)

STEPS = [
    ("step1_ai_markers.py", "01_AI打点", "STEP1_DONE"),
    ("step2_go_detect.py", "02_go_detect", "STEP2_DONE"),
    ("step3_to_7_rig_and_walk.py", "03~07_建骨行走", "STEPS_3_TO_7_DONE"),
]

def run(script, tag, done_mark):
    log = os.path.join(LOGS, f"run_{tag}.txt")
    print(f"\n{'='*50}\n运行 {tag}: {script}\n日志: {log}\n{'='*50}")
    with open(log, 'w', encoding='utf-8') as lf:
        p = subprocess.run([BLENDER, '-b', '--python', os.path.join(BASE, script)],
                           stdout=lf, stderr=subprocess.STDOUT, cwd=BASE)
    with open(log, encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if p.returncode != 0 or done_mark not in content:
        print(f"✗ {tag} 失败(exit {p.returncode}, 完成标记{'有' if done_mark in content else '无'}), 见 {log}")
        sys.exit(1)
    print(f"✓ {tag} 完成")

# 起始步骤: 支持 "python run_all.py 2" 和 "-- 2" 两种传法, 默认1
start = 1
for a in sys.argv[1:]:
    if a.isdigit():
        start = int(a); break
if not (1 <= start <= len(STEPS)):
    print(f"起始步骤必须是 1~{len(STEPS)}"); sys.exit(1)
print(f"从步骤{start}开始")
for i, (script, tag, mark) in enumerate(STEPS, 1):
    if i >= start:
        run(script, tag, mark)
print("\n" + "="*50 + "\n全部完成, 跑自检...\n" + "="*50)
for qa in ["qa_rig.py", "qa_walk.py"]:
    subprocess.run([BLENDER, '-b', '--python', os.path.join(BASE, qa)],
                   stdout=open(os.path.join(LOGS, f"run_qa_{os.path.splitext(qa)[0]}.txt"), 'w', encoding='utf-8'),
                   stderr=subprocess.STDOUT, cwd=BASE)
    print(f"  qa {qa} 已跑, 结果在 logs/")
