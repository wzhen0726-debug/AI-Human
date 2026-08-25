-- RizomUV 2025.0 headless auto-unwrap LUA script
-- VERIFIED 2026-07-22: NormalizeUVW=true + SharpEdges(1°) + Cut + Unfold
-- Run from RizomUV install dir: rizomuv.exe /cfi this_script.lua /nu /nle
-- Replace <FBX_IN> and <FBX_OUT> with absolute paths (use forward slashes)

ZomLoad({File={Path="<FBX_IN>", ImportGroups=true, XYZ=true}, NormalizeUVW=true})
ZomSet({Path="Prefs.FileSuffix", Value=""})

-- Step 1: Select all polygons
ZomSelect({All=true, PrimType="Polygon", ResetBefore=true})

-- Step 2: Auto-detect sharp edges (1° threshold catches ALL normal differences)
-- NOTE: Auto.Skeleton does NOT work on QR uniform quad meshes (no skeleton found)
--       SharpEdges.AngleMin=1.0 is the working alternative
ZomSelect({Auto={SharpEdges={AngleMin=1.0}}, PrimType="Edge", WorkingSet="All"})

-- Step 3: Cut along selected edges
ZomCut({PrimType="Edge", WorkingSet="Selected"})

-- Step 4: Unfold all polygons
ZomUnfold({PrimType="Polygon", WorkingSet="All"})

-- Step 5: Optimize (reduce distortion)
ZomOptimize({Iterations=3})

-- Step 6: Save (FBX format preserves UV data)
ZomSave({File={Path="<FBX_OUT>"}})

-- Step 7: Quit (required to exit headless mode)
ZomQuit()

-- POST-PROCESSING IN BLENDER:
-- 1. Import <FBX_OUT> into Blender
-- 2. Copy UV from imported mesh to retopo mesh via foreach_get/foreach_set
-- 3. bpy.ops.uv.average_islands_scale()
-- 4. bpy.ops.uv.pack_islands(rotate=True, margin=0.02)
-- 5. Normalize to [0.02, 0.98] for 2% margin
