# Eyeball Placement Fit Verification (01_2)

## Re-run rule

Eyeball placement (`run_eyeball.py`) must be re-run whenever the eye-socket base
(`01_1_eye_socket.blend`) changes variant (e.g. v46→v48), because IN_BLEND is the socket
blend itself. Placement parameters are socket-variant-independent — x/z from 3DDFA,
y from fitted virtual eyeball sphere center, + `EYE_PUSH_BACK` — so keep the tuned
parameters on socket rebuild; do NOT re-tune positions.

## Quantitative fit check (`check_eyeball_fit.py`)

KD-tree of face verts within 40mm of each eye center; sample the eyeball sphere surface
(~4000 pts) and measure against skin:

| Metric | Healthy baseline (v48, 2026-08-21) | Failure meaning |
|---|---|---|
| Min surface-to-skin gap | 0.07–0.21mm | ≤0 = penetration; >1mm = floating eyeball |
| Rear pole (center +R along +y) to skin | ≈8mm | clearance behind the bowl |
| Cornea center vs socket center offset (xz) | 0.00mm | >0.5mm = decentered |
| Cornea front pole vs rim front y | protrudes 13–15mm | normal — eyeball bulges past the opening |

Print a per-eye summary; all four must land in range before delivering.

## Delivery

Also deliver the rendered front+close shots AND the blend file itself — the user verifies
eyeball position personally in the GUI and does not trust agent verdicts alone.
