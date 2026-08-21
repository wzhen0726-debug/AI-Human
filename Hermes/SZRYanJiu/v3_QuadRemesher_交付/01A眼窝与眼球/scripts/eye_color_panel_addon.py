# -*- coding: utf-8 -*-
"""眼睛颜色选择面板(常驻插件版) — 安装后打开任何blend都能用.
3D视图按N键 → 侧边栏"眼睛颜色"标签 → 选颜色+血丝 → 点"应用眼睛颜色"."""
bl_info = {
    "name": "眼睛颜色面板",
    "author": "数字人管线",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "3D视图 > 侧边栏(N) > 眼睛颜色",
    "description": "给Eye002眼球换颜色: 7色系×血丝等级, 中文界面",
    "category": "数字人管线",
}
import bpy, os, json, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 注册表: 优先用插件同目录的, 否则用管线scripts目录的
_REG_CANDIDATES = [
    os.path.join(SCRIPT_DIR, "eye002_colors.json"),
    r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\v3_QuadRemesher_交付\01A眼窝与眼球\scripts\eye002_colors.json",
]

COLOR_CN = {"蓝色": "Blue", "棕色": "Brown", "绿色": "Green", "榛色": "Hazel",
            "红色": "Red", "紫色": "Violet", "丧尸": "Zombie"}
BLOOD_CN = {"无": "base", "中": "Bld1", "重": "Bld2"}

def _load_registry():
    for p in _REG_CANDIDATES:
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    raise FileNotFoundError("找不到eye002_colors.json颜色注册表")

def apply_color(color_cn, blood_cn):
    """把指定颜色应用到场景内所有Eye002对象."""
    reg = _load_registry()
    color = COLOR_CN.get(color_cn, color_cn)
    blood = BLOOD_CN.get(blood_cn, blood_cn)
    variants = reg["colors"].get(color)
    if not variants:
        raise ValueError(f"没有这个颜色: {color_cn}")
    if blood not in variants:
        blood = "base"
    tex_path = variants[blood]
    img = bpy.data.images.load(tex_path, check_existing=True)
    img.name = os.path.basename(tex_path)

    eyes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("Eye002")]
    if not eyes:
        raise ValueError("场景里没有眼球(应存在名为Eye002_L/Eye002_R的对象)")
    swapped = 0
    for eye in eyes:
        for slot in eye.data.materials:
            if not slot or not slot.use_nodes:
                continue
            for n in slot.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image and "_D" in n.image.name:
                    n.image = img
                    swapped += 1
    return swapped, len(eyes), blood

class EYE_PT_ColorPanel(bpy.types.Panel):
    bl_label = "眼睛颜色"
    bl_idname = "EYE_PT_ColorPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "眼睛颜色"

    def draw(self, context):
        layout = self.layout
        props = context.scene.eye_color_props
        layout.label(text="第一步: 选择外观")
        layout.prop(props, "color", text="虹膜颜色")
        layout.prop(props, "bloodline", text="血丝程度")
        layout.separator()
        layout.label(text="第二步: 点击应用")
        layout.operator("eye.apply_color", text="应用眼睛颜色", icon='RESTRICT_COLOR_OFF')
        layout.label(text="应用后记得保存(Ctrl+S)", icon='INFO')

class EYE_OT_ApplyColor(bpy.types.Operator):
    bl_label = "应用眼睛颜色"
    bl_idname = "eye.apply_color"
    bl_description = "把选择的颜色和血丝程度应用到左右眼球"

    def execute(self, context):
        props = context.scene.eye_color_props
        try:
            swapped, n_eyes, blood = apply_color(props.color, props.bloodline)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f"已应用: {props.color}/血丝({props.bloodline}), {n_eyes}只眼")
        return {'FINISHED'}

class EYE_ColorProps(bpy.types.PropertyGroup):
    color: bpy.props.EnumProperty(
        items=[("蓝色","蓝色",""), ("棕色","棕色",""), ("绿色","绿色",""),
               ("榛色","榛色",""), ("红色","红色",""), ("紫色","紫色",""),
               ("丧尸","丧尸","")],
        name="虹膜颜色", default="榛色")
    bloodline: bpy.props.EnumProperty(
        items=[("无","无血丝","干净的眼白"), ("中","中等血丝","轻微血丝"),
               ("重","重血丝","明显血丝")],
        name="血丝程度", default="无")

classes = (EYE_ColorProps, EYE_PT_ColorPanel, EYE_OT_ApplyColor)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.eye_color_props = bpy.props.PointerProperty(type=EYE_ColorProps)

def unregister():
    del bpy.types.Scene.eye_color_props
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()
