"""
MCP Bridge Server: connects opencode (MCP stdio) to Blender's MCP addon (TCP socket).

The Blender addon runs a TCP server on localhost:9876 by default.
This bridge implements the MCP stdio protocol and forwards tool calls to Blender.
"""

import json
import socket
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

BLENDER_HOST = "localhost"
BLENDER_PORT = 9876


def send_to_blender(code: str) -> dict:
    """Send Python code to Blender's TCP socket server and return the result."""
    request = {"type": "execute", "code": code, "strict_json": True}
    data = (json.dumps(request) + "\0").encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    try:
        sock.connect((BLENDER_HOST, BLENDER_PORT))
        sock.sendall(data)

        buf = bytearray()
        while b"\0" not in buf:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf.extend(chunk)

        response = json.loads(bytes(buf[: buf.index(b"\0")]))
        return response
    finally:
        sock.close()


app = Server("blender-mcp-bridge")


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="execute_blender_code",
            description="Execute arbitrary Python code in Blender. "
            "The code runs in Blender's Python environment with full access to bpy. "
            "Store results in a dict named 'result'. "
            "Example: result = {\"objects\": [obj.name for obj in bpy.data.objects]}",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute in Blender",
                    }
                },
                "required": ["code"],
            },
        ),
        Tool(
            name="get_scene_info",
            description="Get basic information about the current Blender scene",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_object_info",
            description="Get detailed information about a specific object by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the object",
                    }
                },
                "required": ["name"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "execute_blender_code":
        code = arguments.get("code", "")
        result = send_to_blender(code)
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    elif name == "get_scene_info":
        code = """
import bpy, json
scene = bpy.context.scene
result = {
    "name": scene.name,
    "object_count": len(bpy.data.objects),
    "mesh_count": len(bpy.data.meshes),
    "material_count": len(bpy.data.materials),
    "objects": [{"name": obj.name, "type": obj.type} for obj in bpy.data.objects],
    "render_engine": scene.render.engine,
    "frame_current": scene.frame_current,
    "frame_start": scene.frame_start,
    "frame_end": scene.frame_end,
}
"""
        result = send_to_blender(code)
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    elif name == "get_object_info":
        obj_name = arguments.get("name", "")
        code = f"""
import bpy, json, mathutils
obj = bpy.data.objects.get({json.dumps(obj_name)})
if obj is None:
    result = {{"status": "error", "message": "Object not found: {obj_name}"}}
else:
    info = {{
        "name": obj.name,
        "type": obj.type,
        "location": list(obj.location),
        "rotation_euler": list(obj.rotation_euler),
        "scale": list(obj.scale),
        "visible": obj.visible_get(),
        "selectable": obj.visible_get(),
        "hide_select": obj.hide_select,
        "hide_viewport": obj.hide_viewport,
        "hide_render": obj.hide_render,
        "parent": obj.parent.name if obj.parent else None,
        "children": [c.name for c in obj.children],
        "modifiers": [{{"name": m.name, "type": m.type}} for m in obj.modifiers] if hasattr(obj, "modifiers") else [],
    }}
    if obj.type == "MESH" and obj.data:
        info["vertices"] = len(obj.data.vertices)
        info["edges"] = len(obj.data.edges)
        info["polygons"] = len(obj.data.polygons)
    if obj.material_slots:
        info["materials"] = [slot.material.name if slot.material else None for slot in obj.material_slots]
    result = {{"status": "ok", "result": info}}
"""
        result = send_to_blender(code)
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
