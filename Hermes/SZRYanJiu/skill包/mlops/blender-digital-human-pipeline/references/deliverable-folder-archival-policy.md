# Deliverable Folder Archival Policy (01A eye socket / v3 交付)

End-of-milestone sequence the user expects when a variant is finalized
("记录做全 → 上传 → 修bug → 清理垃圾 → 优化上下文"):

1. **Docs**: append a chapter to `01A眼窝与眼球_技术方案详细记录.md` — problem, failed-attempts
   chain, solution with parameters, verification table, user's own words on the decision,
   lessons. Update the TOC block at the top of the same file.
2. **Git**: commit scripts + docs + data jsons. Root `.gitignore` excludes `*.blend` and
   `*.npz` — blends stay local only. The screenshots dir is ignored too (don't force-add pngs).
   Commit cleanup moves as renames/deletes in the same repo (logs moved to archive show as R).
3. **Skill sync**: update this skill's eye-socket references with the newly finalized
   baseline (mark user-approved variant + backup filename + known residues).
4. **Cleanup** (achieved: models 801M→371M, screenshots 75M→41M):
   - Delete ALL `*.blend1` (autosave junk).
   - Delete superseded era blends (v35/v37_backup/v37_check) — pipeline can regenerate any
     version; only delete what is reproducible or superseded by a kept backup.
   - KEEP: current blend, finalized backup (`*_v48_final.blend`), user-comparison variants
     (方案A/方案B), downstream artifacts (01_2 eyeball), marker blend (01A_markers_eyelid).
   - Delete `__pycache__/`, `*.npz` intermediates, stray root-level `*.txt` logs.
   - `scripts/logs/`: keep current-version logs, move older ones to `scripts/logs/archive/`.
   - `screenshots/`: delete old-version renders (v35–v47 etc.), keep current version +
     INPUT_* + basecolor texture + `3ddfa/` data + eyeball shots.
5. **Bugs found during review** (e.g. clay render overexposure) — fix in place + commit,
   note the fix in the relevant reference file.
6. **Memory**: update the finalized-baseline entry so future sessions don't re-litigate
   settled variants.

Enumerate what is deleted and why in the summary to the user; never delete a blend without a
kept backup or pipeline reproducibility.
