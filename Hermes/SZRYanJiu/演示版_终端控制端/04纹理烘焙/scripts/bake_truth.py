# -*- coding: utf-8 -*-
"""04 真值/校验层 (bake_truth) —— 只读, 不改任何现有产物。

为什么需要: 现在诊断"黑面/脏边"只能靠 RGB 统计猜(v1-v7)。本脚本按【几何真值】逐 texel 回答:
    这个 texel 的射线有没有命中? 命中在哪(距离/命中面是否背向)? 高模真值是什么颜色?
    烘焙出来的颜色与真值差多少? 若有差 —— 是 miss / 命中错面 / 源本身暗 / UV接缝渗透?

模型(对应 Blender selected_to_active):
    texel 中心 → UV 三角形 → 重心插值 → 低模表面点 P + 平滑法线 N
    → 起点 O = P + N·cage → 沿 -N 打射线 → 高模 BVH 首个命中
    → 命中三角形 + 3D重心 → 命中面 UV 重心 → 高模 basecolor 真值色(最近邻)

输出 04纹理烘焙/输出/_truth/:
    04_truth_fill.png          有 texel 的区域(UV 覆盖)
    04_truth_validity.png      1=命中 0=miss
    04_truth_hitdist.png       命中距离(0~3×body cage 线性)
    04_truth_normalalign.png   cos(命中面法线, 低模外法线): 1=同向, <0=命中背面
    04_truth_sourcecolor.png   高模真值色(= 该 texel "正确答案")
    04_truth_attribution.png   逐 texel 归因(红miss/绿ok/橙偏暗/蓝源暗/品红命中背面)
    04_truth_report.json       分区域统计 + 归因计数 + 真值层自校(与 raw 烘焙的一致率)

env: TRUTH_REGION=all|upper (默认 upper: z>0.80×身高 = 头+颈+领口+肩带)
     TRUTH_LOG=<进度日志路径>
"""
import bpy, os, json, time, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image

D = r"E:/WangZhen_Project/AI/ShuZiRen/Hermes/SZRYanJiu/演示版_终端控制端"
UV_BLEND = os.path.join(D, "03自动UV", "输出", "03_auto_uv.blend")
HIGH_POLY = os.path.join(D, "01高模修复", "输出", "01_highpoly_repair.blend")
RAW_PNG = os.path.join(D, "04纹理烘焙", "输出", "04_diffuse_4k_raw.png")
OUT = os.path.join(D, "04纹理烘焙", "输出", "_truth")
os.makedirs(OUT, exist_ok=True)
REGION = os.environ.get("TRUTH_REGION", "upper")
LOGF = os.environ.get("TRUTH_LOG", os.path.join(D, "logs", "_04_truth.log"))
_lg = open(LOGF, "w", encoding="utf-8")
_t0 = time.time()
def P(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True); _lg.write(f"[{time.time()-_t0:6.1f}s] {s}\n"); _lg.flush()

lum = lambda a: 0.2126*np.asarray(a)[..., 0] + 0.7152*np.asarray(a)[..., 1] + 0.0722*np.asarray(a)[..., 2]

P("=== 04 真值/校验层 (bake_truth) ===")
P(f"region={REGION}  log={LOGF}")

# ---------------- 低模 + UV ----------------
bpy.ops.wm.open_mainfile(filepath=UV_BLEND)
low = None
for o in bpy.data.objects:
    if o.type == 'MESH' and '_QR' in o.name:
        low = o; break
if low is None:
    raise SystemExit("ERROR: 03 产物里找不到 _QR 低模")
