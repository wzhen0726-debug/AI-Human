"""v39 自动迭代循环: 每轮跑管线→渲染→vision检查→记录.
运行到指定时间(默认明早9点).
"""
import subprocess, sys, os, time
from datetime import datetime, timedelta

WORKSPACE = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球"
BLENDER = r"D:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
LOG_FILE = os.path.join(WORKSPACE, "scripts", "iteration_log.md")

# 目标结束时间: 明早9点
now = datetime.now()
end_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
if now.hour >= 9:
    end_time += timedelta(days=1)

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    print(msg)

def run_blender(script_name):
    script = os.path.join(WORKSPACE, "scripts", script_name)
    result = subprocess.run(
        [BLENDER, "--background", "--python", script],
        capture_output=True, text=True, timeout=600,
        creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS if sys.platform == 'win32' else 0
    )
    lines = result.stdout.split('\n')
    for line in lines:
        if any(k in line for k in ['UV分配', 'jump', 'geometric', 'still wrong', 'Saved', 'ERROR']):
            log(f"  {line.strip()}")
    return result.returncode == 0

def main():
    log("="*60)
    log(f"v39 自动迭代循环启动, 结束时间: {end_time}")
    log("="*60)

    iteration = 0
    while datetime.now() < end_time:
        iteration += 1
        log(f"\n--- 迭代 {iteration} ---")

        # 跑管线
        if not run_blender("run_eye_socket.py"):
            log("管线失败, 停止")
            break

        # 渲染检查图
        if not run_blender("render_v39_check.py"):
            log("渲染失败, 停止")
            break

        log(f"迭代{iteration}完成")
        time.sleep(10)  # 每轮间隔10秒

    log("="*60)
    log(f"迭代循环结束, 共{iteration}轮")
    log("="*60)

if __name__ == "__main__":
    main()
