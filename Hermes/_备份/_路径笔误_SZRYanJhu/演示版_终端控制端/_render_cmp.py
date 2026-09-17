# -*- coding: utf-8 -*-
"""渲染对比 v58c基线 vs v59: 高模眼部特写(材质色/线框) + QR红区(材质色).
线框图看: 碗底极点放射扇是否消失, rim布线是否平滑.
材质色图看: 红区边界锯齿是否改善.
FLAT光照+无cavity(纯材质色, 防阴影误读). 每次open_mainfile后重建相机.
"""
import bpy, os, math
import numpy as np

D = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJhu\演示版_终端控制端".replace("SZRYanJhu","SZRYanJiu")
LOGS = os.path.join(D, "logs")
HI_BASE = os.path.join(D, "交付","01A眼窝与眼球","models","01_1_eye_socket_备份_20260911_152332_rim重构前.blend")
HI_V59  = os.path.join(D, "logs","_test_v59_eye_socket.blend")
QR_BASE = os.path.join(D, "02QR拓扑","输出","_备份_v58c_rim重构前","02_qr_150k_材质分区检查.blend")
QR_V59  = os.path.join(D, "02QR拓扑","输出","02_qr_150k_材质分区检查.blend")

# 眼部取景(世界坐标, 由实测数据定): L眼中心x=-35.8 y=-106 z=1671mm; rim x[-52,-18] z[1664,1676]
EYE_C = np.array([-0.0358, -0.1060, 1.6700])

def setup_scene(scn):
    scn.render.engine='BLENDER_WORKBENCH'
    scn.display.shading.light='FLAT'
    scn.display.shading.color_type='MATERIAL'
    scn.display.shading.show_cavity=False
    scn.render.film_transparent=False
    scn.world.color=(0.13,0.13,0.15)
    scn.render.resolution_x=1100
    scn.render.resolution_y=700

def make_cam(scn):
    cd=bpy.data.cameras.new("c"); c=bpy.data.objects.new("c",cd)
    scn.collection.objects.link(c); scn.camera=c
    c.rotation_euler=(math.pi/2,0,0)   # 视线沿+Y, up=+Z
    return c,cd

def paint(obj):
    """红=眼窝材质(v44tag/EyeSocket), 灰=皮肤. 高模无材质槽时按tag层上色."""
    me=obj.data
    # QR版有EyeSocket材质槽
    if any(m and "EyeSocket" in m.name for m in me.materials):
        for m in me.materials:
            if m is None: continue
            m.diffuse_color=(0.82,0.12,0.12,1.0) if "EyeSocket" in m.name else (0.60,0.58,0.56,1.0)
        return
    # 高模: 用顶点色按tag层着色
    for side in ("L","R"):
        at=me.attributes.get("v44tag_"+side)
        if at is None: continue
        t=np.zeros(len(me.polygons),dtype=np.int32); at.data.foreach_get("value",t)
        if side=="L": tagL=t
        else: tagR=t
    tagL=np.zeros(len(me.polygons),dtype=np.int32) if 'tagL' not in dir() else tagL
    tagR=np.zeros(len(me.polygons),dtype=np.int32) if 'tagR' not in dir() else tagR
    bowl=(tagL==2)|(tagR==2)
    vc=me.color_attributes.new("cmp",'BYTE_COLOR','CORNER') if not me.color_attributes.get("cmp") else me.color_attributes["cmp"]
    me.color_attributes.active_color=vc
    nl=len(me.loops)
    cols=np.zeros(nl*4,dtype=np.uint8)
    ls=np.array([p.loop_start for p in me.polygons]); lt=np.array([p.loop_total for p in me.polygons])
    for i in range(len(me.polygons)):
        s,e=ls[i],ls[i]+lt[i]
        rgb=(200,30,30) if bowl[i] else (153,148,143)
        cols[s*4:e*4:4]=rgb[0]; cols[s*4+1:e*4+1:4]=rgb[1]
        cols[s*4+2:e*4+2:4]=rgb[2]; cols[s*4+3:e*4+3:4]=255
    vc.data.foreach_set("color",cols)

JOBS=[
  ("v58c基线高模", HI_BASE, "hi"),
  ("v59新高模",    HI_V59,  "hi"),
  ("v58c基线QR",   QR_BASE, "qr"),
  ("v59新QR",      QR_V59,  "qr"),
]
for name,path,kind in JOBS:
    if not os.path.exists(path):
        print(f"SKIP {name}: 不存在"); continue
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    scn=bpy.context.scene; setup_scene(scn)
    obj=max([o for o in bpy.data.objects if o.type=='MESH'],key=lambda o: len(o.data.vertices))
    if kind=="qr": paint(obj)
    else:
        # 高模上色用材质: 建两个槽
        me=obj.data
        # 用tag层赋材质槽
        tagL=np.zeros(len(me.polygons),dtype=np.int32); tagR=np.zeros(len(me.polygons),dtype=np.int32)
        aL=me.attributes.get("v44tag_L"); aR=me.attributes.get("v44tag_R")
        if aL is not None: aL.data.foreach_get("value",tagL)
        if aR is not None: aR.data.foreach_get("value",tagR)
        bowl=(tagL==2)|(tagR==2)
        red=bpy.data.materials.new("RED"); red.diffuse_color=(0.82,0.12,0.12,1.0)
        gray=bpy.data.materials.new("GRAY"); gray.diffuse_color=(0.60,0.58,0.56,1.0)
        while len(me.materials): me.materials.pop(index=0)
        me.materials.append(gray); me.materials.append(red)
        mi=np.zeros(len(me.polygons),dtype=np.int32); mi[bowl]=1
        me.polygons.foreach_set("material_index",mi); me.update()
        print(f"  {name}: 碗面(红)={int(bowl.sum()):,}")
    # 相机: 左眼特写正视
    cam,camd=make_cam(scn)
    camd.lens=300
    cam.location=(EYE_C[0], EYE_C[1]-0.20, EYE_C[2])
    # 线框版(看布线/极点)
    tagname=name.replace(" ","_")
    for wire in (False,True):
        scn.display.shading.show_wire=wire
        if wire: scn.display.shading.wireframe_type='REPLACE'
        scn.render.filepath=os.path.join(LOGS,f"cmp_{tagname}{'_线框' if wire else '_材质'}.png")
        bpy.ops.render.render(write_still=True)
    scn.display.shading.show_wire=False
    # 双眼全景(正视, 看左右对称)
    camd.lens=150
    cam.location=(0.0, -0.35, 1.670)
    scn.render.filepath=os.path.join(LOGS,f"cmp_{tagname}_双眼.png")
    bpy.ops.render.render(write_still=True)
    print(f"渲染完成: {name}")
print("RENDER_CMP_DONE")