lme = low.data
P(f"低模 {low.name}: 面={len(lme.polygons):,} 顶={len(lme.vertices):,}")
Ml = np.array(low.matrix_world)
NV = np.empty(len(lme.vertices)*3); lme.vertices.foreach_get("co", NV); NV = NV.reshape(-1, 3)
VW = NV @ Ml[:3, :3].T + Ml[:3, 3]
LOOPN = np.empty(len(lme.loops)*3); lme.loops.foreach_get("normal", LOOPN); LOOPN = LOOPN.reshape(-1, 3)
LW = LOOPN @ Ml[:3, :3].T
UV = np.empty(len(lme.loops)*2); lme.uv_layers.active.data.foreach_get("uv", UV); UV = UV.reshape(-1, 2)
lme.calc_loop_triangles()
LT = np.empty(len(lme.loop_triangles)*3, np.int32); lme.loop_triangles.foreach_get("loops", LT); LT = LT.reshape(-1, 3)
TP = np.empty(len(lme.loop_triangles), np.int32); lme.loop_triangles.foreach_get("polygon_index", TP)
LV = np.empty(len(lme.loops), np.int32); lme.loops.foreach_get("vertex_index", LV)
P(f"UV三角形 {len(LT):,}")

ctr = np.empty(len(lme.polygons)*3); lme.polygons.foreach_get("center", ctr); ctr = ctr.reshape(-1, 3)
CW = ctr @ Ml[:3, :3].T + Ml[:3, 3]
zmax, zmin = float(CW[:, 2].max()), float(CW[:, 2].min())
xspan = float(CW[:, 0].max() - CW[:, 0].min())
yup = float(CW[:, 1].max() - CW[:, 1].min())
H = zmax - zmin
bbox_max = max(H, xspan, yup)
if REGION == "upper":
    keep_face = CW[:, 2] > zmin + 0.80*H
else:
    keep_face = np.ones(len(lme.polygons), bool)
keep_tri = keep_face[TP]
P(f"区域 {REGION}: 面 {int(keep_face.sum()):,}/{len(keep_face):,} → 三角形 {int(keep_tri.sum()):,}")

# ---------------- 高模 + basecolor ----------------
with bpy.data.libraries.load(HIGH_POLY) as (df, dt):
    dt.objects = df.objects
hi = max([o for o in dt.objects if o is not None and o.type == 'MESH'], key=lambda o: len(o.data.vertices))
bpy.context.collection.objects.link(hi)
hme = hi.data
P(f"高模 {hi.name}: 面={len(hme.polygons):,} 材质={[m.name if m else None for m in hme.materials]}")

him = None
for mat in hme.materials:
    if not (mat and mat.use_nodes):
        continue
    for n in mat.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            inp = n.inputs.get('Base Color')
            if inp and inp.is_linked and inp.links[0].from_node.type == 'TEX_IMAGE':
                him = inp.links[0].from_node.image
if him is None:
    raise SystemExit("ERROR: 高模没有连到 Base Color 的图像")
HW_, HH_ = him.size
HITEX = np.array(him.pixels[:], dtype=np.float32).reshape(HH_, HW_, 4)[:, :, :3]
P(f"高模 basecolor {him.name} {HW_}x{HH_} 均值={HITEX.mean():.3f}")
huvl = hme.uv_layers.active
HUV = np.empty(len(hme.loops)*2); huvl.data.foreach_get("uv", HUV); HUV = HUV.reshape(-1, 2)

# ---------------- BVH ----------------
_t = time.time()
hv = np.empty(len(hme.vertices)*3); hme.vertices.foreach_get("co", hv); hv = hv.reshape(-1, 3)
Mh = np.array(hi.matrix_world); Minv = np.linalg.inv(Mh)
HVW = hv @ Mh[:3, :3].T + Mh[:3, 3]
hpolys = [list(p.vertices) for p in hme.polygons]
bvh = BVHTree.FromPolygons([tuple(v) for v in hv], hpolys)
P(f"BVH 建成 {time.time()-_t:.1f}s ({len(hpolys):,} 面)")

