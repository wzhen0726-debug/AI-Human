# 掠射角自查: 从上方 15/25/40 度俯视各眼 外/内眼角 (实体/面朝向/线框)
import bpy, os, json, math, bmesh
from mathutils import Vector
D=r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端"
J=json.load(open(os.path.join(D,"01a眼窝眼球","3ddfa","eyelid_contour_manual.json"),encoding="utf-8"))
TAG=os.environ.get("SHOT_TAG","cur")
bpy.ops.wm.open_mainfile(filepath=os.environ.get("CHK_BLEND"))
head=max([x for x in bpy.data.objects if x.type=='MESH'],key=lambda x:len(x.data.vertices))
me=head.data
scn=bpy.context.scene
scn.render.engine='BLENDER_WORKBENCH'
sh=scn.display.shading
sh.light='STUDIO'; sh.color_type='SINGLE'; sh.single_color=(0.72,0.72,0.74); sh.show_cavity=True
scn.render.resolution_x=1500; scn.render.resolution_y=1050
cam=bpy.data.objects.new("_c", bpy.data.cameras.new("_c")); scn.collection.objects.link(cam)
scn.camera=cam; cam.data.type='ORTHO'
for i,col in ((0,(0.15,0.35,1.0,1.0)),(1,(1.0,0.1,0.1,1.0))):
    if len(me.materials)<=i: me.materials.append(bpy.data.materials.new(f"fo{i}"))
    me.materials[i].use_nodes=False; me.materials[i].diffuse_color=col
def paint(cd):
    bm=bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table(); bm.normal_update()
    for f in bm.faces: f.material_index = 1 if f.normal.dot(cd)>0 else 0
    bm.to_mesh(me); bm.free()
def place(tgt, elev_deg, R=0.7):
    a=math.radians(elev_deg)
    cam.location=tgt+Vector((0,-R*math.cos(a),R*math.sin(a)))
    cam.rotation_euler=(math.pi/2 - a, 0, 0)
    bpy.context.view_layer.update()
    return (cam.matrix_world.to_3x3() @ Vector((0,0,-1))).normalized()
for side,cx in (("L",-1),("R",1)):
    c=Vector(tuple(float(x) for x in J[side]['center']))
    for tag,off in (("outcorner",(-0.016,-0.002)),("incorner",(-0.014,0.002))):
        tgt=c+Vector((cx*off[0],0,off[1]))
        for elev in (18,32):
            cd=place(tgt, elev)
            for mode,pre in (("solid","gs"),("fo","gf")):
                if mode=="fo": paint(cd)
                else:
                    sh.color_type='SINGLE'
                sh.color_type='MATERIAL' if mode=="fo" else 'SINGLE'
                cam.data.ortho_scale=0.020
                scn.render.filepath=os.path.join(D,"logs",f"{pre}_{TAG}_{side}_{tag}_e{elev}.png"); bpy.ops.render.render(write_still=True)
print("graze shots done")
