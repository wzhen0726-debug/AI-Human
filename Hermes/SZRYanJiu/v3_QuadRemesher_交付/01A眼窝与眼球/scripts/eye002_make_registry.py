"""眼睛模型002贴图整理: 扫描Textures目录生成颜色注册表eye002_colors.json.
颜色贴图: Eye_<Color>[_Bld1|_Bld2]_D.tga (7色系×血丝等级)
辅助贴图: Eye_A(AO)/Eye_BM/Eye_H(高度)/Eye_N(法线) — 不随颜色切换."""
import os, re, json

TEX_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\原始模型\Metahuman低模\眼睛模型002\Textures"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eye002_colors.json")

pat = re.compile(r"^Eye_(Blue|Brown|Green|Hazel|Red|Violet|Zombie)(_Bld1|_Bld2)?_D\.tga$")
aux = {}
colors = {}
for f in sorted(os.listdir(TEX_DIR)):
    full = os.path.join(TEX_DIR, f)
    m = pat.match(f)
    if m:
        color, bld = m.group(1), (m.group(2) or "").lstrip("_")
        variant = bld if bld else "base"
        colors.setdefault(color, {})[variant] = full
    elif f.startswith("Eye_") and f.endswith(".tga"):
        aux[f] = os.path.getsize(full)
    else:
        print(f"  跳过非tga: {f}")

reg = {"tex_dir": TEX_DIR, "colors": colors,
       "aux_maps": {k: f"{v/1048576:.1f}MB" for k, v in aux.items()},
       "note": "base=无血丝, Bld1/Bld2=血丝递增; Zombie只有base"}
json.dump(reg, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"颜色数: {len(colors)}")
for c, vs in colors.items():
    print(f"  {c:8} {sorted(vs.keys())}")
print(f"辅助贴图: {list(aux.keys())}")
print(f"注册表: {OUT}")
