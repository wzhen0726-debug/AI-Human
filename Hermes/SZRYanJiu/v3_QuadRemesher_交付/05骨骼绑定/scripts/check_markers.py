import bpy
coll = bpy.data.collections.get('LM_Rig')
print('collection LM_Rig:', 'EXISTS' if coll else 'MISSING')
if coll:
    print('markers:', len(coll.objects))
    for o in sorted(coll.objects, key=lambda x: x.name):
        sw = [c for c in o.constraints if c.type == 'SHRINKWRAP']
        print(' ', o.name, 'shrinkwrap=', len(sw), 'target=', sw[0].target.name if sw else None)
