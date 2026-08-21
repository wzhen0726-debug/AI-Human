# -*- coding: utf-8 -*-
"""眼睛颜色选择面板 — 在Blender侧边栏(N面板)选择眼睛颜色.

使用方法(3步):
1. 打开已摆好眼球的blend文件 (如 01_2_eyeball_placed.blend)
2. 本文件注册后, 在3D视图按 N 键打开侧边栏, 选 "眼睛颜色" 标签
3. 选择颜色 + 血丝程度, 点击 "应用眼睛颜色" 按钮, 然后保存文件

也可命令行使用(管线自动调用):
  blender -b 文件.blend --python set_eye_color.py -- 棕色 中
  颜色可选: 蓝色/棕色/绿色/榛色/红色/紫色/丧尸  (或英文 Blue/Brown/Green/Hazel/Red/Violet/Zombie)
  血丝可选: 无/中/重 (或 base/Bld1/Bld2)
"""
import bpy, os, json, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(SCRIPT_DIR, "eye002_colors.json")

# 中英文对照
COLOR_CN = {"蓝色": "Blue", "棕色": "Brown", "绿色": "Green", "榛色": "Hazel",
            "红色": "Red", "紫色": "Violet", "丧尸": "Zombie"}
COLOR_EN = {v: k for k, v in COLOR_CN.items()}
BLOOD_CN = {"无": "base", "中": "Bld1", "重": "Bld2"}
BLOOD_EN = {v: k for k, v in BLOOD_CN.items()}

def apply_color(color_cn, blood_cn):
    """把指定颜色应用到场景内所有Eye002对象. 返回替换的贴图节点数."""
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    color = COLOR_CN.get(color_cn, color_cn)
    blood = BLOOD_CN.get(blood_cn, blood_cn)
    variants = reg["colors"].get(color)
    if not variants:
        raise ValueError(f"没有这个颜色: {color_cn}")
    if blood not in variants:
        blood = "base"   # 丧尸色只有"无血丝"
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

# ---------------- Blender GUI 面板 ----------------
class EYE_PT_ColorPanel(bpy.types.Panel):
    bl_label = "眼睛颜色"
    bl_idname = "EYE_PT_ColorPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "眼睛颜色"

    def draw(self, context):
        layout = self.layout
        props = context.scene.eye_color_props
        layout.label(text="选择眼睛外观:")
        layout.prop(props, "color", text="虹膜颜色")
        layout.prop(props, "bloodline", text="血丝程度")
        layout.operator("eye.apply_color", text="应用眼睛颜色", icon='RESTRICT_COLOR_OFF')
        layout.label(text="应用后记得保存文件(Ctrl+S)", icon='INFO')

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
        self.report({'INFO'}, f"已应用: {props.color} / 血丝({props.bloodline}), {n_eyes}只眼")
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
    # 命令行模式: blender -b file.blend --python set_eye_color.py -- 颜色 血丝
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
        color = args[0] if args else "榛色"
        blood = args[1] if len(args) > 1 else "无"
        swapped, n_eyes, blood_used = apply_color(color, blood)
        print(f"已应用: {color}/{blood_used} → {n_eyes}只眼, {swapped}个贴图节点")
        bpy.ops.wm.save_mainfile()
        print(f"已保存: {bpy.data.filepath}")
    else:
        register()
