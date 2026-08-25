# Body Wrap Method Test Results

## Test Environment
- MetaHuman Body: 56K vertices, **14 connected components**
- Tripo high-poly: 193万面, 53% inverted normals, contains clothes
- Target: UV transfer from MetaHuman to Tripo

## Method Comparison

### 1. Shrinkwrap NEAREST_SURFACEPOINT
**Result**: ❌ FAILED  
**Metrics**:
- X span: 1.809m → 0.979m (54% compression)
- Projection quality: 1.01mm average (good)
- UV preserved: No (destroyed by large vertex movement)

**Root cause**: MetaHuman has 14 components. Shrinkwrap projects each component independently. Arms find torso's clothes surface (closer than actual arm position) → collapse.

**Why it fails**: 
- Component 0 (torso): X[-0.24,0.22] → [-0.04,0.04] (6x compression)
- Component 1-2 (right arm): X[0.71,0.90] → [0.49,0.49] (collapsed to line)
- Component 4 (left arm): X[0.14,0.72] → [0.01,0.49] (collapsed)

**Verdict**: Do NOT use.

---

### 2. Shrinkwrap PROJECT
**Result**: ⚠️ PARTIAL  
**Metrics**:
- X span: 1.809m → 1.809m (preserved)
- Y span: 0.313m → 0.313m (preserved)
- Z span: 1.800m → 1.800m (preserved)
- Projection quality: 507mm average distance (failed)
- Only 7.5% vertices actually projected to surface
- UV preserved: Yes (no large movement)

**Root cause**: PROJECT method projects along vertex normals, not towards target surface. MetaHuman normals don't align with Tripo surface → no intersection found.

**Verdict**: Preserves bbox but doesn't actually wrap.

---

### 3. Surface Deform
**Result**: ❌ FAILED  
**Metrics**:
- X span: 1.809m → 1.809m (preserved)
- Projection quality: 490mm average distance
- Only 0.3% vertices projected
- UV preserved: Yes

**Root cause**: Surface Deform modifier's `falloff` parameter has no effect. The binding fails to establish proper vertex correspondence.

**Verdict**: Does not work for this use case.

---

### 4. RBF thin_plate_spline
**Result**: ❌ FAILED  
**Metrics**:
- Used 15 bone landmarks as control points
- X span: 1.809m → 1.878m
- Y span: 0.313m → 1.324m (4x expansion!)
- Z span: 1.800m → 1.904m
- Visual: Head deformed to ellipse, feet elongated

**Root cause**: 15 control points too sparse for 56K vertices. RBF interpolates between sparse points → uncontrolled deformation in between.

**Verdict**: Do NOT use for body wrap.

---

### 5. Affine Transformation (least squares)
**Result**: ❌ FAILED  
**Metrics**:
- Linear matrix diagonal: [1.29, 1.02, 0.95] (reasonable)
- But off-diagonal elements: up to 3.72 (rotation mixed in)
- X span: 1.809m → 1.957m
- Y span: 0.313m → 1.402m (4.5x expansion!)
- Z span: 1.800m → 1.972m

**Root cause**: Least squares solver minimizes error by mixing rotation into the transformation matrix. Non-diagonal elements become large → distortion.

**Verdict**: Do NOT use affine transformation for wrap.

---

### 6. Per-Component Shrinkwrap
**Result**: ❌ FAILED  
**Metrics**:
- Split into 14 separate objects
- Each object Shrinkwrap independently
- X span: 1.809m → 0.979m (same collapse as method 1)
- All 14 components still collapsed

**Root cause**: Clothes inner surface problem not solved by splitting. Each component still finds clothes surface as nearest.

**Verdict**: Splitting doesn't help.

---

### 7. Pure Scaling + Translation ✅
**Result**: SUCCESS  
**Metrics**:
- Scale factors: sx=0.946, sy=0.889, sz=0.997
- X span: 1.809m → 1.809m (100% match)
- Y span: 0.313m → 0.313m (100% match)
- Z span: 1.800m → 1.800m (100% match)
- UV preserved: Yes (0.0 difference)
- No distortion

**Implementation**:
```python
sx = tripo_xspan / mh_xspan
sy = tripo_yspan / mh_yspan
sz = tripo_zspan / mh_zspan
for v in obj.data.vertices:
    v.co.x = (v.co.x - mh_center.x) * sx + tripo_center.x
    v.co.y = (v.co.y - mh_center.y) * sy + tripo_center.y
    v.co.z = (v.co.z - mh_center.z) * sz + tripo_center.z
```

**Verdict**: **ONLY successful method**. Preserves UV, matches bbox, no distortion.

---

## Conclusion

**Only pure scaling + translation works** for body wrap in this scenario.

**Why other methods fail**:
1. **Clothes interference**: Tripo contains clothes, inner surface 5-20mm from body
2. **14 components**: MetaHuman Body is not a single mesh
3. **Sparse control points**: 15 landmarks insufficient for 56K vertices
4. **Algorithm limitations**: Shrinkwrap/Surface Deform/RBF all have fundamental issues with this geometry

**Final verdict (2026-07-29)**: ❌ Body wrap ABANDONED. All 9 methods failed due to structural clothing nesting + 53.1% inverted normals. User moved to QR + external expert consultation. The only "successful" method (scale+translate) was rejected by user because it doesn't preserve surface detail — 拓扑目的是降面数+保细节，不是BBox对齐。

**Detailed failure archive**: `方案md记录/v1_MetaHumanWrap/Body_Wrap方案失败记录.md`
