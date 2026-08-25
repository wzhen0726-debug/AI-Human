# 3DDFA-V3 Deployment on Windows (photo → face landmarks + 8-part seg)

> Use when localizing facial features (esp. EYES) on a 3D head via a rendered front
> photo, instead of texture-dark-pixel guessing. Repo: github.com/wang-zidu/3DDFA-V3
> (CVPR2024). Validated end-to-end 2026-08-06 (demo rc=0, eye landmarks + seg mask extracted).
> Deploy log: `方案md记录/v3_QuadRemesher/01A眼窝与眼球/3DDFA-V3部署调研.md`.

## What it gives (why it's better than dark-pixel)

Single front photo → BFM mesh (35,709 verts) + 68/106/134 landmarks + 8-part semantic
segmentation. **Semantic** ("where is the eye") — robust to untextured / closed-eye /
makeup models, no "darkest=pupil" betting. The dark-pixel method hit an accuracy
ceiling (mm-level residual, no generalization); 3DDFA is the primary route.

## Eye data extraction (verified)

`face_model.npy` (in assets/) `annotation` = 8 parts as BFM vertex indices:
**right_eye = 440 verts idx 2087–6343 (791 tris); left_eye = 440 verts idx 10075–14326 (787 tris)**;
eyebrows 380 each; nose 1282. Part order: `[right_eye, left_eye, right_eyebrow, left_eyebrow, nose, up_lip, down_lip, skin]`.

demo output `results/<name>/<name>.npy` (dict, `allow_pickle=True`):
- `ldm68` (68,2) pixel coords: **right eye = idx 36–41, left eye = 42–47** (ldm106/134 denser).
- `seg_visible` (H,W,1): pixel value **1=right_eye, 2=left_eye** (0 bg, 3/4 brow, 5 nose, 6/7 lips, 8 skin). Eye mask = `(seg==1)|(seg==2)`.
- `seg` (H,W,8): per-part masks, ch 0/1 = right/left eye.
```python
import numpy as np
d = np.load('results/1/1.npy', allow_pickle=True).item()
right_eye = d['ldm68'][36:42]; left_eye = d['ldm68'][42:48]
eye_mask  = (d['seg_visible'][:,:,0]==1) | (d['seg_visible'][:,:,0]==2)
```

## Environment that worked (Windows 11, RTX 4070)

uv venv (Python 3.11, isolated) + torch 2.5.1+cu121 + numpy 1.26.4 + opencv 4.9.0.80 +
scipy/scikit-image/albumentations/torch-summary/Ninja. Pretrained weights (5 files, ~337MB)
in `assets/`: net_recon.pth, face_model.npy, large_base_net.pth,
retinaface_resnet50_2020-07-20_old_torch.pth, similarity_Lm3D_all.mat.

## The 5 hard-won pitfalls (each cost real time — read before deploying)

1. **PYTHONPATH pollution from the agent host.** Spawning the venv python from the
   agent's `execute_code`/subprocess inherits the host's PYTHONPATH → venv loads the
   HOST's numpy2.x, not its own → `np.VisibleDeprecationWarning` AttributeError. Fix:
   strip it before spawn — `env={k:v for k,v in os.environ.items() if k.upper()!="PYTHONPATH"}`.
2. **numpy must be <2.** 3DDFA uses `np.VisibleDeprecationWarning` (removed in numpy2).
   `uv pip install "numpy<2"` (1.26.4 works).
3. **opencv must be ==4.9.0.80.** opencv 5.x has a gapi/GStreamer circular-import crash
   (`partially initialized module 'cv2'`). `--reinstall-package opencv-python` to force 4.9.
4. **mtcnn top-level import forces tensorflow.** `face_box/__init__.py` does
   `from mtcnn import MTCNN` at module top → hard tensorflow dep (hundreds MB) even when
   you only use retinaface. Fix: move the import into `mtcnnface.__init__` (lazy).
5. **GPU renderer needs nvcc (nvdiffrast) — don't fight it.** No nvcc in PATH here.
   Use `--device cpu` + the cython CPU renderer (`util/cython_renderer`). Compile once
   with VS2022 BuildTools: `cmd /c "call <vcvars64.bat> && cd util\cython_renderer && <venv_python> setup.py build_ext -i"`
   → produces `mesh_core_cython.cp311-win_amd64.pyd`. Then demo runs full output (incl. seg)
   on CPU (~10s/img). NOTE: subprocess reading MSVC output needs `encoding='gbk'` on a
   zh-CN Windows or it crashes on undecodable bytes.

## Download pitfalls (this machine's proxy)

- **HuggingFace big blobs (50MB+)** die mid-transfer through proxy 127.0.0.1:7897
  (`SSL: UNEXPECTED_EOF_WHILE_READING` / CURLE_PARTIAL_FILE); small files pass. Workaround:
  mirror **hf-mirror.com** (same paths), bypass proxy `curl --noproxy '*'`, resume
  `curl -C - --retry 5 --retry-delay 2`; loop on partial until size matches; verify by
  loading (truncated .npy → UnpicklingError). Keep proxy for PyPI/GitHub/API only.
- **torch cu121 (2.3GB)** times out via proxy AND via download.pytorch.org direct. Use the
  Aliyun mirror whl DIRECT URL (index-url layout confuses uv):
  `uv pip install "https://mirrors.aliyun.com/pytorch-wheels/cu121/torch-2.5.1%2Bcu121-cp311-cp311-win_amd64.whl"`
  (+ matching torchvision 0.20.1). ~80s vs hours.

## Run command (validated)

```bash
cd <repo>  # cwd matters for relative asset paths
.venv/Scripts/python.exe demo.py -i examples/ -s examples/results --device cpu --backbone resnet50
# → results/<name>/<name>.npy + .obj + .png
```

## Mapping onto our high-poly (next step, not yet done)

Render high-poly front with a KNOWN camera → 3DDFA infer → 2D eye landmarks/seg →
back-project (camera-ray→BVH, or forward-project candidates to validate) → eye region on mesh.
The BFM eye vertex indices (above) are the ground-truth anchor for the eye submesh.