def hit_wuv(idx, loc):
    """命中面 → (重心权重(3,), uv(2,))。支持 n-gon: 按该面 loop 顺序扇形三角化, 取命中点所在的子三角。
    (2026-09-22 修: 原实现直接假设三角形 —— 高模里有 5 个四边形, 一旦命中就 ValueError 维度不符)"""
    vv = hpolys[idx]
    li = list(hme.polygons[idx].loop_indices)
    P_ = np.array([loc[0], loc[1], loc[2]])
    best = None
    for j in range(1, len(vv) - 1):
        A = HVW[vv[0]]; B = HVW[vv[j]]; C = HVW[vv[j + 1]]
        n0 = np.linalg.norm(np.cross(B - P_, C - P_))
        n1 = np.linalg.norm(np.cross(C - P_, A - P_))
        n2 = np.linalg.norm(np.cross(A - P_, B - P_))
        den = n0 + n1 + n2
        w = np.array([n0, n1, n2]) / den if den > 1e-20 else np.array([1.0, 0.0, 0.0])
        sc = float(w.min())
        if best is None or sc > best[0]:
            best = (sc, w, np.stack([HUV[li[0]], HUV[li[j]], HUV[li[j + 1]]]))
    _, w, uvs = best
    return w, np.array([float(np.dot(w, uvs[:, 0])), float(np.dot(w, uvs[:, 1]))])
_bvhray = bvh.ray_cast

# ---------------- 逐 texel 光栅 ----------------
RES = 4096
cage_body = bbox_max * 0.011
cage_eye = bbox_max * 0.055
P(f"cage: body={cage_body*1000:.2f}mm eye={cage_eye*1000:.2f}mm (bbox_max={bbox_max:.3f}m)")

eye_c, eye_r = [], []
for eo in [o for o in bpy.data.objects if o.type == 'MESH' and 'Eye' in o.name]:
    cs = np.empty(len(eo.data.vertices)*3); eo.data.vertices.foreach_get("co", cs)
    Mw = np.array(eo.matrix_world); cs = cs.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3]
    c = cs.mean(axis=0); eye_c.append(c); eye_r.append(float(np.abs(cs-c).max()))
is_bowl_face = np.zeros(len(lme.polygons), bool)
for c, r in zip(eye_c, eye_r):
    is_bowl_face |= (np.linalg.norm(CW - c, axis=1) < 0.95*r)
P(f"眼球 {len(eye_c)} 个; 碗区面 {int(is_bowl_face.sum())}")

tpos = np.zeros((RES, RES, 3), np.float64)
tnrm = np.zeros((RES, RES, 3), np.float64)
tbowl = np.zeros((RES, RES), bool)
tfill = np.zeros((RES, RES), bool)
_t = time.time()
for t in range(len(LT)):
    if not keep_tri[t]:
        continue
    li = LT[t]
    tri = UV[li]
    if (tri[:, 0].max() < 0) or (tri[:, 0].min() > 1) or (tri[:, 1].max() < 0) or (tri[:, 1].min() > 1):
        continue
    xs = np.clip((tri[:, 0]*RES).astype(int), 0, RES-1); ys = np.clip((tri[:, 1]*RES).astype(int), 0, RES-1)
    x0, x1 = int(xs.min()), int(xs.max()); y0, y1 = int(ys.min()), int(ys.max())
    gy, gx = np.mgrid[y0:y1+1, x0:x1+1]
    v0, v1, v2 = tri
    d = (v1[0]-v0[0])*(v2[1]-v0[1]) - (v2[0]-v0[0])*(v1[1]-v0[1])
    if abs(d) < 1e-14:
        continue
    px = (gx+0.5)/RES; py = (gy+0.5)/RES
    w1 = ((px-v0[0])*(v2[1]-v0[1]) - (py-v0[1])*(v2[0]-v0[0]))/d
    w2 = ((py-v0[1])*(v1[0]-v0[0]) - (px-v0[0])*(v1[1]-v0[1]))/d
    w0 = 1.0 - w1 - w2
    ins = (w0 >= -0.002) & (w1 >= -0.002) & (w2 >= -0.002)
    if not ins.any():
        continue
    ii = gy[ins]; jj = gx[ins]        # mgrid 已是绝对像素坐标, 不能再加 x0/y0
    a = w0[ins][:, None]; b = w1[ins][:, None]; c = w2[ins][:, None]
    tpos[ii, jj] = a*VW[LV[li[0]]] + b*VW[LV[li[1]]] + c*VW[LV[li[2]]]
    tnrm[ii, jj] = a*LW[li[0]] + b*LW[li[1]] + c*LW[li[2]]
    tfill[ii, jj] = True
    tbowl[ii, jj] = is_bowl_face[TP[t]]
