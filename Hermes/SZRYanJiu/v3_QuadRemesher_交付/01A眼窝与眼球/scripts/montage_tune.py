# -*- coding: utf-8 -*-
"""把tune A/B/C三组正面渲染拼成一张对比图(带中文标签)."""
from PIL import Image, ImageDraw, ImageFont
import os

shot = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screenshots")
tags = ["A_凸2.8_高0.7", "B_凸1.0_高0.4", "C_凸负1.0_高0.2"]
labels = ["A: 凸出2.8mm (旧验收位)", "B: 凸出1.0mm", "C: 凸出-1.0mm (收进眼睑后)"]
imgs = [Image.open(os.path.join(shot, f"tune_{t}_front.png")) for t in tags]
w, h = imgs[0].size
pad, bar = 20, 60
canvas = Image.new("RGB", (w*3 + pad*4, h + bar + pad*2), (30, 30, 30))
d = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 36)
except Exception:
    font = ImageFont.load_default()
for i, (im, lb) in enumerate(zip(imgs, labels)):
    x = pad + i*(w + pad)
    canvas.paste(im, (x, bar))
    d.text((x + 10, 12), lb, fill=(255, 255, 200), font=font)
out = os.path.join(shot, "tune_ABC_montage.png")
canvas.save(out)
print(out, canvas.size)
