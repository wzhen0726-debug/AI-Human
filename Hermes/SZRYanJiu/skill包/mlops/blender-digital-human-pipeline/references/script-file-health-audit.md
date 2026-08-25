# Pipeline Script Health Audit (encoding corruption, batch compile check)

Use when: pipeline scripts "error out" with no obvious cause, before blaming Blender/QR/logic — or as a pre-flight check before a full pipeline re-run.

## The failure that motivated this (2026-08-06)
`02_qr_auto.py` had a stray UTF-16 BOM (`FF FE`) prepended to an otherwise UTF-8 file
(introduced by an earlier file-write). Python raised `SyntaxError: 'utf-8' codec can't
decode byte 0xff in position 0` on import — the script was silently un-runnable while
looking perfectly normal in listings. The repo copy was clean; only the working copy
was corrupted — so `git diff HEAD` showed nothing. Don't assume "unchanged in git"
means "healthy on disk".

## Batch audit recipe (run from repo root, system python)
```python
import os, glob, py_compile
base = r"<pipeline delivery root>"
for p in sorted(glob.glob(os.path.join(base, "**", "*.py"), recursive=True)):
    data = open(p, "rb").read()
    bad_bom = data[:2] == b"\xff\xfe"          # UTF-16 BOM on a UTF-8 file
    body = data[2:] if bad_bom else data
    try:
        body.decode("utf-8")
        enc_ok = True
    except Exception:
        enc_ok = False
    try:
        if bad_bom:  # compile the stripped body
            compile(body.decode("utf-8"), p, "exec")
        else:
            py_compile.compile(p, doraise=True)
        comp = "OK"
    except Exception as e:
        comp = f"FAIL: {e}"
    print(("BAD_BOM" if bad_bom else "ok     "), os.path.relpath(p, base), comp)
```

## Fix
```python
data = open(p, "rb").read()
assert data[:2] == b"\xff\xfe"
open(p, "wb").write(data[2:])   # strip the 2 stray bytes, keep everything else
```
Then re-verify with `py_compile`. Also verify the fix didn't drift from git
(`git diff` on the file) — in the 2026-08-06 case stripping restored an exact match
with HEAD, so no commit was needed.

## Related read_file quirk
A file with this corruption makes Hermes `read_file` report "binary file cannot display".
That "binary" verdict on a `.py` file is itself a diagnostic signal — check leading bytes
(`xxd file | head -1` or the recipe above) instead of working around it with iconv guesses.

## Pitfalls
- `iconv -f UTF-16` on a UTF-8-with-stray-BOM file produces mojibake, not an error —
  don't trust iconv output as proof of encoding; inspect raw bytes first.
- After any write_file/patch session on pipeline scripts, a 10-second py_compile sweep
  of the touched files catches this class of corruption immediately.