P(f"光栅完成 → {int(tfill.sum()):,} texel [{time.time()-_t:.1f}s]")

iy, ix = np.nonzero(tfill)
N = len(iy)
P(f"待追踪 texel {N:,}")

# ---------------- 射线 ----------------
valid = np.zeros(N, bool)
hdist = np.zeros(N, np.float64)
halign = np.zeros(N, np.float64)
hsrccol = np.zeros((N, 3), np.float64)
# 第2/3候选命中(报告§50): 薄壳衣物/骑跨面的根因是"首个命中不是该拿的那层"
h2dist = np.full(N, np.nan); h2col = np.zeros((N, 3), np.float64)
h3dist = np.full(N, np.nan); h3col = np.zeros((N, 3), np.float64)
_t = time.time(); step = max(1, N//10)
for k in range(N):
    p = tpos[iy[k], ix[k]]; n = tnrm[iy[k], ix[k]]
    ln = math.sqrt(float(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]))
    if ln < 1e-12:
        continue
    n = n/ln
    cg = cage_eye if tbowl[iy[k], ix[k]] else cage_body
    Ol = (p + n*cg) @ Minv[:3, :3].T + Minv[:3, 3]
    Dl = (-n) @ Minv[:3, :3].T
    Dl = Dl/max(math.sqrt(float(Dl[0]**2+Dl[1]**2+Dl[2]**2)), 1e-12)
    res = _bvhray(Vector(Ol), Vector(Dl))   # 不传 distance: 默认=不限制(Blender 语义, 0.0 = 零长度!)
    if res[0] is None:
        continue
    loc, nr, idx, dist = res
    valid[k] = True; hdist[k] = dist
    vv = hpolys[idx]
    A = HVW[vv[0]]; B = HVW[vv[1]]; C = HVW[vv[2]]
    locl = np.array([loc[0], loc[1], loc[2]])
    n0 = np.linalg.norm(np.cross(B-locl, C-locl))
    n1 = np.linalg.norm(np.cross(C-locl, A-locl))
    n2 = np.linalg.norm(np.cross(A-locl, B-locl))
    den = n0+n1+n2
    w = np.array([n0, n1, n2])/den if den > 1e-20 else np.array([1.0, 0.0, 0.0])
    nn = np.array([nr[0], nr[1], nr[2]]); nn = nn/max(np.linalg.norm(nn), 1e-12)
    halign[k] = float(np.dot(nn, n))
    w, _uv1 = hit_wuv(idx, loc)      # 2026-09-22: 统一走 n-gon 安全取 UV(支持四边形)
    u = float(_uv1[0]); v = float(_uv1[1])
    hsrccol[k] = HITEX[int(np.clip(v % 1.0, 0, 1)*(HH_-1)), int(np.clip(u % 1.0, 0, 1)*(HW_-1))]
    # 继续沿同一方向找第2/3层(命中点抬高 eps 防自交)
    _cur = np.array([loc[0], loc[1], loc[2]]); _tot = dist
    for _lvl, (_dl, _cl) in enumerate(((h2dist, h2col), (h3dist, h3col)), start=2):
        _o = _cur + Dl*1e-4
        _r = _bvhray(Vector(_o), Vector(Dl))
        if _r[0] is None:
            break
        _l2, _n2, _i2, _d2 = _r
        _ww, _uv = hit_wuv(_i2, _l2)   # 2026-09-22: 同上(原实现在四边形上会 ValueError 维度不符)
        _cl[k] = HITEX[int(np.clip(_uv[1] % 1, 0, 1)*(HH_-1)), int(np.clip(_uv[0] % 1, 0, 1)*(HW_-1))]
        _tot += _d2
        _dl[k] = _tot
        _cur = np.array([_l2[0], _l2[1], _l2[2]])
    if k % step == 0:
        P(f"  追踪 {100*k//N:3d}% ({k:,}/{N:,}) [{time.time()-_t:.0f}s]")
