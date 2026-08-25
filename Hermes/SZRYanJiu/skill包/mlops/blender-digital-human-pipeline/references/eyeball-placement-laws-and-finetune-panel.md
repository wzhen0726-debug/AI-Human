# Eyeball placement laws + semi-auto finetune panel (01A eyeball v4)

## The core technique: reverse-engineer placement LAWS from the user's GUI manual adjustment

When the user says a placement is wrong and hand-adjusts it in the Blender GUI, do NOT guess
a new value and re-render. Instead:

1. **Backup the user's manual version** (`cp placed.blend placed_用户手动调整版.blend`) — the pipeline re-run will overwrite it otherwise.
2. **Quantitatively diff** user position vs script-computed position (location, rotation, scale).
   Script pattern: open the blend, read `obj.location`, compare against the formula's output,
   print deltas in mm per axis. Also check rotation/scale to confirm pure translation.
3. **Translate deltas into anatomical CONDITIONS, not absolute values.** Absolute mm only hold for
   the current model; the condition holds across models. Example deltas → laws:
   - user pulled eye forward 1.57mm from "cornea 1.5mm behind rim plane" → **law: cornea apex
     coplanar with eyelid opening plane** (protrusion ≈ 0)
   - user raised eye 1.71mm → **law: iris bottom edge rests on the lower eyelid margin**
     (upper lid then naturally covers ~1.5mm of iris top = the "upper lid wraps iris, lower lid
     shows full iris" aesthetic)
   - user didn't move x → x = contour center is correct; both eyes share identical y/z deltas → sync rule
4. **Encode the laws as config** (mm knobs with plain-language comments: too bulgy → decrease),
   re-run the pipeline, and **verify the computed result exactly reproduces the user's manual
   position** (all coordinates match to 0.1mm). Exact reproduction proves the law is right;
   anything else means you fitted noise.

Key insight: the law anchors must be **auto-measurable** so model swaps need no hand parameters:
eyelid opening plane y (from user-marked rim contour), cornea-apex distance from sphere center
(`min(v.y)` in local space when origin=center and face looks -Y), iris radius.

## Measuring pitfalls hit here

- Iris mesh disc (13.2mm for MetaHuman eye002) ≠ visible iris in texture (limbus rim is
  semi-transparent, visible iris ~1mm smaller). Geometry-only solutions overestimate coverage;
  always verify with a rendered front view.
- When iris diameter > eye opening height (13.2 > 12.2mm), "iris bottom touches lower lid" puts
  the iris center ABOVE opening center (+0.5mm base). Do not assume "move down". Draw/solve the
  geometry and check direction before committing (v3c got the sign wrong and wasted a round).
- BFS from cornea apex to find the iris patch leaks onto sclera (29mm wrong diameter). Use
  boundary edges of the source `Eye_Iris` object instead (edges with 1 linked face).
- Texture radial-profile analysis for iris radius fails on MetaHuman textures (no clean
  saturation drop). Skip it; mesh geometry + render verification is enough.

## Semi-auto finetune panel (the fallback when full-auto can't reach aesthetic precision)

Same pattern as eye-socket rim markers: script computes the anatomical default; user fine-tunes
in GUI; the result is saved back into the pipeline so re-runs reproduce it.

- Blender N-panel addon (`eye_position_panel_addon.py` style): sliders 前后/上下/左右 in mm,
  **both eyes moved with the same offset (stays synced)**, buttons: read current position /
  apply / reset to default / **save to pipeline**.
- "Save to pipeline" writes slider offsets to a JSON override file
  (`eyeball_finetune_manual.json`); the placement script loads it and applies on top of the
  anatomical default. Deleting the file returns to pure law-based defaults.
- Sliders are OFFSETS relative to the law-computed default, never absolute positions — this keeps
  the override meaningful after model swaps (only the aesthetic residual is stored).
- Install as resident addon: copy to `%APPDATA%/Blender Foundation/Blender/<ver>/scripts/addons/<name>/__init__.py`
  + any JSON it reads, then enable headless:
  `blender -b --python-expr "import bpy; bpy.ops.preferences.addon_enable(module='<name>'); bpy.ops.wm.save_userpref()"`.
  Verify with `bpy.context.preferences.addons` + `hasattr(bpy.types, '<PT_Class>')` in a fresh `-b` run.

## Verification rendering rules (learned the hard way)

- Lights must be positioned RELATIVE to the face/eye center. Absolute coords (e.g. z=0.5 while
  eyes are at z≈1.67) produce misleading up-lit renders.
- Frame both eyes fully: 50mm lens at ~25cm for front, resolution ≥1000x800. An 85mm close-up at
  30cm crops the eyes to frame edges and makes vision QA useless.
- Vision QA on a render is only valid AFTER camera/lights are known-correct; otherwise you debug
  the model for a camera bug (one full wasted round here).
- Area light energies ~40/15/20 (key/fill/rim) — high values overexpose and mislead vision.

## Process lesson

Letting the user adjust in the GUI once and reverse-engineering the laws is faster than
render-guess loops against aesthetic preferences, and it produces transferable rules for future
models. Always ask for the GUI adjustment when vision-verified parameters still get rejected.
