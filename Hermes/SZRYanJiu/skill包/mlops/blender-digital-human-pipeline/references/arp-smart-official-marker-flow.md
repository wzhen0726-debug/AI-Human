# ARP Smart official marker flow (2026-08-27)

Context: 1.80m model matches ARP template height. The official AI flow
(guess_markers → user fine-tune → go_detect) is the RIGHT approach for
standard-height models. Do NOT bypass ARP and hand-build a rig.

## Marker naming (hard requirement)
`go_detect` only reads objects with fixed names:
`root_loc, chin_loc, neck_loc, shoulder_loc, hand_loc, foot_loc`
(+ optional `thigh_loc, knee_loc, elbow_loc, hand_tip_loc`) and `_sym`
variants for the opposite side. Custom names (e.g. `01_骨盆中心`) are
silently ignored → the rig never sees the user's points.

## AI keypoints are usable
AI files live at `C:\Users\Liyunzhong\Documents\AutoRigPro\AI\inference\`
(inference_front/side/fingers exe + front_model.pth + fingers_model.pth).
With correct screenshots, guess_markers keypoints are close to user-placed
points: wrist ~2cm, knee ~4cm, shoulder ~5cm, neck z ~0mm. go_detect
produces 339 bones incl. 128 finger bones — ARP auto-rigs hands.

## Screenshot-patch pitfalls (headless; ALL THREE required)
1. Do NOT rename the user's body object to `body_temp` — ARP's
   get_selected_objects creates its OWN `body_temp` copy; the name
   collision makes the screenshot patch grab the original model WITH its
   black-clothing textures → AI sees a colored model, detects nothing
   (keypoints all land in image corners). The gray emission material must
   be applied to ARP's copy, not the original.
2. Render resolution MUST be 256×256: `_set_markers_from_keypoints`
   converts pixels with `ratio = world_dim / 256`. A 512 render doubles
   every coordinate.
3. The patched `_screenshot_char` must write geometry back onto `self`:
   `self.larger_dim/larger_dimy/larger_dimtop`, `self.midx/midy/midz`,
   `self.margin` — otherwise all markers land at (0,0,0) and the
   arm-angle calc crashes with zero-length vectors.
Also set margin=1.35 (default 1.05 clips fingertips at image edges →
hand/elbow keypoints fail).

## Pre-populated template flow
Instead of asking the user to place from zero: run guess_markers once →
dump the `_loc` world positions → bake them into a template blend (ball
meshes with show_in_front=True, orange main + yellow `_sym`, front ortho
viewport, short tip card — same conventions as the 01A eyelid markers).
User only fine-tunes, then Ctrl+S.

## Unresolved (2026-08-27)
Headless `go_detect` on the pre-populated template runs and generates the
full rig (339 bones, 128 finger bones), but marker positions are not
respected (one marker read as NoneType → wrist off 33cm, ankle off 10cm).
Root cause not found. DO NOT present the template→build flow as verified
until go_detect position fidelity is proven.

## Corrected old conclusion
The 2026-07-17 "abandon ARP" note applies ONLY to models far from ~1.8m
(the 0.976m case). For the 1.80m model the official flow works — earlier
sessions wrongly used that note to justify bypassing ARP's AI and
hand-building skeletons; the user called this out explicitly.
