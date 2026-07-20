# 版本一：MetaHuman全身Wrap方案 — 完整技术档案

## 环境

| 项目 | 值 |
|------|-----|
| Blender | 5.1.0，路径 `D:\Program Files\Blender Foundation\Blender 5.1\blender.exe` |
| Python | 3.11（Blender内置），numpy/scipy已安装 |
| 运行方式 | `--background --factory-startup --python script.py` |
| 付费插件 | Auto-Rig Pro, Quad Remesher, Better FBX, MACHIN3tools |
| 项目路径 | `E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\` |
| 文档路径 | `全流程文档\数字人模型AI自动化处理流程_技术方案.docx`（v5.0） |
| 测试路径 | `test01\`（头部wrap），`test_mirror\`（镜像对称） |

## 项目目标

Tripo AI生成的高模（含衣服头发）→ 去除衣服/头发 → 对称化 → MetaHuman全身模板wrap → ARKit 52面绑 + Mixamo身体绑 → GLB输出。

## 技术调研过程

### 调研1：两条技术路线选型
- **路线一（相机矩阵扫描）**：设备成本50-500万美元，需专业影棚+运维团队，放弃
- **路线二（AI生成）**：Tripo AI等平台，免费额度，选为唯一路线
- 写入文档：`全流程文档\02_方案选型与决策.md`

### 调研2：Quad Remesher布线对绑定的影响
- 来源：Exoside官方、Blender Artists论坛、80.lv、Polycount
- 结论：Quad Remesher能生成全四边面但**无法生成面部环形线+关节变形友好布线**
- 面部必须用模板拓扑（MetaHuman），身体用Quad Remesher可勉强接受
- 写入文档：`全流程文档\03_技术难点分析.md`

### 调研3：衣服去除
- 体积法（布尔）：紧身衣可用，宽松衣不可用（衣服下面是空的）
- AI分割法（SAM/SCHP）：多视图2D分割→3D面片投票，精度80-85%
- 最大难点：宽松衣物下方无身体几何，需从SMPL模板移植面片
- 纯几何方案：颜色/曲率/法线规则过滤，适合简单场景
- 写入文档：`test01\docs\research_report.md`

### 调研4：头发睫毛去除
- 颜色法（推荐）：深色头发vs肉色皮肤，UV采样纹理
- 距离阈值法：短发可靠，长发不可靠
- 曲率法（辅助）：头发高曲率，睫毛不可靠
- 写入文档：`全流程文档\03_技术难点分析.md`

### 调研5：眼球牙齿处理
- MetaHuman BaseMesh直接分析（24,403顶点，47,901面）
- 眼眶有内壁网格（左眼386个内向面，右眼409个，深度15-26mm）
- 嘴唇内侧有网格（4,621个内向面），口腔有内壁（2,437个内向面，深40mm）
- 眼球/牙齿是独立部件，wrap前删除AI高模的眼球，wrap后单独导入标准模板

### 调研6：中线edge loop要求
- Blender Mirror Modifier官方文档：中轴需要X=0的连续edge loop
- MetaHuman模板满足此要求
- Shrinkwrap可能拉偏中线顶点，wrap过程中需约束X=0归零

### 调研7：Pose问题（T-pose vs A-pose）
- Mixamo要求T-pose，MetaHuman使用A-pose
- 拍照模板：T-pose（双臂水平伸直，双腿肩宽，正面朝前，中性表情）
- 面部：正面朝前，中性表情（ARKit要求）

### 调研8：ZBrush Smart ReSym原理
- 参考文档：`test_mirror\zbrush智能对称调研.md`
- 核心：从中轴种子出发，沿边BFS，两侧走相同步数的顶点自动配对
- 只改顶点坐标，不动UV
- Maxon官方文档确认：SmartReSym只操作顶点位置，UV不受影响

### 调研9：Blender MCP通信验证
- 确认AI可通过MCP协议控制Blender执行Python脚本
- 读取场景状态、获取报错信息

## 头部wrap原型验证（fit_v3.py）

- 文件：`test01\scripts\pipeline\fit_v3.py`
- 输入：Scan_Head_Lv5.obj（297万顶点）+ MH_Head_01.obj（8,280顶点）
- 方法：MediaPipe 478面部特征点→2D→3D映射→Procrustes对齐→Shrinkwrap 4轮→锚定迭代25轮→表面修正
- 结果：精度0.4mm均值，96.2%<1mm，眼对称0.04mm，嘴对称0.75mm
- 已知问题：耳朵偏小，上唇扭曲，内眼角拉伸，鼻翼错位，颈部锯齿

## 镜像对称测试（test_mirror中12轮）

详见 `总结_v2_镜像对称测试.md`。核心结论：bmesh只改vert.co完全不动UV（差异0.0验证），但拓扑不对称模型匹配率天花板74.4%，Blender Python无法复刻ZBrush的Smart ReSym。

## 最终文档（全流程文档/）

docx格式，v5.0，含9章：项目概述→路线选型→核心方案(MetaHuman全身wrap)→技术挑战→全流程方案→AI控制→交付→风险→总结。

## 未完成项

- ❌ 全身wrap未实现（仅头部验证）
- ❌ 衣服去除未实现
- ❌ 头发去除未实现
- ❌ 镜像对称无法在Blender中完美实现
- ❌ 工期21周太长，领导不接受

## 关键API/技术备忘

- bmesh: vert.co和UV layer是独立数据层，改vert.co不动UV
- foreach_get/foreach_set批量读写：`uv.foreach_get("vector", flat_array)` 和 `uv.foreach_set("vector", flat_array)`
- Blender 5.1: `foreach_get`不支持`"x"`/`"y"`属性名，必须用`"vector"`
- `--factory-startup`禁用户插件，需要用`--background`时加
- scipy可直接在Blender Python中使用（Blender 5.1内置numpy但scipy需检查）
- Blender 5.1内置Python 3.11，某些新语法可用

## 关键技术细节补充（来自pipeline实战）

### 坐标系差异（关键Bug）
- 扫描和模板的Z轴零点差149mm：扫描Z[-134,+134]mm（几何中心），模板Z[-89,+283]mm（脖子位置）
- 不能用质心对齐，必须用特征点Procrustes对齐
- 此Bug导致v1/v2的"嘴巴和下巴完全错位"

### Procrustes对齐修复
- 特征点质心平移+距离比缩放+再平移→质量从0.444mm→0.372mm，<1mm从94.4%→97.1%

### No-Pullback Bug（最难发现的Bug）
- 表面修正后直接`v.co = tgt`跳回锚点→464/8280顶点扭曲（眉/鼻/嘴）
- 修复：不用pullback，只用Laplacian平滑，信任Shrinkwrap而非raycast

### SVD旋转对齐失败
- 12个特征点太稀疏+共面，旋转矩阵放大MediaPipe误差→13.6mm误差
- 规则：只用平移+均匀缩放，不要旋转

### Blender单位系统
- **内部单位是米，不是毫米**。阈值0.5mm应写为0.0005
- 此Bug导致诊断脚本认为"所有顶点都在10mm内"（实际是10米）

### NumPy 2.0 pitfall
- `ndarray.ptp()`在NumPy 2.0+中移除，用`np.ptp(arr)`代替
- Blender 5.1内置NumPy 2.3.4，此Bug导致脚本静默失败

### BVH ray_cast API
- 只接受位置参数，不支持关键字参数：`bvh.ray_cast(origin, direction, distance)`（正确）

### 版本历史
- v3.4-laplacian：0.402mm/96.2%/178自相交（当前推荐）
- 选型：NEAREST_SURFACEPOINT（安全，保对称），PROJECT（破坏对称，12mm眼偏移）