P(f"追踪完成 {time.time()-_t:.0f}s | 命中 {int(valid.sum()):,}/{N:,} ({100*valid.mean():.1f}%)")

# ---------------- raw 烘焙对照 ----------------
raw = Image.open(RAW_PNG).convert("RGB")
if raw.size != (RES, RES):
    raw = raw.resize((RES, RES))
# ⚠行序: PIL 第0行=图像顶部(v=1); Blender image.pixels 第0行=底部(v=0) → 必须翻转才能同坐标系比对(踩过)
baked = np.asarray(raw, dtype=np.float32)[::-1]/255.0    # 翻成 Blender 行序(第0行=v0)
P(f"raw 烘焙图 {baked.shape} (已翻成 Blender 行序)")
bk = baked[iy, ix]
lu_src = lum(hsrccol); lu_bk = lum(bk)
d_lum = lu_bk - lu_src

# ---------------- 统计 ----------------
v = valid.copy()
_gap2 = h2dist - hdist
_has2 = np.isfinite(h2dist)
_thin = _has2 & (_gap2 < 0.008)          # 首命中后 8mm 内还有一层 = 薄壳衣物/骑跨
_jump = _thin & (np.abs(lum(h2col) - lum(hsrccol)) > 0.12)   # 且两层颜色明显不同
def reg(name, m):
    if int(m.sum()) == 0:
        return {}
    mm = m & v
    o = {"texels": int(m.sum()), "miss_pct": float(100*(~v[m]).mean())}
    if int(mm.sum()):
        o.update(dict(
            hitdist_mean_mm=float(hdist[mm].mean()*1000), hitdist_p95_mm=float(np.percentile(hdist[mm], 95)*1000),
            align_mean=float(halign[mm].mean()), align_backface_pct=float(100*(halign[mm] < 0).mean()),
            srclum_mean=float(lu_src[mm].mean()), srclum_p05=float(np.percentile(lu_src[mm], 5)),
            srclum_dark_pct=float(100*(lu_src[mm] < 0.25).mean()),
            bakedlum_mean=float(lu_bk[mm].mean()),
            dlum_mean=float(d_lum[mm].mean()), dlum_p05=float(np.percentile(d_lum[mm], 5)),
            dlum_abs_mean=float(np.abs(d_lum[mm]).mean()),
            frac_baked_darker_015=float(100*(d_lum[mm] < -0.15).mean()),
            frac_baked_darker_030=float(100*(d_lum[mm] < -0.30).mean()),
            frac_src_baked_close_005=float(100*(np.abs(d_lum[mm]) < 0.05).mean())))
        o.update(
            second_hit_pct=float(100*_has2[mm].mean()),
            thin_layer_pct=float(100*_thin[mm].mean()),
            thin_layer_colorjump_pct=float(100*_jump[mm].mean()),
            thin_gap2_median_mm=float(np.nanmedian(_gap2[mm & _has2])*1000) if int((mm & _has2).sum()) else None)
    return o

bowl = tbowl[iy, ix]; allm = np.ones(N, bool)
REP = {"params": dict(region=REGION, res=RES, cage_body_mm=round(cage_body*1000, 3), cage_eye_mm=round(cage_eye*1000, 3)),
       "texels_total": int(N), "texels_bowl": int(bowl.sum()),
       "all": reg("all", allm), "bowl": reg("bowl", bowl), "nonbowl": reg("nonbowl", ~bowl)}

# ---------------- 按"距眼球中心的半径"分环(可见性口径: 眼球遮住的是隐藏区) ----------------
_pts = tpos[iy, ix]
ter = np.full(N, np.inf)
for c in eye_c:
    ter = np.minimum(ter, np.linalg.norm(_pts - c, axis=1))
