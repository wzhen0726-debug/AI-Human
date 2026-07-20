# ZBrush 智能网格对称（Smart ReSym）原理、开源方案及代码实现

在不破坏**顶点索引（Topology/Vertex ID）**和 **UV** 的前提下，只通过空间几何计算，将未遮罩区域的“拓扑对称点”强行拉到和遮罩区域对称的位置。

---

## 一、 ZBrush 智能网格对称的底层原理

传统的“镜像（Mirror）”是直接切掉一半网格、复制并缝合另一半，这会**彻底摧毁原始的 UV 和顶点顺序**。而“智能对称”的核心在于**“只移动坐标，不改变结构”**，其逻辑分为三个核心步骤：

### 1. 建立拓扑对称映射表（Topology Mapping）
这是最关键的一步。软件不能只看空间坐标（因为模型可能已经雕刻变形或姿态不对），它必须通过**网格拓扑连接关系（边和面的走向）**来寻找左边顶点 $A$ 在右边的“孪生兄弟”顶点 $A'$。

* **步骤**：
  1. 算法首先从对称轴（如 $X=0$）上的边缘点（种子点）开始。
  2. 沿着边向两侧同时进行“广度优先（BFS）”式扩散搜寻。
  3. 如果左侧走 $N$ 条边能到达一个顶点，右侧沿着镜像方向走 $N$ 条边也能到达一个对应的点，那么这两个点就被绑定为**对称点对 (Symmetric Pair)**。
* **结果**：生成一个映射表 `SymmetricPair[左点ID] = 右点ID`。因为这个过程只读取拓扑，**不改变顶点索引和数量，所以 UV 毫发无损**。

### 2. 遮罩权重过滤（Mask Weighting）
当你在模型某一边绘制了遮罩（Mask）时，软件会根据遮罩值（0.0 ~ 1.0）分配权重：
* **被遮罩的顶点（权重 = 1）**：位置绝对锁定，作为“源数据（Source）”。
* **未被遮罩的顶点（权重 = 0）**：作为“目标数据（Target）”，准备被强制修改。
* **边缘过渡带（权重 0~1）**：用于进行线性或平滑插值，防止拉伸断裂。

### 3. 几何空间镜像与坐标传递
遍历所有未遮罩（或低遮罩）的点，根据映射表找到它在另一侧的“兄弟点”，并将其坐标进行轴向取反（以 $X$ 轴对称面为例）：

$$P_{target} = \text{Mirror}_{X=0}(P_{source})$$

---

## 二、 开源方案与可借鉴的替代

在开源界，这个技术通常被称为 **"Topology-Based Mesh Symmetry"（基于拓扑的网格对称）** 或 **"Symmetry Mapping"**。

### 1. Blender 源码（最佳 C++/Python 参考）
Blender 自带的拓扑对称功能极为成熟（例如网格的 `Snap to Symmetry` 或权重刷子的 `Mirror`）。
* **核心源码位置**：在 Blender 源码中查找 `mesh_symmetry.cc` 或 `blenkernel/intern/mesh_remap.c`。
* **原理**：Blender 使用了一种基于**“初始对称轴边界寻找 + 拓扑图遍历”**的算法。它是完全开源的（GPL 协议），非常适合作为底层算法参考。

### 2. OpenMesh / MeshLab (C++ 几何库)
如果你在写自己的 C++ 3D 软件，建议使用已有的半边网格数据结构：
* **OpenMesh** 提供了极佳的循环器（Circulators），可以让你轻松通过一个顶点找到它周围相连的边、面和邻接点。利用 OpenMesh 可以非常快速地写出拓扑配对算法。

---

## 三、 核心算法伪代码实现

你可以分两步在自己的软件中实现该功能：

### 第一步：生成对称映射表（离线计算或缓存）

```python
def generate_symmetry_map(mesh):
    sym_map = {}  # 格式: {left_v_id: right_v_id}
    visited = set()
    
    # 1. 寻找并在对称轴（如 X=0）附近的点作为种子对
    seed_pairs = find_initial_boundary_pairs(mesh) 
    
    # 2. 广度优先搜索 (BFS) 扩散整个网格
    queue = deque(seed_pairs)  # 队列里存的是一对对的点 (left_v, right_v)
    
    while queue:
        left_v, right_v = queue.popleft()
        
        # 获取两边顶点的邻接点
        left_neighbors = mesh.get_neighbors(left_v)
        right_neighbors = mesh.get_neighbors(right_v)
        
        # 核心：根据相对空间方位（如镜像后的几何位置最接近），配对邻接点
        for lv_next in left_neighbors:
            if lv_next in visited: 
                continue
            
            # 寻找右侧邻接点中，空间镜像后离 lv_next 最近的那一个
            rv_next = find_best_mirror_match(lv_next, right_neighbors)
            
            if rv_next and rv_next not in visited:
                sym_map[lv_next] = rv_next
                sym_map[rv_next] = lv_next
                visited.add(lv_next)
                visited.add(rv_next)
                queue.append((lv_next, rv_next))
                
    return sym_map
	
	
 第二步：根据遮罩应用智能对称（实时执行）
 
 
 def apply_smart_resym(mesh, sym_map, mask_array):
    # mask_array 存储每个点的遮罩值，1.0 表示完全锁定，0.0 表示完全未锁定
    
    for v_id in range(len(mesh.vertices)):
        # 如果这个点有对称点，且它自己没有被完全遮罩（需要被动改变）
        if v_id in sym_map and mask_array[v_id] < 1.0:
            source_v_id = sym_map[v_id]
            
            # 只有当它的兄弟节点被遮罩保护（或遮罩值比它高）时，才从兄弟节点拷贝坐标
            if mask_array[source_v_id] > mask_array[v_id]:
                source_pos = mesh.vertices[source_v_id].position
                target_pos = mesh.vertices[v_id].position
                
                # 计算镜像后的理想位置（以 X 轴为对称面为例）
                mirrored_pos = Vector3(-source_pos.x, source_pos.y, source_pos.z)
                
                # 根据两边遮罩差值进行线性插值（Lerp），防止边缘硬拉伸
                weight = mask_array[source_v_id] - mask_array[v_id]
                final_pos = lerp(target_pos, mirrored_pos, weight)
                
                # 核心：只更新坐标，不碰拓扑结构，UV 自动保留
                mesh.vertices[v_id].position = final_pos
				
				
四、 开发避坑指南
1.绝对不要动 Index：在对齐坐标时，直接覆盖 vertex.position 即可。由于顶点和三角面索引完全没变，你的 UV（绑定在 Loop 或 Vertex 上）会自然保持完美。

2.容错处理：现实中用户的模型拓扑不一定绝对对称（可能存在三角面、五边面混杂，或者局部破损）。在拓扑配对时，如果发现左边有 4 个邻点而右边只有 3 个（拓扑破损），算法必须能够安全退出并跳过该区域，避免死循环或崩溃。