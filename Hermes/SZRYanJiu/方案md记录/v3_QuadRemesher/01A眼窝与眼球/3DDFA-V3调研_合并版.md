# 3DDFA-V3 面部识别调研（合并版）

**状态**: ⏸️ 已暂停 — 半自动手动标记点方案取代（见《01A完整记录_合并版》）
**合并自**: 原 2 个调研文件


---

# 〔合并来源〕3DDFA-V3部署调研.md

## 3DDFA-V3 部署调研记录

**日期**: 2026-08-06（子代理后台部署中）
**目标**: 用 3DDFA-V3 的语义面部识别（关键点+部件分割）替代贴图暗像素法，精确定位眼部。
**仓库**: `Hermes/SZRYanJiu/3DDFA-V3`（外部依赖，已加 .gitignore 不入库）

---

### 一、环境（实测）

| 项 | 值 |
|---|---|
| GPU | RTX 4070, 12GB, 驱动 610.88（支持 CUDA，nvcc 不在 PATH） |
| Python | 系统 3.11.15（无 torch）；uv 建独立 .venv（Python 3.11） |
| torch | cu121（uv pip 安装，~2.3GB，经代理下载慢） |
| 渲染器 | 官方 nvdiffrast（需编译，可能踩坑）；备选 util/cython_renderer CPU 渲染器 |

### 二、输出数据（已摸清，recon.py + io.py）

demo 对每张图输出一个 `.npy`（dict），含：

| 键 | 内容 | 眼部相关 |
|---|---|---|
| `ldm68` / `ldm106` / `ldm106_2d` / `ldm134` | 2D 关键点像素坐标（已映射回原图） | **眼睛关键点在此** |
| `seg_visible` | H×W×1，值 0-8，**8 部件语义分割**（含眼睛区域 mask） | **眼睛区域分割在此** |
| obj | BFM 网格（35,709 顶点，带/不带贴图） | — |

**眼部数据提取**：`face_model.npy` 中 `annotation`/`annotation_tri` 是 8 部件分割的顶点标注，`ldm68/106/134` 是各版本关键点在 BFM 顶点中的索引。

**已实测（face_model.npy 加载成功）**：8 部件分割的顶点结构——

| part | 部件 | 顶点数 | 三角面 | BFM 顶点 idx 范围 |
|---|---|---|---|---|
| 0 | right_eye 右眼 | 440 | 791 | [2087, 6343] |
| 1 | left_eye 左眼 | 440 | 787 | [10075, 14326] |
| 2/3 | right/left_eyebrow 眉 | 380 | 639 | — |
| 4 | nose 鼻 | 1282 | 2405 | — |
| 5 | lip 唇 | — | — | — |

**这意味着眼部区域可用分割标注精确定位**（右眼=BFM 顶点 2087-6343、左眼 10075-14326），不再靠暗像素赌运气。反投影时把 BFM 眼部顶点/关键点映到我们的高模即可。

### 三、预训练权重（assets/）

必需文件（从 HuggingFace `datasets/Zidu-Wang/3DDFA-V3` 下载）：
- `face_model.npy`（99MB，BFM 模型+标注）
- `net_recon.pth`（92MB，ResNet-50 重建模型）✅ 已下
- `large_base_net.pth`（人脸检测辅助）
- `retinaface_resnet50_2020-07-20_old_torch.pth`（人脸检测器）
- `similarity_Lm3D_all.mat`（裁剪用）

### 四、网络坑与解法（重要，复用价值）

**问题**: 经代理（127.0.0.1:7897）下载 HuggingFace 大文件时 SSL 间歇中断（`UNEXPECTED_EOF_WHILE_READING`），小文件 OK、大文件 FAIL。

**解法**: 
1. **hf-mirror.com 镜像 + 不走代理直连**（`curl --noproxy '*'`）——大文件稳定；
2. `curl -C -`（断点续传）+ `--retry 5 --retry-delay 2`；
3. 代理只用于小文件/API，大文件走镜像直连。

**命令模板**:
```bash
## 大文件: 镜像直连 + 断点续传
curl -sL --noproxy '*' -C - --retry 5 --retry-delay 2 \
  -o face_model.npy \
  "https://hf-mirror.com/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets/face_model.npy"
```

### 五、定位眼部的管线（规划）

```
渲染高模正脸图(已知相机参数) 
  → 3DDFA-V3 推理(出2D眼部关键点+分割mask)
  → 按相机参数把2D关键点/分割反投影回3D网格
  → 得到精确的眼部区域(替代暗像素法)
```

优势：3DDFA 是语义识别（懂"哪里是眼睛"），不靠"最暗=瞳孔"的赌运气，鲁棒性强、可泛化到素模/闭眼/不同妆容。

### 五点五、眼部数据提取方法（子代理实测验证，2026-08-06）

