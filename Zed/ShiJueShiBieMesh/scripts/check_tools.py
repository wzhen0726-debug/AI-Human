import bpy

print("=== Quad Remesher 相关操作符 ===")
for attr in dir(bpy.ops):
    if not attr.startswith('_'):
        try:
            mod = getattr(bpy.ops, attr)
            for sub in dir(mod):
                if not sub.startswith('_') and 'quad' in sub.lower():
                    print(f"  bpy.ops.{attr}.{sub}")
                if not sub.startswith('_') and 'remesh' in sub.lower() and 'quad' not in sub.lower():
                    print(f"  bpy.ops.{attr}.{sub}")
        except: pass

print("\n=== 所有 bpy.ops.object 中 remesh/quad 相关 ===")
for sub in dir(bpy.ops.object):
    if 'remesh' in sub.lower() or 'quad' in sub.lower():
        print(f"  bpy.ops.object.{sub}")

print("\n=== ARP add_ 相关操作符 ===")
for sub in dir(bpy.ops.arp):
    if 'add' in sub.lower() or 'append' in sub.lower() or 'smart' in sub.lower() or 'auto' in sub.lower() or 'match' in sub.lower() or 'bind' in sub.lower():
        print(f"  bpy.ops.arp.{sub}")

print("\n=== ARP 所有操作符 ===")
for sub in sorted(dir(bpy.ops.arp)):
    if not sub.startswith('_'):
        print(f"  bpy.ops.arp.{sub}")