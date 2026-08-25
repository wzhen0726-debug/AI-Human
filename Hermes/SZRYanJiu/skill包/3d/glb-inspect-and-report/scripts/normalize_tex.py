"""Normalize freely-named vendor textures in a curated texture library into the
pipeline-standard maps {key}_Color.jpg / _NormalGL.jpg / _Roughness.jpg / _Metallic.jpg.

Why: users drop Poliigon / GSG / custom-named maps into folders; the GLB pipeline
only reads the standard names. Run this after every texture refill, before export.

- Color      <- basecolor | base_color | albedo | diffuse | diff. | _d. | _col
- NormalGL   <- normal | _n. | _nrm        (Poliigon/GSG = OpenGL green-up; copied as-is, NOT flipped)
- Roughness  <- roughness | _r. | _rough   OR extracted from _ARM (G channel)
- Metallic   <- metallic | metalness | _m.  OR extracted from _ARM (B channel)   [v2: now USED, not ignored]
- Everything is resized to <=2048 on the long edge and saved JPEG q87.

Metallic rule (user-required 2026-08-08): if a Metallic map exists it MUST be
emitted — the pipeline wires it into the Principled Metallic input. Only materials
whose texture set has no Metallic map fall back to a scalar metallicFactor.

Usage:
    python normalize_tex.py "E:\\path\\to\\贴图素材库" key1 key2 ...
If no keys are given, every folder whose standard Color.jpg is missing is processed.
A file already named `{key}_*.jpg` is treated as a normalized product and skipped,
so re-running after a refill only picks up the newly-dropped vendor files.
"""
import os, sys
from PIL import Image

MAXSZ = 2048

def classify(fn, key):
    f = fn.lower()
    if fn.startswith(f'{key}_') and fn.endswith('.jpg'):  # already a normalized product
        return 'SKIP'
    if fn.startswith('_'):
        return 'SKIP'
    if 'metallic' in f or 'metalness' in f: return 'Metallic'
    if 'arm' in f:                            return 'ARM'
    if 'roughness' in f or '_r.' in f or '_rough' in f: return 'Roughness'
    if 'normalgl' in f or 'normal' in f or '_n.' in f or '_nrm' in f: return 'Normal'
    if any(s in f for s in ('basecolor','base_color','albedo','diffuse','diff.','_d.','_col')): return 'Color'
    if 'ambientocclusion' in f or '_ao.' in f: return 'AO'
    return None

def find_folder(root, key):
    """Match folder `{key}_{中文名}` by ASCII part before the first CJK char.
    Never prefix-match: keys may contain underscores (steel vs steel_big)."""
    for d in os.listdir(root):
        fp = os.path.join(root, d)
        if not os.path.isdir(fp):
            continue
        ci = next((i for i, ch in enumerate(d) if ord(ch) >= 0x4E00), -1)
        if ci > 0 and d[:ci].rstrip('_') == key:
            return fp
    return None

def resize(im):
    w, h = im.size
    if max(w, h) <= MAXSZ:
        return im
    r = MAXSZ / max(w, h)
    return im.resize((max(1, int(w*r)), max(1, int(h*r))), Image.LANCZOS)

def process(root, key):
    folder = find_folder(root, key)
    if not folder:
        print(f'[{key}] folder missing'); return False
    chan = {}
    for fn in sorted(os.listdir(folder)):
        fp = os.path.join(folder, fn)
        if not os.path.isfile(fp):
            continue
        c = classify(fn, key)
        if c and c != 'SKIP' and c not in chan:
            chan[c] = fp
    if 'Color' not in chan:
        return False  # empty / 待填充 folder
    out = {'Color': resize(Image.open(chan['Color']).convert('RGB'))}
    if 'Normal' in chan:
        out['NormalGL'] = resize(Image.open(chan['Normal']).convert('RGB'))
    if 'Roughness' in chan:
        out['Roughness'] = resize(Image.open(chan['Roughness']).convert('L'))
    if 'Metallic' in chan:
        out['Metallic'] = resize(Image.open(chan['Metallic']).convert('L'))
    if 'ARM' in chan:  # packed AO=R, Roughness=G, Metallic=B — fill whichever is missing
        arm = Image.open(chan['ARM']).convert('RGB')
        if 'Roughness' not in out:
            out['Roughness'] = resize(arm.split()[1])
        if 'Metallic' not in out:
            out['Metallic'] = resize(arm.split()[2])
    for suf, im in out.items():
        im.save(os.path.join(folder, f'{key}_{suf}.jpg'), 'JPEG', quality=87)
    flags = ''.join(s[0] for s in ('Color','NormalGL','Roughness','Metallic') if s in out)
    print(f'[{key:<14}] {flags:<6} src={sorted(chan)}')
    return True

if __name__ == '__main__':
    root = sys.argv[1]
    keys = list(sys.argv[2:])
    if not keys:
        for d in sorted(os.listdir(root)):
            fp = os.path.join(root, d)
            if not os.path.isdir(fp):
                continue
            ci = next((i for i, ch in enumerate(d) if ord(ch) >= 0x4E00), -1)
            if ci <= 0:
                continue
            key = d[:ci].rstrip('_')
            if not os.path.exists(os.path.join(fp, f'{key}_Color.jpg')):
                keys.append(key)
    for k in keys:
        process(root, k)
    print('完成')
