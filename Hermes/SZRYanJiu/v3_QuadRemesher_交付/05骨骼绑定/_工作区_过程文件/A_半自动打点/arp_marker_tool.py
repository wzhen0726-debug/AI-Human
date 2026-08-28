"""ARP打点工具 (用户从0打点用): N面板按钮生成正确命名的标记球+自动镜像对侧.
用法: Scripting标签页打开本文本块 → ▶运行一次 → Layout按N → 'ARP打点'面板.
命名规范: <序号>_<中文> (主侧) / <序号>_<中文>_对侧镜像 (自动驱动跟随主侧)
每个球带自定义属性 arp_name(root_loc/chin_loc/...), 绑定脚本据此识别."""
import bpy

# ARP Smart标记体系: 名称 → 中文说明
MARKERS = [
    ("root_loc",     "01", "骨盆中心"),
    ("chin_loc",     "02", "下巴"),
    ("neck_loc",     "03", "颈根"),
    ("shoulder_loc", "04", "肩"),
    ("elbow_loc",    "05", "肘"),
    ("hand_loc",     "06", "手腕"),
    ("hand_tip_loc", "07", "指尖"),
    ("thigh_loc",    "08", "大腿根上段"),
    ("knee_loc",     "09", "膝"),
    ("foot_loc",     "10", "脚踝"),
]
SYMS = {"shoulder_loc", "elbow_loc", "hand_loc", "hand_tip_loc",
        "thigh_loc", "knee_loc", "foot_loc"}


def get_or_make_material():
    m = bpy.data.materials.get("arp_orange")
    if m is None:
        m = bpy.data.materials.new("arp_orange")
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        if b:
            b.inputs["Base Color"].default_value = (1.0, 0.55, 0.05, 1.0)
            b.inputs["Emission Color"].default_value = (1.0, 0.55, 0.05, 1.0)
            b.inputs["Emission Strength"].default_value = 0.6
    return m


def get_or_make_ball_mesh():
    key = "arp_marker_ball"
    me = bpy.data.meshes.get(key)
    if me is None:
        import bmesh
        me = bpy.data.meshes.new(key)   # 必须先new再to_mesh(to_mesh的参数不能是None)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=12, radius=0.03)
        bm.to_mesh(me); bm.free()
        me.materials.append(get_or_make_material())
    return me


def find_coll():
    c = bpy.data.collections.get("ARP_Markers")
    if c is None:
        c = bpy.data.collections.new("ARP_Markers")
        bpy.context.scene.collection.children.link(c)
    return c


def find_main(arp_id):
    for o in bpy.data.objects:
        if o.get("arp_name") == arp_id and not o.get("is_sym"):
            return o
    return None


def add_driver_chain(sym, main):
    """对称球位置由主球驱动: x取反, y/z跟随(与手写版fix_live_mirror同机制)"""
    mods = {0: "-var", 1: "var", 2: "var"}
    chans = ['LOC_X', 'LOC_Y', 'LOC_Z']
    for i in range(3):
        fc = sym.driver_add("location", i)
        d = fc.driver
        d.type = 'SCRIPTED'
        d.expression = mods[i]
        v = d.variables.new()
        v.name = "var"
        v.type = 'TRANSFORMS'
        t = v.targets[0]
        t.id = main
        t.transform_type = chans[i]
        t.transform_space = 'WORLD_SPACE'


def create_marker(arp_id, cn, num):
    """主球建在3D光标处; 若该点是对称类, 同时建对侧镜像球(位置驱动实时同步)."""
    coll = find_coll()
    cur = bpy.context.scene.cursor.location.copy()

    if find_main(arp_id):
        return None, None, f"{cn} 已存在, 不重复创建"

    main = bpy.data.objects.new(f"{num}_{cn}", get_or_make_ball_mesh())
    main.location = cur
    main.show_in_front = True
    main.show_name = True
    main.empty_display_size = 0  # 纯mesh球
    main["arp_name"] = arp_id
    main["is_sym"] = False
    coll.objects.link(main)

    sym = None
    if arp_id in SYMS:
        sym = bpy.data.objects.new(f"{num}_{cn}_对侧镜像", get_or_make_ball_mesh())
        sym.location = (-cur.x, cur.y, cur.z)
        sym.show_in_front = True
        sym.show_name = True
        sym.empty_display_size = 0
        sym["arp_name"] = arp_id
        sym["is_sym"] = True
        coll.objects.link(sym)
        add_driver_chain(sym, main)
    return main, sym, None


class ARPMARKER_OT_add(bpy.types.Operator):
    bl_idname = "arpmarker.add"
    bl_label = "放置此标记"
    bl_description = "在3D光标处创建该标记球(对称点同时自动生成对侧镜像)"
    bl_options = {'REGISTER', 'UNDO'}
    marker: bpy.props.StringProperty()

    def execute(self, ctx):
        for aid, num, cn in MARKERS:
            if aid == self.marker:
                _, _, err = create_marker(aid, cn, num)
                if err:
                    self.report({'WARNING'}, err)
                else:
                    self.report({'INFO'}, f"{cn} 已放到光标位置")
                return {'FINISHED'}
        return {'CANCELLED'}


class ARPMARKER_OT_clear(bpy.types.Operator):
    bl_idname = "arpmarker.clear_all"
    bl_label = "删除全部标记重来"

    def execute(self, ctx):
        n = 0
        for o in [o for o in bpy.data.objects if o.get("arp_name") is not None]:
            bpy.data.objects.remove(o, do_unlink=True)
            n += 1
        self.report({'INFO'}, f"已删除{n}个")
        return {'FINISHED'}


class ARPMARKER_PT_panel(bpy.types.Panel):
    bl_label = "ARP打点工具"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ARP打点"

    def draw(self, ctx):
        col = self.layout.column()
        done = sum(1 for aid, _, _ in MARKERS if find_main(aid))
        col.label(text=f"进度: {done}/{len(MARKERS)}")
        col.separator()
        col.operator("arpmarker.clear_all", icon='TRASH')
        col.separator()
        for aid, num, cn in MARKERS:
            row = col.row(align=True)
            op = row.operator("arpmarker.add", text=f"{num} {cn}")
            op.marker = aid
            if find_main(aid):
                row.label(text="✓", icon='CHECKMARK')
        col.separator()
        done_all = "✓ 已完成, Ctrl+S保存!" if done == len(MARKERS) else ""
        col.label(text=done_all)


classes = (ARPMARKER_OT_add, ARPMARKER_OT_clear, ARPMARKER_PT_panel)


def register():
    for c in classes:
        try:
            bpy.utils.register_class(c)
        except Exception:
            bpy.utils.unregister_class(c)
            bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass


if __name__ == "__main__":
    register()
    print("=== ARP打点工具已加载: View3D侧栏(N键) → ARP打点 ===")
