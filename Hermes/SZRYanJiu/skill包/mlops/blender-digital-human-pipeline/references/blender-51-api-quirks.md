# Blender 5.1 API Quirks

> Collected 2026-07-31

## NodeLinks.remove()

Blender 5.1 changed `NodeLinks.remove()` to accept exactly **1 argument** (a link reference), not 2 (from_socket, to_socket).

```python
# WRONG (Blender 5.0 and earlier):
nt.links.remove(normal_map.outputs['Normal'], bsdf.inputs['Normal'])

# CORRECT (Blender 5.1):
for link in list(nt.links):  # copy list before mutating
    if link.to_node == bsdf and link.to_socket.name == 'Normal':
        nt.links.remove(link)
```

## OBJ Import

`bpy.ops.import_scene.obj()` does not exist. Use:
```python
bpy.ops.wm.obj_import(filepath=path)
```

## import_scene Support

`bpy.ops.import_scene` only supports:
- `.fbx` → `bpy.ops.import_scene.fbx()`
- `.gltf` / `.glb` → `bpy.ops.import_scene.gltf()`

No `.obj`, `.ply`, `.stl` etc.

## Voxel Remesh

Parameter lives on mesh data, not the modifier:
```python
mesh.data.remesh_voxel_size = 0.01  # NOT modifier.remesh_voxel_size
```

## Material.use_nodes Deprecation

`Material.use_nodes` triggers a DeprecationWarning in Blender 5.1 (expected removal in 6.0). Still works, but plan for migration.
