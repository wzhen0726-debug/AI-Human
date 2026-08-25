# Demo blend addendum — viewport framing + CJK text hints

Addendum to `demo-blend-for-laypeople.md` (2026-08-21 session; written separately because the
original file's write-gate deduped; merge content together when convenient).

## Frame the view on the target (5th must-set)

A layperson cannot find a small object in a scene. Open the view ALREADY framed on the part:
```python
rv = space.region_3d
rv.view_location = Vector(target_center)   # e.g. midpoint between both eyes
rv.view_distance = 0.082                   # meters; tight framing
rv.view_perspective = 'ORTHO'
```
Set it on EVERY VIEW_3D area (both halves after the split). Start tight on the feature, then
expect feedback like "视野再全一点" — this user wanted ~35% more room than the initial tight
framing (6cm → 8.2cm view_distance). Keep the object centered; only widen distance.

## In-scene text hints: the CJK font trap

Blender's default font has NO CJK glyphs — Chinese text objects silently render as nothing or
boxes, and the user just reports "没看到文字牌" (can't see the hint). Root cause is the font,
not position. Fix:
```python
f = bpy.data.fonts.load(r"C:\Windows\Fonts\msyh.ttc")   # Microsoft YaHei, ships with Windows
cu.font = f; cu.font_bold = f
```
Additional rules:
- Place the text object INSIDE the ortho viewport bounds: ORTHO shows ±view_distance/2 in height;
  check the offset against that before trusting it's visible.
- `cu.size` ~5mm for an 8cm framing; multi-line (`\n`), `align_x='CENTER'`.
- Emission material (Emission Strength ~3, yellow) so it reads over the model.
- Rotate to face the viewer: this project's face looks -Y → `rotation_euler=(radians(90),0,0)`.
- Verify visibility yourself (render a viewport screenshot or reason geometrically) before
  handing over.

## Viewport state verification

After saving, re-open headless and read back BOTH viewports: shading type (expect MATERIAL),
view_distance, view_location, view_rotation quaternion. All four persist in the workspace.
