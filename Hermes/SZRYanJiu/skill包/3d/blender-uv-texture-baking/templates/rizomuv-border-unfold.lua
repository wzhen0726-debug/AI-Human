-- RizomUV Headless LUA Script (NOT RECOMMENDED — produces projection, not LSCM/ARAP)
-- VERIFIED 2026-07-22: ZomUnfold in /cfi + /nu + /nle headless mode ALWAYS does
-- orthogonal projection, not LSCM/ARAP unfolding — regardless of IslandGroups,
-- NormalizeUVW, Border+Cut, or Iterations. Final confirmed score: 4.5/10.
-- An earlier "7.0/10" claim was a false positive from a UV import bug.
-- Use Blender ZEN UV (8.25/10) or ANGLE_BASED+average (8.5/10) instead.
-- Kept for reference and future testing if RizomUV fixes headless Unfold.
-- RUN FROM: cd "D:\Program Files\Rizom Lab\RizomUV 2025.0" && rizomuv.exe /cfi this_script.lua /nu /nle

ZomLoad({File={Path="<FBX_IN>", ImportGroups=true, XYZUVW=true, UVWProps=true}})
ZomSet({Path="Prefs.FileSuffix", Value=""})
ZomSelect({PrimType="Edge", Border=true, ResetBefore=true})
ZomCut({PrimType="Edge", WorkingSet="Selected"})
ZomIslandGroups({Mode="CreateFromCuts"})
ZomUnfold({PrimType="Polygon", WorkingSet="All"})
ZomOptimize({Iterations=20})
ZomSave({File={Path="<FBX_OUT>"}})
ZomQuit()
