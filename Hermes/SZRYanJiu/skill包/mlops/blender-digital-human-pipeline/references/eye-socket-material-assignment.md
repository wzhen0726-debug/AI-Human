# Eye Socket Material Assignment — v44tag 拓扑标记是唯一权威

眼窝碗面赋独立材质（供 QR `UseMaterialIds` 沿 rim 布线）的正确做法与历次弯路。

## 权威做法：读 `v44tag` 层，零几何猜测

`make_eye_cup` 从 rim 开放边界环（ring0）重建碗面时，已给每个新建碗面打上 bmesh
per-face int 层 `v44tag_<side>`（值 2=碗面，1=倒角带，0=皮肤；见 socket_ops.py 建面处
`_nf[tag_l] = 2`），且**该层随 .blend 持久化**（`me.attributes["v44tag_L"]` 可读）。
这批面从 rim 环长出来，**材质边界天然就是 rim**——这是最准确的碗面身份标识。

```python
tagL = np.zeros(n, np.int32); me.attributes["v44tag_L"].data.foreach_get("value", tagL)
tagR = np.zeros(n, np.int32); me.attributes["v44tag_R"].data.foreach_get("value", tagR)
sock = np.where((tagL == 2) | (tagR == 2))[0]   # 这就是全部碗面，不用任何投影/深度
```

校验（assign_socket_material.py 末尾自带）：碗面连通块应=2（左右各一）；材质边界边数
应≈rim 环顶点数（干净贴合时远小于几何猜法的值）。

## 弯路（勿再走）：用几何投影事后重猜哪些是碗面

旧版 assign 用「面心 XZ 投影 point-in-polygon（对手描 rim）+ SVD 拟合 rim 平面 depth +
3D 距 rim 折线」判定。三个维度全都不可靠，根因是**手描 rim 轮廓 ≠ ring0**：

- 手描 rim 是**眼睑缘（皮肤最前方）**，ring0 是删面后网格的真实开放边界，两者位置有差。
- XZ pip 当闸门：眼窝碗口沿翻出 rim 的 XZ 包围（眼球是球，碗口比眼睑开口大），pip 把
  这批碗内面（depth>0）全部漏判 → 用户见"红色收窄到碗底、口沿被灰色侵入"。
- SVD rim 平面 depth 判溢出：碗口沿第 0~3 层刚好贴在平面附近，略低于平面即被误判成
  "rim 前方皮肤"。实测 depth<-TOL 的面按拓扑层级分布在第 0-8 层（碗口沿→碗壁上部），
  depth 中位从第 0 层 +0.6mm 单调升到碗底 +16mm——**完美的碗形梯度，全是正常碗面**。

规则：**只要 v44tag 层在，就用它；任何「用轮廓/平面/距离重算碗面归属」的方案都是
在拿一个近似基准去猜一个已有精确答案的问题。**

## 别去「修」ring0 的 Y

`make_eye_cup` 的径向投影（socket_ops.py）只把 ring0 顶点在 XZ 平面拉到手描轮廓半径，
**不调 Y（前后深度）——这是对的**。ring0 的 Y 是碗深基准（`rim_y = mean(ring0.y)`，
碗面下沉深度从它起算）。若把 ring0 的 Y 硬对齐到手描 rim 的 Y（皮肤最前方），会破坏
碗深基准且让 ring0 不再共面 → **整碗外翻凸出眼眶**。诊断出的「ring0 下睑顶点比手描
rim 前移 N mm」不是缺陷，是碗口过渡面的正常位置，不要用投影去掰。

## QR 后低模上的"溢出"多判

- vision 在低模（QR 后 14 万四边面）上反复误报：把四边面马赛克边界读成"破碎锯齿/裂口"，
  把碗口下缘正常延伸读成"水平溢出条纹"，把取景到画面边缘读成"溢出到脸颊"。
- 定量反驳口径（在 QR 检查副本上算）：真溢出 = `depth<-1mm 且 dmin>2mm` 的面数，应为 0；
  红面连通块应=2 且左右 X 区间不重叠。两个都过就是干净的，别被 vision 在低模上的描述带偏。
- xremesh 对同一输入会偶发 0xC0000005 崩溃（中途某百分比死掉，retopo.fbx 不生成）——
  **原样重试一次**即可，同输入两次结果不同是引擎偶发，不是分区/网格问题。

## 相关

- 眼窝 rim 轮廓/松弛/径向投影：`eye-socket-rim-relaxation-projection.md`
- QR 材质 ID 引导布线总流程：`qr-material-id-uv-joint-workflow.md`
