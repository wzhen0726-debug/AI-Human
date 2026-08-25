"""共享数据：解析 GLB 材质，供 xlsx/docx/md 生成器使用。
复制到目标项目的 scripts/ 下，按需修改 classify() 和 FOLDER/OUT_DIR。
"""
import json, struct, glob, os
from collections import OrderedDict

def glb_material_names(path):
    """读 GLB JSON chunk 的 materials 数组，返回名字列表（含重复）。"""
    with open(path, 'rb') as f:
        magic, version, length = struct.unpack('<4sII', f.read(12))
        if magic != b'glTF': return None
        chunk_len, chunk_type = struct.unpack('<II', f.read(8))
        if chunk_type != 0x4E4F534A: return None
        data = json.loads(f.read(chunk_len))
    return [m.get('name', f'(unnamed_{i})') for i, m in enumerate(data.get('materials', []))]

def glb_material_face_counts(path):
    """按材质索引聚合面数。返回 {mat_name: tri_count}。tris=indices_count/3。"""
    with open(path, 'rb') as f:
        magic, version, length = struct.unpack('<4sII', f.read(12))
        chunk_len, chunk_type = struct.unpack('<II', f.read(8))
        data = json.loads(f.read(chunk_len))
    mats = data.get('materials', [])
    accessors = data.get('accessors', [])
    counts = {}
    for mesh in data.get('meshes', []):
        for prim in mesh.get('primitives', []):
            mi = prim.get('material')
            name = mats[mi].get('name', f'mat_{mi}') if mi is not None else '(no_material)'
            idx = prim.get('indices')
            tris = (accessors[idx]['count'] // 3) if idx is not None else (accessors[prim['attributes']['POSITION']]['count'] // 3)
            counts[name] = counts.get(name, 0) + tris
    return counts

def classify(name):
    """按文件名前缀分类 —— 每个项目都要改。返回 (类别名, 排序权重)。"""
    if name.startswith('1_'):
        if '_幕墙' in name: return ('发射塔楼 — 幕墙', 1)
        if '_建筑' in name: return ('发射塔楼 — 建筑', 2)
        if '_钢构' in name: return ('发射塔楼 — 钢构', 3)
        return ('发射塔楼 — 机电', 4)
    if name.startswith('2_'): return ('发射机房', 5)
    if name.startswith('3_'): return ('配电机房', 6)
    return ('其他', 99)

def collect(folder, strip_suffix='.rvt.glb'):
    """扫描 folder 下所有 .glb，按 classify() 分组。
    返回 OrderedDict[类别 → [(name, slot_count, unique_count, unique_names_list), ...]]
    """
    files = sorted(glob.glob(os.path.join(folder, '*.glb')))
    rows = []
    for p in files:
        base = os.path.basename(p)
        name = base.replace(strip_suffix, '').replace('.glb', '')
        mats = glb_material_names(p)
        if mats is None: continue
        uniq = sorted(set(mats))
        cat, order = classify(base)
        rows.append((cat, order, name, len(mats), len(uniq), uniq))
    groups = OrderedDict()
    for cat, order, name, total, ucnt, uniq in sorted(rows, key=lambda r: (r[1], r[2])):
        groups.setdefault(cat, []).append((name, total, ucnt, uniq))
    return groups

FOLDER = r'.\原始glb\assembled_nomerge'   # 改这里
OUT_DIR = r'.'
