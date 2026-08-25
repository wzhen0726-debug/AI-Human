"""Inspect GLB materials with fingerprint-based dedup.

Drops into any project, edit FOLDER / GLOB below, run with system python.
Prints per-file: every material slot with name/baseColor/metallic/roughness/tri-count,
then groups by fingerprint to expose TRUE material count.

Why fingerprint (name, baseColorFactor, metallic, roughness) and not name:
Revit exports one entry per unique fingerprint, so same name → many distinct
materials (color-coded MEP systems), and same color → many names (white paint
on metal_alu/plaster/unknown). See references/revit-glb-quirks.md §0.
"""
import json, struct, os, glob
from collections import defaultdict

FOLDER = r'E:\WangZhen_Project\20260807_GD\原始glb\assembled_nomerge'
GLOB = '2_发射机房*.glb'   # edit per batch

def parse_glb(path):
    with open(path, 'rb') as f:
        magic, version, length = struct.unpack('<4sII', f.read(12))
        assert magic == b'glTF'
        chunk_len, chunk_type = struct.unpack('<II', f.read(8))
        assert chunk_type == 0x4E4F534A  # 'JSON'
        gltf = json.loads(f.read(chunk_len))
        bin_data = b''
        if f.tell() < length:
            bin_len, bin_type = struct.unpack('<II', f.read(8))
            if bin_type == 0x004E4942:  # 'BIN\0'
                bin_data = f.read(bin_len)
    return gltf, bin_data

def material_face_count(gltf):
    """Sum triangle counts per material index across all meshes/primitives."""
    mat_tris = defaultdict(int)
    for mesh in gltf.get('meshes', []):
        for prim in mesh.get('primitives', []):
            mat_idx = prim.get('material')
            if mat_idx is None:
                continue
            if 'indices' in prim:
                tri_count = gltf['accessors'][prim['indices']]['count'] // 3
            else:
                tri_count = gltf['accessors'][prim['attributes']['POSITION']]['count'] // 3
            mat_tris[mat_idx] += tri_count
    return mat_tris

def fmt_color(c):
    if not c:
        return '#FFFFFFFF'
    return '#{:02X}{:02X}{:02X}{:02X}'.format(
        int(c[0]*255), int(c[1]*255), int(c[2]*255), int(c[3]*255))

def fingerprint(mat):
    pbr = mat.get('pbrMetallicRoughness', {})
    base = tuple(round(x, 4) for x in pbr.get('baseColorFactor', [1,1,1,1]))
    met  = round(pbr.get('metallicFactor', 1.0), 4)
    rough= round(pbr.get('roughnessFactor', 1.0), 4)
    return (base, met, rough)

def inspect(path):
    gltf, _ = parse_glb(path)
    mat_tris = material_face_count(gltf)
    mats = gltf.get('materials', [])
    fp_groups = defaultdict(list)
    for i, m in enumerate(mats):
        fp_groups[fingerprint(m)].append(i)
    print(f'\n{"="*88}\n  {os.path.basename(path)}\n{"="*88}')
    print(f'slots={len(mats)}  unique_names={len(set(m.get("name","") for m in mats))}  unique_fingerprints={len(fp_groups)}\n')
    for i, m in enumerate(mats):
        base, met, rough = fingerprint(m)
        tris = mat_tris.get(i, 0)
        print(f'  [{i:3d}] {m.get("name","?"):<22} tris={tris:>9,}  base={fmt_color(base)}  met={met}  rough={rough}')
    print(f'\n  --- fingerprint groups ---')
    for fp, idxs in sorted(fp_groups.items(), key=lambda x: -sum(mat_tris.get(i,0) for i in x[1])):
        base, met, rough = fp
        names = sorted(set(mats[i].get('name','?') for i in idxs))
        total_tris = sum(mat_tris.get(i,0) for i in idxs)
        print(f'  {fmt_color(base)} met={met} rough={rough}  → {len(idxs)} slots / {total_tris:,} tris / names={names}')

if __name__ == '__main__':
    for p in sorted(glob.glob(os.path.join(FOLDER, GLOB))):
        inspect(p)
