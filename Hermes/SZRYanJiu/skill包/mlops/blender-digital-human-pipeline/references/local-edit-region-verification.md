# Verify the anatomical region BEFORE any local geometry edit (2026-08-05 incident)

A fully QA-passed bump-flattening run (Laplace harmonic fill, all numeric gates
green, vision-confirmed) had to be rolled back entirely because the edit hit
the WRONG BODY REGION: z≈1.18–1.23 was assumed to be "chest" but was actually
upper abdomen (xiphoid/epigastric zone). The real problem bump is elsewhere,
still unlocalized.

## Why z-height alone misleads

On human-body meshes, arm span ≈ height (this model: 1.810m span vs 1.801m
height, after Z-up ground alignment). The entire front torso then occupies a
narrow z band, so a z coordinate cannot reliably distinguish chest from
abdomen — a ~2cm z error crosses anatomical regions.

## Mandatory localization protocol before local edits

1. **Landmark-relative, not absolute coordinates.** Locate the target via
   anatomical landmarks (clavicle notch, nipple line, navel, armpit, iliac
   crest) and express the edit region as an offset from them.
2. **Confirm with the user before cutting.** Show a render/screenshot with the
   candidate region marked and get explicit confirmation. Never proceed on the
   agent's own visual inference — render + vision_analyze verified "bump gone"
   twice here and still missed that the region was wrong.
3. **User GUI check is the final acceptance gate.** Numeric QA (deviation
   outside target = 0, no new non-manifold, normal flips = 0) proves the edit
   was clean, not that it was in the right place.

## Rollback discipline when an edit was misplaced

- Delete the derived blend AND its autosave sibling (`*_chestflat.blend` plus
  `*_chestflat.blend1`) — autosaves otherwise leave 79MB confusion in the
  deliverables folder.
- Verify the baseline blend is untouched (file size + mtime) and confirm with
  a directory listing before reporting the rollback.
- Record the misidentified coordinates in the work log so nobody re-targets
  the same wrong region later (z≈1.18–1.23 = abdomen on THIS model).
