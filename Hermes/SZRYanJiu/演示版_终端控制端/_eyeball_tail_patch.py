# -*- coding: utf-8 -*-
"""run_eyeball_v2: 挪到碗之后 — 末尾把眼球并入 02 碗输出(正典, 幂等)."""
import ast
P = r"E:\WangZhen_Project\AI\ShuZiRen\Hermes\SZRYanJiu\演示版_终端控制端\01a眼窝眼球\scripts\run_eyeball_v2.py"
s = open(P, encoding="utf-8").read()
R = []
def rep(old, new, tag):
    global s
    assert old in s, f"未匹配: {tag}"
    s = s.replace(old, new, 1); R.append(tag)

rep('''  输出路径不变(01A眼窝与眼球/models/01_2_eyeball_placed.blend), 供02碗工序与05绑定读取。''',
'''  输出 01a眼窝眼球/输出/01_2_eyeball_placed.blend; 2026-09-17 起在【眼窝碗之后】调用,
  并在末尾把眼球并入 02 碗输出(正典 02_qr_150k_socket.blend), 供03 UV/04烘焙/05绑定全程携带。''', "1 头注")

rep('''    # 验证渲染(正面+特写, EEVEE三灯同run_eyeball.py)
    render_verification(centers[0], centers[1])
    print("=== Done ===")''',
'''    # 验证渲染(正面+特写, EEVEE三灯同run_eyeball.py)
    render_verification(centers[0], centers[1])
    # ---- 2026-09-17 新流程(用户): QR → 碗 → 眼球摆入 — 摆好后并入碗输出(正典), 幂等 ----
    try:
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _sock = os.path.join(_root, "02QR拓扑", "输出", "02_qr_150k_socket.blend")
        if os.path.exists(_sock):
            bpy.ops.wm.open_mainfile(filepath=_sock)
            _has = [o.name for o in bpy.data.objects if o.name.startswith("Eye002")]
            if _has:
                print(f"碗输出已含眼球, 跳过并入: {_has}")
            else:
                with bpy.data.libraries.load(OUT_BLEND) as (_src, _dst):
                    _dst.objects = [n for n in _src.objects if n.startswith("Eye002")]
                _eyes = [o for o in _dst.objects if o is not None]
                for _o in _eyes:
                    bpy.context.scene.collection.objects.link(_o)
                bpy.ops.wm.save_as_mainfile(filepath=_sock)
                print(f"眼球已并入碗输出: {[o.name for o in _eyes]} → {os.path.basename(_sock)}")
        else:
            print(f"碗输出不存在({os.path.basename(_sock)}), 仅产出 01_2 (独立运行模式)")
    except Exception as _e:
        print(f"眼球并入碗输出失败: {_e}")
    print("=== Done ===")''', "2 并入尾块")

ast.parse(s)
open(P, "w", encoding="utf-8").write(s)
print("run_eyeball_v2 已应用:", R, flush=True)