_reye_mm = min(eye_r)*1000 if eye_r else 0.0
RINGS = {}
for nm, a, b in (("hidden_lt13mm", 0, 13), ("ring_13-16mm", 13, 16), ("ring_16-20mm", 16, 20),
                 ("outer_20-30mm", 20, 30), ("face_gt30mm", 30, 1e9)):
    m = v & (ter*1000 >= a) & (ter*1000 < b)
    if int(m.sum()) == 0:
        continue
    RINGS[nm] = dict(texels=int(m.sum()),
                     ang_mean_deg=round(float(np.degrees(np.arccos(np.clip(halign[m], -1, 1))).mean()), 2),
                     ang_gt30_pct=round(float(100*(halign[m] < 0.866).mean()), 2),
                     backface_pct=round(float(100*(halign[m] < 0).mean()), 2),
                     hitdist_mean_mm=round(float(hdist[m].mean()*1000), 2),
                     srclum_mean=round(float(lu_src[m].mean()), 4),
                     src_dark_pct=round(float(100*(lu_src[m] < 0.25).mean()), 2))
REP["rings_by_eye_radius"] = dict(eyeball_radius_mm=round(_reye_mm, 2), rings=RINGS)
P("按眼球半径分环(可见性口径): " + json.dumps(RINGS, ensure_ascii=False))

cls = np.zeros(N, np.int8)
cls[v] = 1
cls[v & (halign < 0)] = 4
cls[valid & (d_lum < -0.15)] = 2
cls[valid & (lu_src < 0.25)] = 3
cls[valid & _jump] = 5        # 薄壳两层色跳(骑跨候选)
cnt = {int(c): int((cls == c).sum()) for c in np.unique(cls)}
REP["attribution"] = {"0_miss": cnt.get(0, 0), "1_ok": cnt.get(1, 0), "2_baked_darker_than_source": cnt.get(2, 0),
                      "3_source_itself_dark": cnt.get(3, 0), "4_hit_backface": cnt.get(4, 0),
                      "5_thin_layer_colorjump": cnt.get(5, 0)}
REP["attribution_pct"] = {k: round(100.0*x/max(1, N), 2) for k, x in REP["attribution"].items()}
# 真值层自校: 若本层射线模型与 Blender 烘焙一致, 则"命中正确"的 texel 上 烘焙色≈真值色
_okm = v & (np.abs(halign) > 0.9)
if int(_okm.sum()):
    _d = np.abs(lu_bk[_okm] - lu_src[_okm])
    REP["selfcheck"] = {"n": int(_okm.sum()),
                        "median_abs_lum_diff": float(np.median(_d)),
                        "frac_within_0.05": float(100*(_d < 0.05).mean()),
                        "frac_within_0.10": float(100*(_d < 0.10).mean()),
                        "bias_mean": float((lu_bk[_okm]-lu_src[_okm]).mean()),
                        "pearson_lum": float(np.corrcoef(lu_bk[_okm], lu_src[_okm])[0, 1])}
    P("自校(命中面同向的 texel上 烘焙 vs 高模真值): " + json.dumps(REP["selfcheck"], ensure_ascii=False))
P("归因: " + json.dumps(REP["attribution"], ensure_ascii=False))
P("占比: " + json.dumps(REP["attribution_pct"], ensure_ascii=False))
P("all : " + json.dumps(REP["all"], ensure_ascii=False))
P("bowl: " + json.dumps(REP["bowl"], ensure_ascii=False))
P("mask: " + json.dumps({k: (None if x is None else int(x)) for k, x in
                         dict(tfill=int(tfill.sum()), bowl=int(bowl.sum())).items()}, ensure_ascii=False))

# ---------------- 出图 ----------------
def out_gray(flat, path):
    a = np.zeros(RES*RES, np.float64); a[iy*RES+ix] = flat
    Image.fromarray((np.clip(a.reshape(RES, RES)[::-1], 0, 1)*255).astype(np.uint8)).save(path)   # 翻回看图行序
def out_rgb(flat, path, gain=1.0):
    a = np.zeros((RES*RES, 3)); a[iy*RES+ix] = np.clip(flat*gain, 0, 1)
    Image.fromarray((a.reshape(RES, RES, 3)[::-1]*255).astype(np.uint8)).save(path)

