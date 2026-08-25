# Headless Blender: avoiding system lag on the user's machine

## Symptom
User reports the whole machine stutters for a few seconds (mouse drags lag) while the agent runs background Blender work. This is transient CPU/GPU/disk spike, NOT sustained exhaustion.

## Root causes (this user's machine)
- EEVEE renders recompile shaders on every launch → CPU spike + GPU contention with display output (mouse lag).
- Loading/saving 1.6GB .blend files on **E drive = HDD** (system disk is NVMe SSD) → disk I/O spike.
- Multiple Blender tasks running in parallel stack the spikes.

## Rules
1. **Lower priority**: spawn background blender.exe with `subprocess.Popen(..., creationflags=0x00004000)` (BELOW_NORMAL_PRIORITY_CLASS), or set via psutil after spawn. Never let it compete with the user's foreground work.
2. **One heavy task at a time** — serialize Blender runs, never render in parallel.
3. **Verification screenshots: use BLENDER_WORKBENCH** (`scene.render.engine='BLENDER_WORKBENCH'`), not EEVEE — no shader compile, much lighter.
4. **Before killing any blender.exe/python.exe residual, identify ownership**: print cmdline + start time via psutil. The user's own GUI session opens files without `-b` and may spawn a NodePreview addon helper process. NEVER kill the user's session; only kill processes matching my own `-b ... --python` invocations.
5. Residual check recipe: `psutil.process_iter`, filter names blender.exe/python.exe/xremesh.exe, print pid, rss, create_time, cmdline; also sample cpu_percent over ~3s and report RAM via psutil.virtual_memory().
