# -*- coding: utf-8 -*-
"""眼球位置微调面板(常驻插件) — 半自动: 脚本按解剖规律自动摆位, 不满意可在GUI微调并保存回管线.
使用方法: 3D视图按N键 → "眼球位置"标签.
按钮说明(从上到下):
  1. 读取当前位置 — 眼球已在场景里, 先把面板滑块同步到眼球当前位置
  2. 拖滑块微调(左右眼自动同步) → 点"应用微调"看效果, 可反复调
  3. 满意后点"保存到管线" — 以后重跑脚本自动用这个位置
  4. "恢复默认位置" — 回到解剖规律计算的位置(角膜贴开口平面+虹膜底贴下睑)"""
bl_info = {
    "name": "眼球位置微调面板",
    "author": "数字人管线",
    "version": (2, 0),
    "blender": (4, 0, 0),
    "location": "3D视图 > 侧边栏(N) > 眼球位置",
    "description": "半自动微调眼球位置: 左右同步, 可保存到管线",
    "category": "数字人管线",
}
import bpy, os, json

SCRIPTS_DIR = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\scripts"
_CONTOUR_JSON = os.path.join(
    r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球",
    "screenshots", "3ddfa", "eyelid_contour_manual.json")
_MANUAL_JSON = os.path.join(SCRIPTS_DIR, "eyeball_finetune_manual.json")


def _contour():
    return json.load(open(_CONTOUR_JSON, encoding="utf-8"))


def _corneal_dist(eye):
    """角膜顶点距(对象原点≈球心, 眼球无旋转缩放)."""
    return abs(min(v.co.y for v in eye.data.vertices))


def _default_pos(side, cont):
    """解剖规律默认位(v4): 角膜贴开口平面(凸出0.1mm) + 虹膜中心在开口中心上1.4mm."""
    import eye002_config as cfg  # 需要SCRIPTS_DIR在sys.path, register时已加
    c = cont[side]["center"]
    rim_y = float(c[1])
    eye = bpy.data.objects.get(f"Eye002_{side}")
    cd = _corneal_dist(eye) if eye else 0.0153
    return [c[0], rim_y + cd - cfg.EYE_PROTRUSION_MM / 1000.0, c[2] + cfg.EYE_Z_OFFSET_MM / 1000.0]


def _load_props_from_scene(props):
    """把场景内眼球当前位置换算为滑块偏移量(相对解剖默认位)."""
    cont = _contour()
    for side in ("L", "R"):
        eye = bpy.data.objects.get(f"Eye002_{side}")
        if not eye:
            return False
    side = "R"  # 两眼同步, 读一只即可
    eye = bpy.data.objects[f"Eye002_{side}"]
    cur = eye.location
    d = _default_pos(side, cont)
    props.dx_mm = round((cur.x - d[0]) * 1000, 2)
    props.dy_mm = round((cur.y - d[1]) * 1000, 2)
    props.dz_mm = round((cur.z - d[2]) * 1000, 2)
    return True


def _apply_offset(props):
    """滑块偏移应用到两眼(相对解剖默认位, 两眼同步)."""
    cont = _contour()
    for side in ("L", "R"):
        eye = bpy.data.objects.get(f"Eye002_{side}")
        if not eye:
            return f"找不到眼球 Eye002_{side}"
        d = _default_pos(side, cont)
        eye.location = (d[0] + props.dx_mm / 1000.0,
                        d[1] + props.dy_mm / 1000.0,
                        d[2] + props.dz_mm / 1000.0)
    return None


class EYEBALL_PT_PosPanel(bpy.types.Panel):
    bl_label = "眼球位置微调"
    bl_idname = "EYEBALL_PT_PosPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "眼球位置"

    def draw(self, context):
        layout = self.layout
        props = context.scene.eyeball_pos_props
        layout.operator("eyeball.read_current", text="① 读取当前位置", icon='IMPORT')
        layout.label(text="② 拖滑块微调(毫米, 左右同步):")
        layout.prop(props, "dy_mm", text="  前后(负=往脸里收)")
        layout.prop(props, "dz_mm", text="  上下(正=往上)")
        layout.prop(props, "dx_mm", text="  左右(正=往外)")
        layout.operator("eyeball.apply_pos", text="应用微调", icon='CHECKMARK')
        layout.separator()
        layout.operator("eyeball.write_manual", text="③ 保存到管线", icon='FILE_TICK')
        layout.operator("eyeball.reset_default", text="恢复默认位置", icon='LOOP_BACK')


