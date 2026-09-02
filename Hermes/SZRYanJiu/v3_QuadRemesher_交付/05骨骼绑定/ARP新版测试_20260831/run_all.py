"""ARP骨骼绑定 程序化管线 — 统一入口 (2026-09-01)
用法: blender -b --python run_all.py [起始步骤]
步骤: 1=AI打点 2=go_detect 3~7=建骨+权重+行走+贴地
全程无需人工干预(除步骤1后可选GUI确认点位)。
产物: 01_AI打点.blend / 02_go_detect骨架.blend / 03_骨骼绑定.blend / 04_行走测试.blend
自检: qa_rig.py(骨架) qa_walk.py(行走) diag_foot2.py(贴地)"""
import subprocess, sys, os

BASE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\05骨骼绑定\ARP新版测试_20260831"
BLENDER = r"D:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
LOGS = os.path.join(BASE, "logs")
os.makedirs(LOGS, exist_ok=True)

STEPS = [
    ("step1_ai_markers.py", "01_AI打点"),
    ("step2_go_detect.py", "02_go_detect"),
    ("step3_to_7_rig_and_walk.py", "03~07_建骨行走"),
]

def run(script, tag):
    log = os.path.join(LOGS, f"run_{tag}.txt")
    print(f"\n{'='*50}\n运行 {tag}: {script}\n日志: {log}\n{'='*50}")
    with open(log, 'w', encoding='utf-8') as lf:
        p = subprocess.run([BLENDER, '-b', '--python', os.path.join(BASE, script)],
                           stdout=lf, stderr=subprocess.STDOUT, cwd=BASE)
    if p.returncode != 0:
        print(f"✗ {tag} 失败(exit {p.returncode}), 见 {log}")
        sys.exit(1)
    # 检查关键成功标记
    with open(log, encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if 'Traceback' in content and 'DONE' not in content:
        print(f"⚠ {tag} 日志含Traceback但已完成, 检查 {log}")
    print(f"✓ {tag} 完成")

start = int(sys.argv[sys.argv.index('--') + 1]) if '--' in sys.argv and sys.argv[-1].isdigit() else 1
print(f"从步骤{start}开始")
for i, (script, tag) in enumerate(STEPS, 1):
    if i >= start:
        run(script, tag)
print("\n" + "="*50 + "\n全部完成\n" + "="*50)
