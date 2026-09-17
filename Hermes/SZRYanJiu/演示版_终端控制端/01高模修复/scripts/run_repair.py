"""
高模修复一键运行脚本（网格修复 + 黏连修复）
用法:
  blender --background --factory-startup --python scripts/run_repair.py [-- <input.glb> <output.blend>]
默认: input/raw_model.glb → v6_run/01_repair.blend
"""
import bpy, sys, os, json

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)

if '--' in sys.argv:
    argv = sys.argv[sys.argv.index('--') + 1:]
    GLB_PATH = argv[0]
    OUTPUT_PATH = argv[1]
else:
    GLB_PATH = os.path.join(PROJECT_DIR, "input", "raw_model.glb")
    OUTPUT_PATH = os.path.join(PROJECT_DIR, "v6_run", "01_repair.blend")

print("=" * 60)
print("高模修复（网格修复 + 黏连修复）")
print(f"输入: {GLB_PATH}")
print(f"输出: {OUTPUT_PATH}")
print("=" * 60)

sys.path.insert(0, SCRIPTS_DIR)
import repair, adhesion

# 1. 导入GLB
print("\n[0] 导入原始模型...")
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

# 2. 获取主网格
obj = repair.get_main_mesh()
if not obj:
    print("ERROR: 导入后未找到网格")
    sys.exit(1)

# 3. 网格修复
print("\n[0] 开始网格修复...")
t0 = __import__('time').time()
repair_result = repair.repair_pipeline(obj, smooth_iter=2, smooth_factor=0.3)
print(f"[0] 网格修复完成 ({__import__('time').time()-t0:.1f}s)")

# 4. 黏连修复
print("\n[0] 开始黏连修复...")
t0 = __import__('time').time()
adhesion_result = adhesion.adhesion_pipeline(
    obj, threshold_mm=None, push_step_mm=None,  # None=按身高自动
    smooth_iter=5, smooth_factor=0.2, max_pairs=5000)
print(f"[0] 黏连修复完成 ({__import__('time').time()-t0:.1f}s)")

# 5. 最终质量检查
final_check = repair.verify_mesh(obj)

# 5.5 最终焊接 (v17): 保证 QR-ready, 解决 xremesh 卡 21%
weld_result = repair.final_weld_for_qr(obj)

# 6. 保存
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_PATH)
print(f"\n保存完成: {OUTPUT_PATH}")
print(f"\n最终模型: {final_check['verts']} verts, {final_check['faces']} faces")
print(f"水密: {final_check['watertight']}, 流形: {final_check['manifold']}")
print(f"非流形边: {final_check['non_manifold_edges']}, 边界边: {final_check['boundary_edges']}")
print(f"尺寸: {final_check['dimensions']}")
print(f"最终焊接: 焊掉 {weld_result['welded']} 顶点, 补 {weld_result['filled']} 孔面, "
      f"焊后非流形={weld_result['non_manifold']} 边界={weld_result['boundary']}")
print("=" * 60)
