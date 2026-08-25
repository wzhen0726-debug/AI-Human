-- RizomUV 2025.0 Headless UV Unwrap Script
-- Usage: cd "D:/Program Files/Rizom Lab/RizomUV 2025.0" && ./rizomuv.exe /cfi "<this_file>" /nu /nle
--
-- Prerequisites:
--   1. Blender exported FBX with seams marked (bmesh edge.seam=True)
--   2. RizomUV must run from its install directory (ForcePython.usda dependency)
--
-- Replace <FBX_IN> and <FBX_OUT> with absolute paths before running.

ZomLoad({File={Path="<FBX_IN>", ImportGroups=true, XYZUVW=true, UVWProps=true}})
ZomSet({Path="Prefs.FileSuffix", Value=""})
ZomUnfold({PrimType="Polygon", WorkingSet="All"})
ZomOptimize({Iterations=3})
ZomSave({File={Path="<FBX_OUT>"}})
ZomQuit()