**8 部件分割顺序**（recon.py 第121行注释确认）：
`[right_eye, left_eye, right_eyebrow, left_eyebrow, nose, up_lip, down_lip, skin]`

demo 输出 `<name>.npy`（dict，allow_pickle）含：

| 键 | 内容 | 眼部提取 |
|---|---|---|
| `seg_visible` | H×W×1，原图坐标 | **值1=右眼、2=左眼**（3=右眉 4=左眉 5=鼻 6=上唇 7=下唇 8=皮肤 0=背景）。眼部mask = `(seg==1)|(seg==2)` |
| `seg` | H×W×8 | 第0、1通道=右/左眼独立mask（255=该区域） |
| `ldm68` | 68关键点像素坐标 | **右眼=索引36–41，左眼=索引42–47** |
| `ldm106`/`ldm134` | 更密关键点 | 右眼约66–75，左眼约76–85（精确索引待跑通后画编号图确认） |

**3D 网格级**：`face_model.npy` 的 `model['annotation'][0]`/`[1]` = 右/左眼各 440 个 BFM 顶点索引（可用于 Blender 侧选中眼部顶点）。

**提取代码**：
```python
import numpy as np
d = np.load('results/1/1.npy', allow_pickle=True).item()
right_eye = d['ldm68'][36:42]          # 右眼关键点(像素坐标)
left_eye  = d['ldm68'][42:48]          # 左眼关键点
eye_mask  = (d['seg_visible'][:,:,0]==1) | (d['seg_visible'][:,:,0]==2)  # 眼部mask
```

### 六、torch 安装卡点与解法

- **问题**: torch cu121（CUDA 版 2.3GB）经代理/直连 download.pytorch.org 多次 300-600s 超时。
- **解法**: 用**国内镜像**装。阿里云 cu121 有 CUDA 版 win 包，但 `--index-url` 目录结构 uv 解析不了 → **直接用完整 whl URL**：
  ```bash
  uv pip install --python .venv/Scripts/python.exe \
    "https://mirrors.aliyun.com/pytorch-wheels/cu121/torch-2.5.1%2Bcu121-cp311-cp311-win_amd64.whl" \
    "https://mirrors.aliyun.com/pytorch-wheels/cu121/torchvision-0.20.1%2Bcu121-cp311-cp311-win_amd64.whl"
  ```
  备选：CPU 版（190MB，单图推理够用，但不利用 GPU）。
- **渲染器**: 机器无 gcc/cl 在 PATH，但有 **VS2022 BuildTools**（`C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools`）→ 可编译 `util/cython_renderer`（CPU 渲染器）。nvdiffrast 因 nvcc 不在 PATH 不死磕，用 `--device cpu` + cython 渲染器即可出全部输出（含分割）。

### 六、状态

- [x] 仓库克隆
- [x] 输出格式摸清（npy 键 + 分割/mask）
- [x] 网络坑定位与解法（镜像直连）
- [x] torch + 依赖装完（阿里云镜像 whl 直链装 cu121，见"六"）
- [x] 权重全部下完（5/5，镜像直连+断点续传）
- [x] **demo 跑通**（2026-08-06，CPU device + cython 渲染器，rc=0 处理 examples/1.jpg + 2.png）
- [x] 眼部关键点/分割提取验证（ldm68 右眼36-41/左眼42-47 像素坐标精确，seg_visible 值0-8 齐全）

#### demo 跑通的最终配置（实测有效）

**环境坑记录**（关键，避免重踩）：
1. **PYTHONPATH 污染**：从 Hermes 的 execute_code 起子进程会继承 Hermes 的 PYTHONPATH，导致 .venv 加载到 hermes-agent 的 numpy2.x → 起子进程前必须 `{k:v for k,v in os.environ.items() if k.upper()!="PYTHONPATH"}`。
2. **numpy**：必须 `<2`（3DDFA 用了 numpy2 移除的 `np.VisibleDeprecationWarning`）→ 装 `numpy<2`（实测 1.26.4）。
3. **opencv**：必须 `==4.9.0.80`（5.0 有 gapi/GStreamer 循环 import bug）→ 强制 `--reinstall-package opencv-python`。
4. **mtcnn 懒加载**：`face_box/__init__.py` 顶层 `from mtcnn import MTCNN` 硬依赖 tensorflow → 改成 `mtcnnface.__init__` 内懒加载（我们用 retinaface，不需要 tensorflow）。
5. **渲染器**：GPU 分支要 nvdiffrast（需 nvcc，装不上）→ 用 **CPU device + cython CPU 渲染器**（`util/cython_renderer`，VS2022 BuildTools 的 vcvars64 环境编译出 `mesh_core_cython.cp311-win_amd64.pyd`）。

