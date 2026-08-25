# 3DDFA-V3 眼部（眼睛）2D 关键点与语义分割数据提取

3DDFA-V3 (CVPR2024, wang-zidu/3DDFA-V3) 跑通 demo 后，每张图输出 `<name>.npy`（pickle dict，已映射回原图坐标系）。本文档说明眼部数据在哪、怎么提取。已通过实际加载 `assets/face_model.npy` + 读源码（`model/recon.py`、`util/io.py`）验证。

## 一、语义分割（8 部件）

**部件顺序**（recon.py 第 121 行注释，固定）：
`[right_eye, left_eye, right_eyebrow, left_eyebrow, nose, up_lip, down_lip, skin]`

输出里两种分割（npy dict 的 key）：
- `seg_visible`: shape (H, W, 1)，单通道。**像素值含义：0=背景， 1=右眼， 2=左眼， 3=右眉， 4=左眉， 5=鼻， 6=上唇， 7=下唇， 8=皮肤**。被遮挡部件不显示。
- `seg`: shape (H, W, 8)，每部件一个独立通道（值 0 或 255）。第 0 通道=右眼，第 1 通道=左眼。被遮挡区域仍按 3D 估计显示。

**眼部 mask 提取**：
```python
import numpy as np
d = np.load('<name>.npy', allow_pickle=True).item()
sv = d['seg_visible'][:, :, 0]          # (H, W)
eye_mask = (sv == 1) | (sv == 2)        # 双眼合并
right_eye_mask = (sv == 1)
left_eye_mask  = (sv == 2)
# 或用 8 通道版：eye_mask = (d['seg'][:,:,0]==255) | (d['seg'][:,:,1]==255)
```

**3D 网格级（Blender 侧选眼部顶点用）**：`assets/face_model.npy` 的 `model['annotation']` 是 8 个 list，分别存 8 部件的顶点索引：
- `annotation[0]` = 右眼 440 顶点（791 三角面，idx 范围 ~[2087, 6343]）
- `annotation[1]` = 左眼 440 顶点（787 三角面，idx 范围 ~[10075, 14326]）
- `annotation_tri[0]/[1]` = 对应三角面。整套网格 35709 顶点 / 70789 三角面（BFM 拓扑，与 Deep3D/MGCNet/HRN 一致）。

## 二、2D 关键点

npy dict 的 key：`ldm68`、`ldm106`、`ldm106_2d`、`ldm134`，每个都是 (N, 2) 已映射回原图像素坐标（util/io.py 的 back_resize_ldms 处理过，y 轴已翻转回正常图像坐标）。

- **68 点**（标准定义）：**右眼 = 索引 36–41，左眼 = 索引 42–47**（已对照顶点索引验证：右眼顶点 2215/3886/4920/5828/4801/3640，左眼 10455/11353/12383/14066/12653/11492）。
  ```python
  right_eye_kpts = d['ldm68'][36:42]   # (6, 2)
  left_eye_kpts  = d['ldm68'][42:48]
  ```
- **106 点**：右眼约在索引 66–75（顶点 2215, 3888, 4661, 5439, 6215, 5191, 4416, 3642, 4666, ...），左眼约 76–85（10077, 10969, 11610, 12514, 14066, 12784, 11881, 11236, 11487, ...）—— 与 68 点眼部顶点高度重合。**精确索引需画编号图确认**（见下）。
- **134 点**：含更密的眼眶轮廓点，眼睛区域同样需编号图确认。
- `ldm106` vs `ldm106_2d`：前者是 3D 顶点直接投影；后者对脸部轮廓 33 点做了动态 2D marching（姿态变化时轮廓更准），**眼睛等非轮廓点两者一致**。

**确认 106/134 眼部精确索引的方法**：把关键点连同索引编号画到重建结果图上（用 `assets/meanshape-106ldms.obj` / `meanshape-134ldms.obj` 或任意一张 demo 输出的 ldm 可视化），肉眼数出落在眼眶上的索引。

## 三、跑通要点（Windows 11）
- demo 入口：`python demo.py -i examples/ -s examples/results --device cpu --backbone resnet50`（resnet50 精度高于 mbnetv3）。
- 渲染器：`--device cpu` 走 `util/cpu_renderer.py`（需先编译 `util/cython_renderer: python setup.py build_ext -i`，需 Cython + MSVC BuildTools，机器已有 VS2022 BuildTools）；`--device cuda` 走 nvdiffrast（Windows 编译需 nvcc+MSVC，易踩坑）。**纯提取 2D 关键点不依赖渲染器**（只做几何投影 to_image），但 seg 分割和 render 可视化需要渲染器。
- 权重下载见 huggingface 下载技巧（hf-mirror 直连 + 断点续传 + 字节数校验，代理下大文件会被静默截断）。
