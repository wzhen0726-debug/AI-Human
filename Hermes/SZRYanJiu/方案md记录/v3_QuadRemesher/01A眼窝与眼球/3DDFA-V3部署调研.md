# 3DDFA-V3 部署调研记录

**日期**: 2026-08-06（子代理后台部署中）
**目标**: 用 3DDFA-V3 的语义面部识别（关键点+部件分割）替代贴图暗像素法，精确定位眼部。
**仓库**: `Hermes/SZRYanJiu/3DDFA-V3`（外部依赖，已加 .gitignore 不入库）

---

## 一、环境（实测）

| 项 | 值 |
|---|---|
| GPU | RTX 4070, 12GB, 驱动 610.88（支持 CUDA，nvcc 不在 PATH） |
| Python | 系统 3.11.15（无 torch）；uv 建独立 .venv（Python 3.11） |
| torch | cu121（uv pip 安装，~2.3GB，经代理下载慢） |
| 渲染器 | 官方 nvdiffrast（需编译，可能踩坑）；备选 util/cython_renderer CPU 渲染器 |

## 二、输出数据（已摸清，recon.py + io.py）

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

## 三、预训练权重（assets/）

必需文件（从 HuggingFace `datasets/Zidu-Wang/3DDFA-V3` 下载）：
- `face_model.npy`（99MB，BFM 模型+标注）
- `net_recon.pth`（92MB，ResNet-50 重建模型）✅ 已下
- `large_base_net.pth`（人脸检测辅助）
- `retinaface_resnet50_2020-07-20_old_torch.pth`（人脸检测器）
- `similarity_Lm3D_all.mat`（裁剪用）

## 四、网络坑与解法（重要，复用价值）

**问题**: 经代理（127.0.0.1:7897）下载 HuggingFace 大文件时 SSL 间歇中断（`UNEXPECTED_EOF_WHILE_READING`），小文件 OK、大文件 FAIL。

**解法**: 
1. **hf-mirror.com 镜像 + 不走代理直连**（`curl --noproxy '*'`）——大文件稳定；
2. `curl -C -`（断点续传）+ `--retry 5 --retry-delay 2`；
3. 代理只用于小文件/API，大文件走镜像直连。

**命令模板**:
```bash
# 大文件: 镜像直连 + 断点续传
curl -sL --noproxy '*' -C - --retry 5 --retry-delay 2 \
  -o face_model.npy \
  "https://hf-mirror.com/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets/face_model.npy"
```

## 五、定位眼部的管线（规划）

```
渲染高模正脸图(已知相机参数) 
  → 3DDFA-V3 推理(出2D眼部关键点+分割mask)
  → 按相机参数把2D关键点/分割反投影回3D网格
  → 得到精确的眼部区域(替代暗像素法)
```

优势：3DDFA 是语义识别（懂"哪里是眼睛"），不靠"最暗=瞳孔"的赌运气，鲁棒性强、可泛化到素模/闭眼/不同妆容。

## 六、状态

- [x] 仓库克隆
- [x] 输出格式摸清（npy 键 + 分割/mask）
- [x] 网络坑定位与解法（镜像直连）
- [ ] torch + 依赖装完（下载中）
- [ ] 权重全部下完（net_recon 已下，其余续传中）
- [ ] demo 跑通（示例图→BFM+关键点+分割）
- [ ] 高模正脸→眼部关键点提取验证
- [ ] 反投影回 3D 定位眼部

（后续步骤完成后补实测结果）
