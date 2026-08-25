# UV Margin Formula (2026-07-21)

## Purpose
After UV unwrap, islands may touch the [0,1] boundaries (0% margin), causing texture bleeding. Apply uniform margin around all UVs.

## Formula
```python
import numpy as np

# f is flat float32 array of UVs, shape (n_loops*2,)
us = f[0::2]; vs = f[1::2]
min_u, max_u = min(us), max(us)
min_v, max_v = min(vs), max(vs)
range_u = max(max_u - min_u, 1e-6)
range_v = max(max_v - min_v, 1e-6)

margin = 0.02  # 2% margin
scale = 1.0 - 2 * margin  # 0.96 for 2% margin

for i in range(len(us)):
    f[i*2] = margin + (us[i] - min_u) / range_u * scale
    f[i*2+1] = margin + (vs[i] - min_v) / range_v * scale
```

## Tradeoff
| Margin | Scale | Utilization |
|--------|-------|:-----------:|
| 2% | 0.96 | ~79% |
| 3% | 0.94 | ~70% |
| 5% | 0.90 | ~62% |

## ZEN UV Packing Margin Issue
ZEN UV's `packing=True` produces islands that touch the [0,1] boundaries (0% margin). Always apply this formula after ZEN UV unwrap.