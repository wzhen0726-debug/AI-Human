"""PyWrap Bridge - Blender 插件.

与 PyWrap(Wrap4D 风格包裹工具) 协同:
- 一键导出 基础网格/扫描网格 到交换目录 (世界坐标, 保留 UV, 顶点序一致)
- 在 Blender 编辑模式按顺序选点, 导出为包裹控制点对
- 导入包裹结果 / 应用为形态键 / 原地替换网格(保留骨骼蒙皮修改器)
- 形态键批量 Delta 迁移到包裹结果 (数字人表情迁移)
- 一键启动 PyWrap

安装: Blender -> 编辑 -> 偏好设置 -> 插件 -> 安装 -> 选择本文件 -> 勾选 "PyWrap Bridge"
"""

bl_info = {
    "name": "PyWrap Bridge",
    "author": "PyWrap",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "3D 视口侧栏 > PyWrap",
    "description": "与 PyWrap 包裹工具的数据桥接",
    "category": "Import-Export",
}

import json
import os
import subprocess
import sys

import bmesh
import bpy
from mathutils import Vector

PROP_DIR = "pywrap_exchange_dir"
PROP_BASE_VIDS = "pywrap_base_vids"
PROP_TARGET_VIDS = "pywrap_target_vids"
PROP_BASE_NAME = "pywrap_base_name"
PROP_TARGET_NAME = "pywrap_target_name"


# ---------------- 工具 ----------------

def _default_exchange() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "blender_exchange")


def _exdir(context) -> str:
    d = context.scene.get(PROP_DIR) or _default_exchange()
    os.makedirs(d, exist_ok=True)
    return d


def _mesh_objects(context):
    return [o for o in context.scene.objects if o.type == "MESH"]


def write_obj_world(obj, path: str):
    """以世界坐标写出 OBJ, 保留 UV (顶点顺序 = mesh.vertices 顺序)."""
    M = obj.matrix_world
    mesh = obj.data
    uv_layer = mesh.uv_layers.active
    v_lines, vt_lines, f_lines = [], [], []
    for v in mesh.vertices:
        w = M @ v.co
        v_lines.append(f"v {w.x:.6f} {w.y:.6f} {w.z:.6f}")
    for poly in mesh.polygons:
        toks = []
        for li in poly.loop_indices:
            vi = mesh.loops[li].vertex_index + 1
            if uv_layer is not None:
                uv = uv_layer.data[li].uv
                vt_lines.append(f"vt {uv.x:.6f} {uv.y:.6f}")
                toks.append(f"{vi}/{len(vt_lines)}")
            else:
                toks.append(str(vi))
        f_lines.append("f " + " ".join(toks))
    with open(path, "w", encoding="utf-8") as f:
        f.write("# PyWrap bridge export\n")
        f.write("\n".join(v_lines + vt_lines + f_lines) + "\n")


