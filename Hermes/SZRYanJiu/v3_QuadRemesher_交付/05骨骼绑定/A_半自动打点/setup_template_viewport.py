"""打点模板视口配置 v2: 打开即可用.
视口参数(已验证可持久化): 材质预览+3m视野+身体中心+正视+正交.
移动工具: -b后台无法设置工具状态, 用场景内中文文字牌提示按G切换.
"""
import bpy, os
from mathutils import Vector, Quaternion

# 正视全身: 模型1.80m, 中心(0,0,0.9), 视距3.0正交 → 全身完整可见
FRONT_ROT = Quaternion((0.7071, 0.7071, 0.0, 0.0))
CENTER = Vector((0, 0, 0.9))
DIST = 3.0

for ws in bpy.data.workspaces:
    for scr in ws.screens:
        for area in scr.areas:
            if area.type != 'VIEW_3D':
                continue
            for sp in area.spaces:
                if sp.type != 'VIEW_3D':
                    continue
                sp.shading.type = 'MATERIAL'       # 材质预览(着色模式)
                sp.overlay.show_text = True        # 左上角显示视图名
                rv = sp.region_3d
                if rv:
                    rv.view_location = CENTER      # 对准身体中心
                    rv.view_distance = DIST        # 3m视野, 全身可见
                    rv.view_perspective = 'ORTHO'  # 正交, 好对齐
                    rv.view_rotation = FRONT_ROT   # 正视, 不是头顶

# 中文文字牌(照01A: 场景内3D文字, 用户打开就看到)
for o in [o for o in bpy.data.objects if o.name.startswith("打点操作提示")]:
    bpy.data.objects.remove(o, do_unlink=True)
cu = bpy.data.curves.new("打点操作提示_curve", type='FONT')
cu.body = ("打点操作提示:\n"
           "1. 按G键切换移动工具(或点左侧工具栏箭头图标)\n"
           "2. 点击彩色小球, 按G拖动到关节位置(会贴着皮肤)\n"
           "3. 只需放右侧8个点, 左侧自动镜像生成\n"
           "4. 放完按Ctrl+S保存")
cu.align_x = 'CENTER'
cu.align_y = 'CENTER'
cu.size = 0.035          # 35mm字高(3m视野内清晰可见)
cu.space_line = 1.5
FONT = r"C:\Windows\Fonts\msyh.ttc"
if os.path.exists(FONT):
    f = bpy.data.fonts.load(FONT)
    cu.font = f
    cu.font_bold = f
txt = bpy.data.objects.new("打点操作提示", cu)
txt.location = Vector((0.9, -1.2, 1.5))   # 身体右前方, 不挡模型
bpy.context.scene.collection.objects.link(txt)
print("文字牌已添加")

bpy.ops.wm.save_as_mainfile()
print("VIEWPORT_SETUP_V2_DONE")
