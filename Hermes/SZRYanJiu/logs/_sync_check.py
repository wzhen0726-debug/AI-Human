import os, hashlib, sys

BASE = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu"

def files(d, pats=(".py", ".md", ".json")):
    out = {}
    if not os.path.isdir(d):
        return out
    for root, dirs, fs in os.walk(d):
        for f in fs:
            if f.endswith(pats):
                p = os.path.join(root, f)
                rel = os.path.relpath(p, d)
                out[rel] = hashlib.md5(open(p, "rb").read()).hexdigest()[:8]
    return out

pairs = [
    ("01高模修复", "v3_QuadRemesher_交付/01高模修复与黏连检测", "演示版_终端控制端/01高模修复"),
    ("01a眼窝", "v3_QuadRemesher_交付/01A眼窝与眼球", "演示版_终端控制端/01a眼窝眼球"),
    ("02拓扑", "v3_QuadRemesher_交付/02QuadRemesher拓扑", "演示版_终端控制端/02QR拓扑"),
    ("03UV", "v3_QuadRemesher_交付/03自动UV", "演示版_终端控制端/03自动UV"),
    ("03UV_rim", "v3_QuadRemesher_交付/03自动UV_rim_bevel", "演示版_终端控制端/03自动UV"),
    ("04烘焙", "v3_QuadRemesher_交付/04纹理烘焙", "演示版_终端控制端/04纹理烘焙"),
    ("05绑定", "v3_QuadRemesher_交付/05骨骼绑定", "演示版_终端控制端/05骨骼绑定"),
    ("06GLB", "v3_QuadRemesher_交付/06GLB导出", "演示版_终端控制端/06GLB导出"),
]
for label, dv, dm in pairs:
    dv = os.path.join(BASE, dv.replace("/", os.sep))
    dm = os.path.join(BASE, dm.replace("/", os.sep))
    fv, fm = files(dv), files(dm)
    sv, sm = set(fv), set(fm)
    both = sv.intersection(sm)
    same = [k for k in sorted(both) if fv[k] == fm[k]]
    diff = [k for k in sorted(both) if fv[k] != fm[k]]
    onlyv = sorted(sv - sm)
    onlym = sorted(sm - sv)
    print(f"\n### {label}  交付={len(sv)}个 演示={len(sm)}个")
    if same:
        print(f"  相同 {len(same)}: " + ", ".join(same[:6]) + (" ..." if len(same) > 6 else ""))
    if diff:
        print(f"  *内容不同 {len(diff)}: " + ", ".join(diff[:14]))
    if onlyv:
        print(f"  仅交付有 {len(onlyv)}: " + ", ".join(onlyv[:12]))
    if onlym:
        print(f"  仅演示有 {len(onlym)}: " + ", ".join(onlym[:12]))
