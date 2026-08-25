# Pipeline script corruption: stray UTF-16 BOM

## Symptom
A previously-working pipeline script suddenly fails:
- `SyntaxError (unicode error) 'utf-8' codec can't decode byte 0xff in position 0` at line 1, with a garbled char (e.g. `import bpy` shown as `import bpy`).
- read_file flags the .py as "binary / cannot display".

## Cause
A stray UTF-16 BOM (`FF FE`, 2 bytes) got written BEFORE the UTF-8 body by an earlier file write. The body itself is valid UTF-8 (no NUL bytes).

## Verify
```python
data = open(path,'rb').read()
print(data[:8].hex())                      # starts with fffe
data[2:].decode('utf-8')                    # body decodes fine -> BOM-only corruption
```

## Fix
Strip the first 2 bytes, rewrite, then verify with `py_compile.compile(path, doraise=True)`.

## Batch scan (all pipeline scripts)
```python
for p in glob.glob(os.path.join(base,'**','*.py'), recursive=True):
    d = open(p,'rb').read()
    if d[:2] == b'\xff\xfe': print('BAD_BOM', p)
```

## Guard
After writing any pipeline script, py_compile it before launching in Blender — a corrupted script fails instantly with a confusing line-1 error and wastes a debug cycle.