out_gray(tfill[iy, ix].astype(float), os.path.join(OUT, "04_truth_fill.png"))
out_gray(v.astype(float), os.path.join(OUT, "04_truth_validity.png"))
out_gray(np.clip(hdist/(cage_body*4), 0, 1), os.path.join(OUT, "04_truth_hitdist.png"))
out_gray(np.clip(halign, 0, 1), os.path.join(OUT, "04_truth_normalalign.png"))
out_rgb(hsrccol, os.path.join(OUT, "04_truth_sourcecolor.png"))
pal = np.array([[1, 0, 0], [0.15, 0.8, 0.15], [1, 0.55, 0], [0.15, 0.25, 1], [1, 0, 1], [1, 1, 0]], np.float32)
out_rgb(pal[np.clip(cls, 0, 5)], os.path.join(OUT, "04_truth_attribution.png"))
P("出图: fill/validity/hitdist/normalalign/sourcecolor/attribution")

json.dump(REP, open(os.path.join(OUT, "04_truth_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
P(f"报告 → {os.path.join(OUT, '04_truth_report.json')}")

# ---------------- 逐 texel 数据落盘(供下游判定/修复) ----------------
np.savez_compressed(os.path.join(OUT, "04_truth_texels.npz"),
                    iy=iy.astype(np.int32), ix=ix.astype(np.int32), fill=tfill[iy, ix],
                    bowl=tbowl[iy, ix], valid=valid, hdist=hdist.astype(np.float32),
                    halign=halign.astype(np.float32), srccol=hsrccol.astype(np.float32),
                    cls=cls, h2dist=h2dist.astype(np.float32), h2col=h2col.astype(np.float32),
                    eye_r_mm=(ter*1000).astype(np.float32))
P("逐texel数据 → 04_truth_texels.npz")

# ---------------- 修复效果判定: v1-v7 把像素改向真值还是改离真值 ----------------
try:
    fin = Image.open(os.path.join(D, "04纹理烘焙", "输出", "04_diffuse_4k.png")).convert("RGB")
    if fin.size != (RES, RES):
        fin = fin.resize((RES, RES))
    final = np.asarray(fin, dtype=np.float32)[::-1]/255.0
    fc = final[iy, ix]
    changed = (np.abs(fc - bk).max(axis=1) > 3.0/255.0)
    e_raw = np.abs(bk - hsrccol).mean(axis=1)
    e_fix = np.abs(fc - hsrccol).mean(axis=1)
    nch = int(changed.sum())
    VER = {"changed_texels": nch, "changed_pct": round(100.0*nch/max(1, N), 3),
           "bowl_changed": int((changed & bowl).sum())}
    if nch:
        VER.update(err_raw_on_changed=float(e_raw[changed].mean()),
                   err_fix_on_changed=float(e_fix[changed].mean()),
                   improved_pct=float(100*(e_fix[changed] < e_raw[changed]).mean()),
                   worsened_pct=float(100*(e_fix[changed] > e_raw[changed]).mean()),
                   mean_delta_err=float((e_fix[changed] - e_raw[changed]).mean()))
        P("修复判定(改动像素 vs 高模真值): " + json.dumps(
            {k: (round(v, 5) if isinstance(v, float) else v) for k, v in VER.items()}, ensure_ascii=False))
    # 全体
    VER["all_err_raw"] = float(e_raw.mean()); VER["all_err_fix"] = float(e_fix.mean())
    # 衣肤交界代理: 改动像素中"原烘焙值本来就很准(±0.03)"的比例 —— 这部分属于无谓改写
    if nch:
        VER["changed_where_raw_already_good_pct"] = float(100*(e_raw[changed] < 0.03).mean())
        VER["changed_where_raw_already_good_became_worse_pct"] = float(
            100*((e_raw[changed] > -1) & (e_raw[changed] < 0.03) & (e_fix[changed] > e_raw[changed])).mean())
    REP["fix_verdict"] = VER
    P("修复判定汇总: " + json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in VER.items()}, ensure_ascii=False))
except Exception as _e:
    P(f"修复判定跳过: {_e}")

json.dump(REP, open(os.path.join(OUT, "04_truth_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
P("TRUTH_DONE")
_lg.close()