def write_obj_from_world_verts(verts, faces, path: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# PyWrap bridge export\n")
        for w in verts:
            f.write(f"v {w.x:.6f} {w.y:.6f} {w.z:.6f}\n")
        for face in faces:
            f.write("f " + " ".join(str(i + 1) for i in face) + "\n")


def read_obj(path: str):
    """读取 OBJ 顶点(世界坐标)与面(v 索引). 返回 (verts, faces)."""
    verts, faces = [], []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                verts.append(Vector(tuple(float(x) for x in line.split()[1:4])))
            elif line.startswith("f "):
                idx = []
                for tok in line.split()[1:]:
                    v = int(tok.split("/")[0])
                    idx.append(v - 1 if v > 0 else len(verts) + v)
                faces.append(idx)
    return verts, faces


def _active_mesh(context):
    obj = context.object
    if obj is None or obj.type != "MESH":
        return None
    return obj


def _record_selected_vids(obj) -> list[int]:
    bm = bmesh.from_edit_mesh(obj.data)
    vids = [v.index for v in bm.select_history if isinstance(v, bmesh.types.BMVert)]
    if not vids:
        vids = [v.index for v in bm.verts if v.select]
    return vids


# ---------------- 操作符 ----------------

class PYWRAP_OT_export_base(bpy.types.Operator):
    bl_idname = "pywrap.export_base"
    bl_label = "导出为基础网格 base.obj"
    bl_description = "把当前网格物体以世界坐标导出到交换目录 base.obj (保留UV)"

    def execute(self, context):
        obj = _active_mesh(context)
        if obj is None:
            self.report({"ERROR"}, "请先选中一个网格物体")
            return {"CANCELLED"}
        path = os.path.join(_exdir(context), "base.obj")
        write_obj_world(obj, path)
        context.scene[PROP_BASE_NAME] = obj.name
        self.report({"INFO"}, f"已导出 {obj.name} -> {path}")
        return {"FINISHED"}


class PYWRAP_OT_export_target(bpy.types.Operator):
    bl_idname = "pywrap.export_target"
    bl_label = "导出为扫描网格 target.obj"
    bl_description = "把当前网格物体以世界坐标导出到交换目录 target.obj"

    def execute(self, context):
        obj = _active_mesh(context)
        if obj is None:
            self.report({"ERROR"}, "请先选中一个网格物体")
            return {"CANCELLED"}
        path = os.path.join(_exdir(context), "target.obj")
        write_obj_world(obj, path)
        context.scene[PROP_TARGET_NAME] = obj.name
        self.report({"INFO"}, f"已导出 {obj.name} -> {path}")
        return {"FINISHED"}


class PYWRAP_OT_record_base_points(bpy.types.Operator):
    bl_idname = "pywrap.record_base_points"
    bl_label = "记录选点为【基础】控制点"
    bl_description = "编辑模式下按点击顺序记录选中顶点索引(使用选择历史)"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.mode == "EDIT"

    def execute(self, context):
        vids = _record_selected_vids(context.object)
        if not vids:
            self.report({"ERROR"}, "没有选中的顶点")
            return {"CANCELLED"}
        context.scene[PROP_BASE_VIDS] = vids
        self.report({"INFO"}, f"已记录 {len(vids)} 个基础控制点")
        return {"FINISHED"}


class PYWRAP_OT_record_target_points(bpy.types.Operator):
    bl_idname = "pywrap.record_target_points"
    bl_label = "记录选点为【扫描】控制点"
    bl_description = "编辑模式下按点击顺序记录选中顶点索引(使用选择历史)"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.mode == "EDIT"

    def execute(self, context):
        vids = _record_selected_vids(context.object)
        if not vids:
            self.report({"ERROR"}, "没有选中的顶点")
            return {"CANCELLED"}
        context.scene[PROP_TARGET_VIDS] = vids
        self.report({"INFO"}, f"已记录 {len(vids)} 个扫描控制点")
        return {"FINISHED"}


class PYWRAP_OT_export_points(bpy.types.Operator):
    bl_idname = "pywrap.export_points"
    bl_label = "导出控制点对 points.json"
    bl_description = "按记录顺序把 基础/扫描 顶点索引配对并写出 points.json"

    def execute(self, context):
        b = list(context.scene.get(PROP_BASE_VIDS, []))
        t = list(context.scene.get(PROP_TARGET_VIDS, []))
        n = min(len(b), len(t))
        if n == 0:
            self.report({"ERROR"}, "请先分别记录基础/扫描控制点")
            return {"CANCELLED"}
        if len(b) != len(t):
            self.report({"WARNING"}, f"两侧点数不同({len(b)}/{len(t)}), 按较少侧截断")
        data = {"format": "vids",
                "base_vids": b[:n], "target_vids": t[:n],
                "names": [f"P{i+1}" for i in range(n)]}
        path = os.path.join(_exdir(context), "points.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.report({"INFO"}, f"已导出 {n} 对控制点 -> {path}")
        return {"FINISHED"}


class PYWRAP_OT_launch(bpy.types.Operator):
    bl_idname = "pywrap.launch"
    bl_label = "启动 PyWrap"
    bl_description = "启动 PyWrap 包裹工具 (自动加载交换目录数据)"

    def execute(self, context):
        main_py = os.path.join(os.path.dirname(_default_exchange()), "main.py")
        if not os.path.isfile(main_py):
            self.report({"ERROR"}, f"未找到 PyWrap 入口: {main_py}")
            return {"CANCELLED"}
        kwargs = {"cwd": os.path.dirname(main_py)}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        try:
            subprocess.Popen(["python", main_py], **kwargs)
        except Exception as e:
            self.report({"ERROR"}, f"启动失败: {e}")
            return {"CANCELLED"}
        self.report({"INFO"}, "PyWrap 已启动")
        return {"FINISHED"}


class PYWRAP_OT_import_result(bpy.types.Operator):
    bl_idname = "pywrap.import_result"
    bl_label = "导入包裹结果为新物体"
    bl_description = "把交换目录 wrapped.obj 导入为新网格物体"

    def execute(self, context):
        path = os.path.join(_exdir(context), "wrapped.obj")
        if not os.path.isfile(path):
            self.report({"ERROR"}, f"未找到 {path}, 请先在 PyWrap 中包裹并导出")
            return {"CANCELLED"}
        verts, faces = read_obj(path)
        mesh = bpy.data.meshes.new("pywrap_wrapped")
        mesh.from_pydata([tuple(v) for v in verts], [], faces)
        mesh.update()
        obj = bpy.data.objects.new("pywrap_wrapped", mesh)
        context.scene.collection.objects.link(obj)
        context.view_layer.objects.active = obj
        obj.select_set(True)
        self.report({"INFO"}, f"已导入 {len(verts)} 顶点")
        return {"FINISHED"}


def _find_base_obj(context):
    name = context.scene.get(PROP_BASE_NAME, "")
    obj = bpy.data.objects.get(name) if name else None
    if obj is None:
        obj = _active_mesh(context)
    return obj


class PYWRAP_OT_apply_shape_key(bpy.types.Operator):
    bl_idname = "pywrap.apply_shape_key"
    bl_label = "结果应用为形态键 (Shape Key)"
    bl_description = "在基础物体上新建形态键, 顶点位置取包裹结果 (世界坐标换算回局部)"

    def execute(self, context):
        path = os.path.join(_exdir(context), "wrapped.obj")
        obj = _find_base_obj(context)
        if obj is None or not os.path.isfile(path):
            self.report({"ERROR"}, "缺少基础物体或 wrapped.obj")
            return {"CANCELLED"}
        verts, _ = read_obj(path)
        if len(verts) != len(obj.data.vertices):
            self.report({"ERROR"},
                        f"顶点数不一致: 结果{len(verts)} vs 基础{len(obj.data.vertices)}")
            return {"CANCELLED"}
        if obj.data.shape_keys is None:
            obj.shape_key_add(name="Basis", from_mix=False)
        Minv = obj.matrix_world.inverted()
        sk = obj.shape_key_add(name="PyWrap_Wrapped", from_mix=False)
        for i, w in enumerate(verts):
            sk.data[i].co = Minv @ w
        self.report({"INFO"}, "已添加形态键 PyWrap_Wrapped")
        return {"FINISHED"}


class PYWRAP_OT_replace_mesh(bpy.types.Operator):
    bl_idname = "pywrap.replace_mesh"
    bl_label = "结果替换网格 (保留骨骼/蒙皮/UV/修改器)"
    bl_description = "把基础物体顶点坐标原地替换为包裹结果, 物体层级/骨骼/权重不变"

    def execute(self, context):
        path = os.path.join(_exdir(context), "wrapped.obj")
        obj = _find_base_obj(context)
        if obj is None or not os.path.isfile(path):
            self.report({"ERROR"}, "缺少基础物体或 wrapped.obj")
            return {"CANCELLED"}
        verts, _ = read_obj(path)
        if len(verts) != len(obj.data.vertices):
            self.report({"ERROR"},
                        f"顶点数不一致: 结果{len(verts)} vs 基础{len(obj.data.vertices)}")
            return {"CANCELLED"}
        Minv = obj.matrix_world.inverted()
        for i, w in enumerate(verts):
            obj.data.vertices[i].co = Minv @ w
        obj.data.update()
        self.report({"INFO"}, f"{obj.name} 网格已替换 (骨骼/蒙皮保留)")
        return {"FINISHED"}


class PYWRAP_OT_transfer_shape_keys(bpy.types.Operator):
    bl_idname = "pywrap.transfer_shape_keys"
    bl_label = "形态键批量迁移到结果 (Delta Transfer)"
    bl_description = "把基础物体上的所有形态键按 delta 迁移到包裹结果物体上"

    def execute(self, context):
        src = _find_base_obj(context)
        dst = bpy.data.objects.get("pywrap_wrapped")
        if src is None or dst is None:
            self.report({"ERROR"}, "需要基础物体与已导入的 pywrap_wrapped 物体")
            return {"CANCELLED"}
        if src.data.shape_keys is None or len(src.data.shape_keys.key_blocks) < 2:
            self.report({"ERROR"}, "基础物体没有形态键")
            return {"CANCELLED"}
        if len(src.data.vertices) != len(dst.data.vertices):
            self.report({"ERROR"}, "两物体顶点数不一致")
            return {"CANCELLED"}
        if dst.data.shape_keys is None:
            dst.shape_key_add(name="Basis", from_mix=False)
        s_basis = src.data.shape_keys.reference_key
        d_basis = dst.data.shape_keys.reference_key
        M3s = src.matrix_world.to_3x3()
        M3d_inv = dst.matrix_world.to_3x3().inverted()
        n_src = len(src.data.vertices)
        count = 0
        for kb in src.data.shape_keys.key_blocks:
            if kb == s_basis:
                continue
            new_kb = dst.shape_key_add(name=kb.name, from_mix=False)
            for i in range(n_src):
                delta_w = M3s @ (kb.data[i].co - s_basis.data[i].co)
                new_kb.data[i].co = d_basis.data[i].co + M3d_inv @ delta_w
            count += 1
        self.report({"INFO"}, f"已迁移 {count} 个形态键到 {dst.name}")
        return {"FINISHED"}


class PYWRAP_OT_export_shapes(bpy.types.Operator):
    bl_idname = "pywrap.export_shapes"
    bl_label = "导出形态键序列 shapes/*.obj"
    bl_description = "把基础物体的每个形态键以世界坐标导出为独立 OBJ (供 PyWrap 批量迁移)"

    def execute(self, context):
        obj = _find_base_obj(context)
        if obj is None or obj.data.shape_keys is None:
            self.report({"ERROR"}, "基础物体没有形态键")
            return {"CANCELLED"}
        M = obj.matrix_world
        faces = [tuple(p.vertices) for p in obj.data.polygons]
        out_dir = os.path.join(_exdir(context), "shapes")
        os.makedirs(out_dir, exist_ok=True)
        basis = obj.data.shape_keys.reference_key
        count = 0
        for kb in obj.data.shape_keys.key_blocks:
            if kb == basis:
                continue
            verts = [M @ kb.data[i].co for i in range(len(obj.data.vertices))]
            write_obj_from_world_verts(verts, faces,
                                       os.path.join(out_dir, f"{kb.name}.obj"))
            count += 1
        self.report({"INFO"}, f"已导出 {count} 个形态键到 {out_dir}")
        return {"FINISHED"}


class PYWRAP_OT_open_dir(bpy.types.Operator):
    bl_idname = "pywrap.open_dir"
    bl_label = "打开交换目录"
    bl_description = "在文件管理器中打开交换目录"

    def execute(self, context):
        d = _exdir(context)
        if sys.platform == "win32":
            os.startfile(d)
        else:
            subprocess.Popen(["xdg-open", d])
        return {"FINISHED"}


# ---------------- 面板 ----------------

class PYWRAP_PT_panel(bpy.types.Panel):
    bl_label = "PyWrap 桥接"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PyWrap"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.prop(scene, f'["{PROP_DIR}"]', text="交换目录") \
            if scene.get(PROP_DIR) else layout.label(text=f"交换目录: {_default_exchange()}")

        box = layout.box()
        box.label(text="① 导出到 PyWrap", icon="EXPORT")
        box.operator("pywrap.export_base")
        box.operator("pywrap.export_target")

        box = layout.box()
        box.label(text="② 控制点对 (编辑模式选点)", icon="VERTEXSEL")
        box.operator("pywrap.record_base_points")
        box.operator("pywrap.record_target_points")
        b = len(scene.get(PROP_BASE_VIDS, []))
        t = len(scene.get(PROP_TARGET_VIDS, []))
        box.label(text=f"已记录: 基础 {b} 点 / 扫描 {t} 点")
        box.operator("pywrap.export_points")

        box = layout.box()
        box.label(text="③ 包裹", icon="MOD_MESHDEFORM")
        box.operator("pywrap.launch")

        box = layout.box()
        box.label(text="④ 结果回导", icon="IMPORT")
        box.operator("pywrap.import_result")
        box.operator("pywrap.apply_shape_key")
        box.operator("pywrap.replace_mesh")
        box.operator("pywrap.transfer_shape_keys")
        box.operator("pywrap.export_shapes")

        layout.operator("pywrap.open_dir", icon="FILE_FOLDER")


CLASSES = [
    PYWRAP_OT_export_base, PYWRAP_OT_export_target,
    PYWRAP_OT_record_base_points, PYWRAP_OT_record_target_points,
    PYWRAP_OT_export_points, PYWRAP_OT_launch,
    PYWRAP_OT_import_result, PYWRAP_OT_apply_shape_key,
    PYWRAP_OT_replace_mesh, PYWRAP_OT_transfer_shape_keys,
    PYWRAP_OT_export_shapes, PYWRAP_OT_open_dir,
    PYWRAP_PT_panel,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
