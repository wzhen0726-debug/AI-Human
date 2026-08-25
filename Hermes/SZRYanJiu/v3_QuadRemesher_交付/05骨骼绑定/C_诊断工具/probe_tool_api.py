"""探测5.1后台安全设置默认工具的方式(不用会崩溃的tool_set_by_id)."""
import bpy

ws = bpy.data.workspaces[0]
print("WorkSpace属性:")
for attr in dir(ws):
    if 'tool' in attr.lower():
        print(f"  ws.{attr}")

# tools集合
if hasattr(ws, 'tools'):
    print(f"\ntools集合: {len(ws.tools)}个")
    for t in ws.tools:
        print(f"  {t.name}")

# 尝试: 加移动工具 + 设为激活
try:
    ws.tools.add("builtin.move")
    ws.tools.set_active({"builtin.move"})
    print("\nset_active成功")
    print("active tools:", [t.name for t in ws.tools])
except Exception as ex:
    print(f"\nset_active失败: {ex}")

print("PROBE_DONE")
