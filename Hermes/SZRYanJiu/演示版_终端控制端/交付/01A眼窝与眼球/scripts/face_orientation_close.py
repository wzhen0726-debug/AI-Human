# 面朝向特写自查(红=背离相机, 与 Blender 面朝向 overlay 同原理)
import bpy, os, json, math
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"交付","01A眼窝与眼球","screenshots","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
TAG=os.environ.get("SHOT_TAG","cur")
bpy.ops.wm.open_mainfile(filepath=os.environ.get("CHK_BLEND"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=head.data
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
sh=scn.display.shading
sh.light='FLAT'; sh.color_type='MATERIAL'; sh.show_cavity=False
scn.render.resolution_x=1400; scn.render.resolution_y=1050
cam=bpy.data.objects.new("_c", bpy.data.cameras.new("_c")); scn.collection.objects.link(cam)
scn.camera=cam; cam.data.type='ORTHO'
# 材质 0=蓝(朝相机) 1=红(背离)
for i,col in ((0,(0.15,0.35,1.0,1.0)),(1,(1.0,0.1,0.1,1.0))):
    if len(me.materials)<=i: me.materials.append(bpy.data.materials.new(f"fo{i}"))
    me.materials[i].use_nodes=False; me.materials[i].diffuse_color=col
import bmesh
def paint(cam_dir):
    bm=bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.normal_update()
    for f in bm.faces:
        f.material_index = 1 if f.normal.dot(cam_dir) > 0.0 else 0
    bm.to_mesh(me); bm.free()
for side,cx in (("L",-1),("R",1)):
    c=Vector(tuple(float(x) for x in J[side]['center']))
    for tag,off in (("incorner",(-0.014,0.000)),("lowlid",(-0.004,-0.006)),("mid",(0.0,0.0))):
        tgt=c+Vector((cx*off[0],0,off[1]))
        loc=tgt+Vector((0,-0.6,0.02))
        cam.location=loc; cam.rotation_euler=(1.52,0,0)
        for sc_,suf in ((0.018,""),(0.048,"_full")):
            cam.data.ortho_scale=sc_
            bpy.context.view_layer.update()
            cmd=(cam.matrix_world.to_3x3() @ Vector((0,0,-1))).normalized()
            paint(cmd)
            scn.render.filepath=os.path.join(D,"logs",f"fo_{TAG}_{side}_{tag}{suf}.png"); bpy.ops.render.render(write_still=True)
print("faceo close done")
