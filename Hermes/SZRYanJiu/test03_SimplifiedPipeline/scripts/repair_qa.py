"""高模修复质检 — 检查网格修复+黏连修复后的模型质量。
Run: blender --background 01_repair.blend --factory-startup --python repair_qa.py
"""
import bpy, bmesh, json, sys, os, math

def run_qa():
    obj = None
    for o in bpy.data.objects:
        if o.type == 'MESH':
            obj = o; break
    if not obj:
        print("QA: FAIL - No mesh found")
        sys.exit(1)

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    loose_verts = sum(1 for v in bm.verts if len(v.link_edges) == 0)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-10)

    xs = [v.co.x for v in mesh.vertices]
    ys = [v.co.y for v in mesh.vertices]
    zs = [v.co.z for v in mesh.vertices]
    dim_x = max(xs) - min(xs)
    dim_y = max(ys) - min(ys)
    dim_z = max(zs) - min(zs)
    cx = (max(xs)+min(xs))/2
    cy = (max(ys)+min(ys))/2
    cz_min = min(zs)

    bm.free()

    # 对高模(非Voxel Remesh)：非流形边<50、边界边<50即可
    # QR能处理少量非流形/边界，不会崩溃
    checks = {
        "mesh_name": obj.name,
        "vert_count": len(mesh.vertices),
        "face_count": len(mesh.polygons),
        "non_manifold_edges": {"value": non_manifold, "max": 50, "pass": non_manifold <= 50},
        "boundary_edges": {"value": boundary, "max": 50, "pass": boundary <= 50},
        "loose_verts": {"value": loose_verts, "max": 0, "pass": loose_verts == 0},
        "degenerate_faces": {"value": degenerate, "max": 0, "pass": degenerate == 0},
        "oriented_arms_along_x": {"value": dim_x > dim_y * 1.5, "pass": dim_x > dim_y * 1.5},
        "centered_x": {"value": round(cx, 6), "max": 0.01, "pass": abs(cx) < 0.01},
        "centered_y": {"value": round(cy, 6), "max": 0.05, "pass": abs(cy) < 0.05},
        "grounded_z": {"value": abs(cz_min) < 0.005, "pass": abs(cz_min) < 0.005},
        "face_count_min": {
            "value": len(mesh.polygons),
            "min": 100000,
            "pass": len(mesh.polygons) >= 100000,
            "note": "高模应保留10万面以上"
        },
        "height_range": {
            "value": round(dim_z, 4),
            "min": 0.8, "max": 2.5,
            "pass": 0.8 <= dim_z <= 2.5
        },
    }

    all_pass = all(c.get("pass", True) for c in checks.values() if isinstance(c, dict))
    checks["OVERALL"] = "PASS" if all_pass else "FAIL"

    print("=" * 60)
    print("高模修复质检报告")
    print("=" * 60)
    for key, val in checks.items():
        if isinstance(val, dict) and "pass" in val:
            status = "✅" if val["pass"] else "❌"
            print(f"  {status} {key}: {val['value']}")
        else:
            print(f"  {key}: {val}")
    print("=" * 60)
    print(f"总评: {checks['OVERALL']}")
    print("=" * 60)

    report_path = os.path.join(os.path.dirname(bpy.data.filepath), "repair_qa_report.json")
    with open(report_path, 'w') as f:
        json.dump(checks, f, indent=2, ensure_ascii=False)
    print(f"报告已保存: {report_path}")

    return checks

if __name__ == "__main__":
    run_qa()