**最终跑通命令**：
```bash
## 先编译CPU渲染器(一次性): cmd里 call vcvars64.bat 后 python setup.py build_ext -i
cd "E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\3DDFA-V3"
.venv/Scripts/python.exe demo.py -i examples/ -s examples/results --device cpu --backbone resnet50
## 输出: results/<name>/<name>.npy (含 ldm68/106/134 + seg_visible/seg) + .obj + .png
```
> 注：虽然 torch 装了 cu121（CUDA 版），但 demo 实际用 `--device cpu` 跑（因 nvdiffrast 缺 nvcc）。重建网络推理在 CPU 上单图 ~10s 可接受；分割渲染走 cython CPU 渲染器。

- [ ] 高模正脸→3DDFA→反投影定位眼部（下一步）


---

# 〔合并来源〕3DDFA-V3调研报告.md

## 3DDFA-V3 调研报告

**调研日期**: 2026-08-04（2026-08-06 整理）
**调研对象**: https://github.com/wang-zidu/3DDFA-V3
**论文**: 3D Face Reconstruction with the Geometric Guidance of Facial Part Segmentation, CVPR 2024 (Highlight), arXiv:2312.00311
**结论**: ❌ 当前管线不需要引入，留作后备方案

---

### 一、它是做什么的

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

### 二、技术规格

#### 模型与数据

- 人脸模型基于 **BFM**（Basel Face Model），35,709 顶点拓扑
- 与 Deep3D / MGCNet / HRN 等同拓扑系列互通（提供 38,365/53,215/53,490 顶点的索引映射）
- 提供 8 部件分割标注（`face_model.npy` 中的 `annotation`/`annotation_tri`）
- 合成表情数据集（基于 MaskGan 扩展：闭眼、张嘴、皱眉）

#### 推理骨干

| 版本 | 特点 |
|---|---|
| ResNet-50 | 推荐，精度最高 |
| MobileNet-V3 | 快速版，精度接近，速度更高（官方标注"仍在测试中"） |

#### 依赖环境

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

#### 预训练权重（需从 HuggingFace 下载）

`net_recon.pth`（主模型）、`face_model.npy`（BFM 模型+标注）、`retinaface_resnet50_*.pth`（人脸检测）、`large_base_net.pth` 等约 8 个文件。

---

### 三、对我们管线有什么用

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

### 四、为什么当前不用它

#### 4.1 输入类型不匹配

| | 3DDFA-V3 假设 | 我们的管线 |
|---|---|---|
| 输入 | 2D 照片 | 3D 高模（Tripo 生成） |
| 目标 | 从照片重建 3D | 3D 已存在，只需定位眼区 |
| 核心功能利用率 | 重建+分割+关键点 | 只用到"眼部定位"一个零头 |

它的主功能（照片→3D 重建）我们完全用不上——我们已经有 3D 高模了。

#### 4.2 已有更轻的替代方案且实测成功

当前 01A 眼窝脚本用的方法：**UV 采样贴图亮度 → 暗像素聚类 → 质心**。

- 原理：Tripo 高模贴图上画了眼睛，虹膜是暗像素
- 实测结果：双眼各提取 500+ 暗像素顶点，质心稳定
- 依赖：零（纯 numpy + Blender 内置）
- 耗时：秒级

对比 3DDFA-V3 路线：需要装 conda 环境 + PyTorch + 编译 nvdiffrast + 下载预训练权重，然后渲染→推理→反投影，一套下来环境配置就可能踩坑半天，最后得到的眼区定位精度不会比贴图暗像素法更好（因为我们的贴图上本来就有画好的眼睛）。

#### 4.3 部署成本 vs 收益

| 维度 | 成本/收益 |
|---|---|
| 环境配置 | conda + PyTorch + nvdiffrast 编译 + 权重下载，估计 0.5-1 天 |
| 运行依赖 | 每次跑都要 GPU 推理（或慢速 CPU 渲染器） |
| 收益 | 眼部定位——已被零成本方法解决 |
| 零预算适配 | 不符（零预算原则：能不用重依赖就不用） |

---

### 五、什么时候会需要它（后备触发条件）

只有一种情况需要重新启用：**输入模型的贴图上没有画眼睛（纯素模）**。

此时贴图暗像素法会失败（找不到暗像素聚类），3DDFA-V3 的后备路线：
```
渲染高模正脸图 → 3DDFA-V3 → 2D 眼部 landmarks/分割
→ 按相机参数反投影回 3D 网格 → 眼区顶点集
```

这条路线已写入 `眼窝与眼球集成设计方案.md` 第二章，但不进当前管线。

---

### 六、参考链接

- 官方仓库: https://github.com/wang-zidu/3DDFA-V3
- 论文: https://arxiv.org/abs/2312.00311
- 权重下载: https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/tree/main/assets
- BFM 模型: https://faces.dmi.unibas.ch/bfm/