class EYEBALL_OT_ReadCurrent(bpy.types.Operator):
    bl_label = "读取当前位置"
    bl_idname = "eyeball.read_current"
    bl_description = "把场景内眼球的当前位置读入滑块"

    def execute(self, context):
        props = context.scene.eyeball_pos_props
        if not _load_props_from_scene(props):
            self.report({'ERROR'}, "场景里没有Eye002_L/Eye002_R眼球")
            return {'CANCELLED'}
        self.report({'INFO'}, f"已读取: 前后{props.dy_mm:+.2f} 上下{props.dz_mm:+.2f} 左右{props.dx_mm:+.2f}mm")
        return {'FINISHED'}


class EYEBALL_OT_ApplyPos(bpy.types.Operator):
    bl_label = "应用微调"
    bl_idname = "eyeball.apply_pos"
    bl_description = "把滑块偏移应用到左右眼球(同步)"

    def execute(self, context):
        props = context.scene.eyeball_pos_props
        err = _apply_offset(props)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        self.report({'INFO'}, f"已应用: 前后{props.dy_mm:+.1f} 上下{props.dz_mm:+.1f} 左右{props.dx_mm:+.1f}mm")
        return {'FINISHED'}


class EYEBALL_OT_ResetDefault(bpy.types.Operator):
    bl_label = "恢复默认位置"
    bl_idname = "eyeball.reset_default"
    bl_description = "回到解剖规律计算的位置"

    def execute(self, context):
        props = context.scene.eyeball_pos_props
        props.dx_mm = props.dy_mm = props.dz_mm = 0.0
        err = _apply_offset(props)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        self.report({'INFO'}, "已恢复解剖规律默认位置")
        return {'FINISHED'}


class EYEBALL_OT_WriteManual(bpy.types.Operator):
    bl_label = "保存到管线"
    bl_idname = "eyeball.write_manual"
    bl_description = "把当前眼球位置写为管线定案(以后重跑脚本自动用这个位置)"

    def execute(self, context):
        props = context.scene.eyeball_pos_props
        for side in ("L", "R"):
            if not bpy.data.objects.get(f"Eye002_{side}"):
                self.report({'ERROR'}, f"找不到眼球 Eye002_{side}")
                return {'CANCELLED'}
        out = {"dx_mm": round(props.dx_mm, 2), "dy_mm": round(props.dy_mm, 2),
               "dz_mm": round(props.dz_mm, 2)}
        out["_说明"] = "用户GUI手动验收的微调偏移(相对解剖规律默认位, 毫米). run_eyeball_v2.py重跑时自动加载. 删除此文件则回到纯解剖规律默认值."
        json.dump(out, open(_MANUAL_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        self.report({'INFO'}, f"已保存到管线: {os.path.basename(_MANUAL_JSON)} (偏移 x{out['dx_mm']:+.1f} y{out['dy_mm']:+.1f} z{out['dz_mm']:+.1f}mm)")
        return {'FINISHED'}


class EYEBALL_PosProps(bpy.types.PropertyGroup):
    dy_mm: bpy.props.FloatProperty(name="前后", default=0.0, min=-10, max=10, precision=2, step=5)
    dz_mm: bpy.props.FloatProperty(name="上下", default=0.0, min=-10, max=10, precision=2, step=5)
    dx_mm: bpy.props.FloatProperty(name="左右", default=0.0, min=-10, max=10, precision=2, step=5)


classes = (EYEBALL_PosProps, EYEBALL_PT_PosPanel, EYEBALL_OT_ReadCurrent,
           EYEBALL_OT_ApplyPos, EYEBALL_OT_ResetDefault, EYEBALL_OT_WriteManual)


def register():
    import sys
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.eyeball_pos_props = bpy.props.PointerProperty(type=EYEBALL_PosProps)


def unregister():
    del bpy.types.Scene.eyeball_pos_props
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
