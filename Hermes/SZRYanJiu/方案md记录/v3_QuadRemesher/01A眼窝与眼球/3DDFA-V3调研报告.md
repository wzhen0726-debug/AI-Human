# 3DDFA-V3 调研报告

**调研日期**: 2026-08-04（2026-08-06 整理）
**调研对象**: https://github.com/wang-zidu/3DDFA-V3
**论文**: 3D Face Reconstruction with the Geometric Guidance of Facial Part Segmentation, CVPR 2024 (Highlight), arXiv:2312.00311
**结论**: ❌ 当前管线不需要引入，留作后备方案

---

## 一、它是做什么的

**一句话**：单张 2D 人脸照片 → 重建出带语义分割标注的 3D 人脸网格。

具体输出（一次推理全部产出）：

| 输出 | 内容 | 格式 |
|---|---|---|
| 3D 人脸网格 | BFM 拓扑，35,709 顶点 | OBJ（带/不带贴图） |
| 关键点 | 68 / 106 / 134 点（2D+3D） | npy |
| 8 部件语义分割 | 含眼睛区域 mask | 2D 分割图 + 3D 顶点标注 |
| 贴图 | 从照片提取的纹理 | OBJ 材质 |

**技术核心**（论文贡献）：提出 Part Re-projection Distance Loss (PRDL)，把人脸部件分割转化为 2D 点集，让重建网格与分割区域在几何分布上对齐。相比只依赖稀疏关键点的方法，能更好处理极端表情（闭眼、张嘴、皱眉）。

---

## 二、技术规格

### 模型与数据

- 人脸模型基于 **BFM**（Basel Face Model），35,709 顶点拓扑
- 与 Deep3D / MGCNet / HRN 等同拓扑系列互通（提供 38,365/53,215/53,490 顶点的索引映射）
- 提供 8 部件分割标注（`face_model.npy` 中的 `annotation`/`annotation_tri`）
- 合成表情数据集（基于 MaskGan 扩展：闭眼、张嘴、皱眉）

### 推理骨干

| 版本 | 特点 |
|---|---|
| ResNet-50 | 推荐，精度最高 |
| MobileNet-V3 | 快速版，精度接近，速度更高（官方标注"仍在测试中"） |

### 依赖环境

```
python 3.8 (conda)
torch 1.12.1+cu102（Windows 10 上 1.10 验证可用）
Pillow 10.3.0 / opencv-python 4.9.0.80（要求同版本 libjpeg）
albumentations（retinaface 检测器）
tensorflow + mtcnn（可选，MTCNN 检测器）
nvdiffrast（可微渲染器，NVlabs，需编译）
  或 cython CPU 渲染器（face3d 改造，免 nvdiffrast）
Ninja（编译）
```

### 预训练权重（需从 HuggingFace 下载）

`net_recon.pth`（主模型）、`face_model.npy`（BFM 模型+标注）、`retinaface_resnet50_*.pth`（人脸检测）、`large_base_net.pth` 等约 8 个文件。

---

## 三、对我们管线有什么用

我们关心的场景：**眼窝制作时的眼部区域定位**。

3DDFA-V3 能提供的眼部相关输出：
1. 眼睛区域的 2D 分割 mask（8 部件分割之一）
2. 眼周关键点（68/106/134 点中的眼点）
3. 3D 网格上的眼部顶点索引（`annotation`）

**理论上的使用路径**：
```
高模渲染正脸图 → 3DDFA-V3 推理 → 2D 眼部 mask/关键点
→ 射线反投影回 3D 网格 → 得到眼区顶点
```

---

## 四、为什么当前不用它

### 4.1 输入类型不匹配

| | 3DDFA-V3 假设 | 我们的管线 |
|---|---|---|
| 输入 | 2D 照片 | 3D 高模（Tripo 生成） |
| 目标 | 从照片重建 3D | 3D 已存在，只需定位眼区 |
| 核心功能利用率 | 重建+分割+关键点 | 只用到"眼部定位"一个零头 |

它的主功能（照片→3D 重建）我们完全用不上——我们已经有 3D 高模了。

### 4.2 已有更轻的替代方案且实测成功

当前 01A 眼窝脚本用的方法：**UV 采样贴图亮度 → 暗像素聚类 → 质心**。

- 原理：Tripo 高模贴图上画了眼睛，虹膜是暗像素
- 实测结果：双眼各提取 500+ 暗像素顶点，质心稳定
- 依赖：零（纯 numpy + Blender 内置）
- 耗时：秒级

对比 3DDFA-V3 路线：需要装 conda 环境 + PyTorch + 编译 nvdiffrast + 下载预训练权重，然后渲染→推理→反投影，一套下来环境配置就可能踩坑半天，最后得到的眼区定位精度不会比贴图暗像素法更好（因为我们的贴图上本来就有画好的眼睛）。

### 4.3 部署成本 vs 收益

| 维度 | 成本/收益 |
|---|---|
| 环境配置 | conda + PyTorch + nvdiffrast 编译 + 权重下载，估计 0.5-1 天 |
| 运行依赖 | 每次跑都要 GPU 推理（或慢速 CPU 渲染器） |
| 收益 | 眼部定位——已被零成本方法解决 |
| 零预算适配 | 不符（零预算原则：能不用重依赖就不用） |

---

## 五、什么时候会需要它（后备触发条件）

只有一种情况需要重新启用：**输入模型的贴图上没有画眼睛（纯素模）**。

此时贴图暗像素法会失败（找不到暗像素聚类），3DDFA-V3 的后备路线：
```
渲染高模正脸图 → 3DDFA-V3 → 2D 眼部 landmarks/分割
→ 按相机参数反投影回 3D 网格 → 眼区顶点集
```

这条路线已写入 `眼窝与眼球集成设计方案.md` 第二章，但不进当前管线。

---

## 六、参考链接

- 官方仓库: https://github.com/wang-zidu/3DDFA-V3
- 论文: https://arxiv.org/abs/2312.00311
- 权重下载: https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/tree/main/assets
- BFM 模型: https://faces.dmi.unibas.ch/bfm/
