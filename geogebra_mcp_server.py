"""
GeoGebra MCP Server - 通过 Model Context Protocol 暴露 GeoGebra 操控能力

让 Claude Code 直接操控 GeoGebra 绘制机构运动简图、执行几何构造、
保存 .ggb 文件、导出截图、控制动画等。

使用方式 (在 Claude Code 中自动调用):
    geogebra_exec(command="A = (0, 0)")
    geogebra_batch(commands_json='["A = (0,0)", "B = (6,0)", "Segment(A,B)"]')
    geogebra_draw_mechanism(name="crank_rocker", design_json='{...}')
    geogebra_save(filepath="D:/tool/output.ggb")
"""

import asyncio
import json
import subprocess
import os
import time
import sys
import threading

from mcp.server.fastmcp import FastMCP

__version__ = "0.1.0"

from auto_launcher import (
    ensure_geogebra_running,
    get_cdp_port,
)

# ── 守护进程管理器 ──

NODE = "node"  # 依赖 PATH 环境变量，不再硬编码路径
DAEMON_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geogebra_daemon.js")


class DaemonError(Exception):
    pass


class GeoGebraDaemonClient:
    """管理 Node.js 守护进程，通过 stdin/stdout JSON 行协议通信"""

    def __init__(self, cdp_port: int = None):
        self.cdp_port = cdp_port or get_cdp_port()
        self.proc = None
        self._lock = threading.Lock()
        self._pending = {}
        self._next_id = 0
        self._reader_thread = None
        self._ready = threading.Event()
        self._shutdown = False
        self._stderr_lines = []

    def start(self, wait_for_ready: bool = False):
        env = os.environ.copy()
        env["GEOGEBRA_CDP_PORT"] = str(self.cdp_port)
        self.proc = subprocess.Popen(
            [NODE, DAEMON_JS],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self._reader_thread = threading.Thread(target=self._read_responses, daemon=True)
        self._reader_thread.start()
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

        if wait_for_ready:
            if not self._ready.wait(15):
                self.proc.kill()
                stderr_output = '\n'.join(self._stderr_lines[-10:])
                raise DaemonError(f"Daemon startup timeout / 守护进程启动超时\nstderr: {stderr_output}")

    def _read_stderr(self):
        """后台线程: 读取守护进程 stderr"""
        while not self._shutdown:
            try:
                line = self.proc.stderr.readline()
                if not line:
                    break
                self._stderr_lines.append(line.strip())
                sys.stderr.write(f"[daemon] {line}")
                sys.stderr.flush()
            except Exception:
                break

    def stop(self):
        self._shutdown = True
        if self.proc and self.proc.poll() is None:
            try:
                self._call('shutdown', {}, timeout=2)
            except Exception:
                pass
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()

    def _read_responses(self):
        """后台线程: 持续读取守护进程 stdout 的 JSON 响应"""
        while not self._shutdown:
            try:
                line = self.proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                resp = json.loads(line)
                if resp.get('type') == 'ready':
                    self._ready.set()
                    continue
                if resp.get('type') == 'fatal':
                    self._stderr_lines.append(f"FATAL: {resp.get('error')}")
                    self._ready.set()
                    continue
                msg_id = resp.get('id')
                if msg_id is not None and msg_id in self._pending:
                    self._pending[msg_id] = resp
            except (json.JSONDecodeError, ValueError):
                continue
            except Exception:
                break

    def _restart(self):
        """终止旧进程并重新启动守护进程（用于崩溃后自动恢复）。"""
        old_proc = self.proc
        if old_proc and old_proc.poll() is None:
            try:
                old_proc.terminate()
                old_proc.wait(timeout=3)
            except Exception:
                old_proc.kill()
        # 重置状态
        self.proc = None
        self._pending.clear()
        self._ready.clear()
        self._next_id = 0
        self.start()

    def _call(self, method, params=None, timeout=30):
        retried = False
        while True:
            try:
                with self._lock:
                    self._next_id += 1
                    msg_id = str(self._next_id)
                    req = json.dumps({"id": msg_id, "method": method, "params": params or {}})
                    self._pending[msg_id] = None
                    try:
                        self.proc.stdin.write(req + '\n')
                        self.proc.stdin.flush()
                    except BrokenPipeError:
                        raise DaemonError("Daemon crashed / 守护进程已崩溃")

                start = time.time()
                while time.time() - start < timeout:
                    if self._pending.get(msg_id) is not None:
                        resp = self._pending.pop(msg_id)
                        if resp.get('ok'):
                            return resp.get('result')
                        else:
                            raise DaemonError(resp.get('error', 'Unknown error'))
                    time.sleep(0.01)

                self._pending.pop(msg_id, None)
                raise DaemonError(f"Call timeout / 调用超时 '{method}' ({timeout}s)")

            except DaemonError as e:
                if retried:
                    raise
                retried = True

                # 如果守护进程还没连接上 GeoGebra，尝试自动启动
                if not self._ready.is_set():
                    sys.stderr.write(
                        "[geogebra-mcp] GeoGebra not connected, attempting auto-launch... / 未连接，尝试自动启动...\n"
                    )
                    if ensure_geogebra_running(port=self.cdp_port):
                        sys.stderr.write("[geogebra-mcp] GeoGebra launched, restarting daemon... / 已启动，重启守护进程...\n")
                    else:
                        sys.stderr.write("[geogebra-mcp] Auto-launch failed / 自动启动失败\n")

                sys.stderr.write(f"[geogebra-mcp] Daemon error ({e}), restarting... / 守护进程错误，正在重启...\n")
                try:
                    self._restart()
                except DaemonError as restart_err:
                    raise DaemonError(f"Daemon restart failed / 守护进程重启失败: {restart_err}")
                # 重试写入（loop 回到开头）

    # ── 便捷方法 ──
    def status(self):           return self._call('status')
    def exec_cmd(self, cmd):    return self._call('exec', {'cmd': cmd})
    def batch(self, commands):  return self._call('batch', {'commands': commands})
    def new_construction(self): return self._call('new')
    def save(self, path):       return self._call('save', {'path': path})
    def png(self, path, scale=2): return self._call('png', {'path': path, 'scale': scale})
    def get_xml(self):          return self._call('xml_get')
    def set_xml(self, xml):     return self._call('xml_set', {'xml': xml})
    def get_base64(self):       return self._call('base64')
    def set_perspective(self, p): return self._call('perspective', {'perspective': p})
    def eval_js(self, code):    return self._call('eval', {'code': code})
    def get_objects(self):      return self._call('objects')
    def set_color(self, l, r, g, b): return self._call('set_color', {'label': l, 'r': r, 'g': g, 'b': b})
    def set_visible(self, l, v):     return self._call('set_visible', {'label': l, 'visible': v})
    def set_label_visible(self, l, v): return self._call('set_label_visible', {'label': l, 'visible': v})
    def set_thickness(self, l, t):   return self._call('set_thickness', {'label': l, 'thickness': t})
    def set_point_size(self, l, s):  return self._call('set_point_size', {'label': l, 'size': s})
    def animate(self, l, a=True):    return self._call('animate', {'label': l, 'animate': a})
    def animate_speed(self, l, s):   return self._call('animate_speed', {'label': l, 'speed': s})
    def reset_view(self):            return self._call('reset_view')


# ── 全局守护进程实例 ──

_daemon = None

def get_daemon(cdp_port: int = None):
    global _daemon
    if _daemon is None:
        _daemon = GeoGebraDaemonClient(cdp_port=cdp_port)
        _daemon.start()
    return _daemon


# ── FastMCP Server ──

mcp = FastMCP("geogebra")


@mcp.tool()
async def geogebra_exec(command: str) -> str:
    """
    Execute a GeoGebra command. To make a mechanism MOVE (animate),
    you MUST create an angle slider and define points that depend on it.

    ── COMMAND REFERENCE ──

    POINTS:
      A = (x, y)            — free point
      A = (3, 4)
      M = Midpoint(A, B)     — midpoint
      P = Point(c, 0.5)      — point on curve c at parameter 0..1

    ANGLE SLIDER (the KEY to animation):
      α = 30°               — creates an angle slider. ALWAYS start with this
      β = 60°               — for mechanisms needing a second angle
      These become sliders. Use StartAnimation(α) to drive motion.

    DEPENDENT POINTS (formulas using the angle):
      A = O1 + (r*cos(α), r*sin(α))
      A = (r*cos(α), r*sin(α))   — same when O1 is origin
      X = (a*cos(α), b*sin(α))   — ellipse motion
      These points MOVE when α changes. This is how animation works.

    LINES & SEGMENTS:
      Line(A, B)             — infinite line through A,B
      Segment(A, B)          — segment between A,B
      Ray(A, B)              — ray from A through B
      PerpendicularLine(A, l)— line through A ⟂ l
      ParallelLine(A, l)     — line through A ∥ l

    CIRCLES & ARCS:
      Circle(O, r)           — circle center O radius r
      Circle(O, A)           — circle center O through point A
      c = Circle(O1, 2)      — name it 'c' to reuse

    INTERSECTIONS (critical for mechanisms):
      P = Intersect(c1, c2)           — all intersections
      P = Intersect(c1, c2, 1)        — FIRST intersection (use 1 or 2)
      P = Intersect(c1, c2, 2)        — SECOND intersection
      P = Intersect(Segment(A,B), c)  — segment-circle intersection

    ANGLES:
      Angle(A, O, B)         — ∠AOB in degrees

    SLIDER (numeric):
      r = 2                  — creates a numeric slider if value is a plain number
      r = Slider(0, 5, 0.1)  — explicit slider(min, max, step)

    TRANSFORMATIONS:
      Rotate(A, α, O)        — rotate A around O by angle α
      Dilate(A, s, O)        — dilate A from O by factor s
      Translate(A, v)        — translate A by vector v

    ANIMATION:
      StartAnimation(α)       — start the slider α animating
      StartAnimation()        — start all sliders
      StopAnimation()         — stop all animations
      SetAnimationSpeed(α, s) — set speed (0.1–10)
      After building the mechanism, always call StartAnimation(angle_label)
      and then geogebra_animate() for speed control.

    MISC:
      ZoomIn(1)              — zoom
      ZoomOut(1)             — un-zoom
      Pan(x, y)              — pan view

    ── CRITICAL RULES ──
    1. ALWAYS create an angle slider (eg α=30°) FIRST before dependent points
    2. Dependent points use cos(α), sin(α) — they move when α animates
    3. For linkages, define fixed pivots → slider → dependent points → segments
    4. Intersect() with index 1 or 2 picks WHICH intersection to use
    5. After all commands, call geogebra_animate() to start motion

    Args:
        command: GeoGebra command string (see reference above)
    """
    try:
        result = get_daemon().exec_cmd(command)
        return json.dumps({"success": True, "result": result, "command": command}, ensure_ascii=False)
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e), "command": command}, ensure_ascii=False)


@mcp.tool()
async def geogebra_batch(commands_json: str) -> str:
    """
    在 GeoGebra 中批量执行多条命令。适合一次性构建完整机构。

    Args:
        commands_json: JSON 数组格式的命令列表, 如 '["A=(0,0)","B=(6,0)","Segment(A,B)"]'
    """
    try:
        commands = json.loads(commands_json)
        if not isinstance(commands, list):
            return json.dumps({"success": False, "error": "commands_json 必须是 JSON 数组"}, ensure_ascii=False)
        results = get_daemon().batch(commands)
        ok = sum(1 for r in results if r['result'] not in (False, None) and not str(r['result']).startswith('Error'))
        return json.dumps({"success": True, "total": len(results), "succeeded": ok, "failed": len(results) - ok, "details": results}, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return json.dumps({"success": False, "error": f"JSON 解析错误: {e}"}, ensure_ascii=False)
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def geogebra_new_construction() -> str:
    """新建空白 GeoGebra 构造，清除当前所有对象。"""
    try:
        get_daemon().new_construction()
        return json.dumps({"success": True, "message": "已清空构造"})
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
async def geogebra_save(filepath: str) -> str:
    """
    保存当前 GeoGebra 构造为 .ggb 文件。

    Args:
        filepath: 保存路径, 如 "D:/tool/my_mechanism.ggb"
    """
    try:
        result = get_daemon().save(filepath)
        return json.dumps({"success": True, "path": result['saved'], "size_bytes": result.get('size', 0)})
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
async def geogebra_export_png(filepath: str, scale: int = 2) -> str:
    """
    导出当前 GeoGebra 视图为 PNG 截图。

    Args:
        filepath: 保存路径, 如 "D:/tool/screenshot.png"
        scale: 缩放因子 (1-4, 默认2)
    """
    try:
        result = get_daemon().png(filepath, scale)
        return json.dumps({"success": True, "path": result['saved']})
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
async def geogebra_version() -> str:
    """返回 MCP Server 版本号。"""
    import json as _json
    return _json.dumps({"version": __version__})


@mcp.tool()
async def geogebra_help(topic: str = "all") -> str:
    """
    获取 GeoGebra 命令和机构设计的帮助。在构建机构之前先调用此工具。

    Args:
        topic: "commands"=命令参考, "mechanisms"=机构模板, "animation"=动画, "all"=全部
    """
    help_text = _get_help(topic)
    return json.dumps({"topic": topic, "help": help_text}, ensure_ascii=False)


def _get_help(topic: str) -> str:
    if topic == "commands":
        return """
GeoGebra COMMAND REFERENCE for mechanism drawing:

POINTS: A=(x,y) | M=Midpoint(A,B) | P=Point(curve, param 0..1)
ANGLE SLIDER: α=30° (creates a slider — animate this to drive the mechanism)
DEPENDENT POINTS: A=O+(r*cos(α), r*sin(α)) — recalculated when α changes
SEGMENTS: Segment(A,B) — drawn between two points
CIRCLES: Circle(O, r) or Circle(O, A) | Always NAME circles for reuse: c1=Circle(A,5)
INTERSECTIONS: P=Intersect(c1,c2,1) — index 1 or 2 picks which intersection point
LINES: Line(A,B) (infinite) | Ray(A,B) | PerpendicularLine(A,l) | ParallelLine(A,l)
ANGLES: Angle(A,O,B) — returns degrees | Angle(polygon_name) — all interior angles
SLIDERS: r=2 (numeric slider) | r=Slider(0,5,0.1) (min,max,step)
ANIMATION: StartAnimation(α) | StopAnimation() | SetAnimationSpeed(α, 0.5)
TRANSFORM: Rotate(A, α, O) | Dilate(A, s, O) | Translate(A, v)
MISC: ZoomIn(1) | ZoomOut(1) | Delete(A)

RULES:
1. α=30° creates an ANGLE slider (range 0°–360°)
2. r=2 creates a NUMBER slider, NOT an angle
3. Points using cos/sin of the angle slider will MOVE during animation
4. Intersect(c1,c2,1) — ALWAYS specify the index (1 or 2)
5. Name circles to use them in Intersect: c1=Circle(A,5)  NOT  Circle(A,5) alone
"""
    elif topic == "mechanisms":
        return """
MECHANISM TEMPLATES:

CRANK-ROCKER (曲柄摇杆机构):
  O1=(0,0)    O2=(d,0)    α=30°    (d=frame spacing, typically 6)
  A=O1+(r*cos(α),r*sin(α))    (r=crank length, typically 2)
  c1=Circle(A,L)               (L=coupler length, typically 5)
  c2=Circle(O2,R)              (R=rocker length, typically 4)
  B=Intersect(c1,c2,1)
  Segment(O1,A)  Segment(A,B)  Segment(B,O2)
  Then: geogebra_animate(label="α", animate=true, speed=0.5)
  VALID IF: r+max(d,L,R) ≤ sum of other two (Grashof condition)

SLIDER-CRANK (曲柄滑块机构):
  O=(0,0)    α=30°    (O=fixed crank pivot)
  A=O+(r*cos(α),r*sin(α))    (r=crank length, typically 2)
  c=Circle(A,L)               (L=connecting rod, typically 5)
  guide=Line((0,-r),(10,-r))  (horizontal guide)
  B=Intersect(c,guide,1)
  Segment(O,A)  Segment(A,B)  (slider is point B on the guide)
  Then: geogebra_animate(label="α", animate=true, speed=0.5)

DOUBLE-CRANK (双曲柄机构):
  O1=(0,0)    O2=(d,0)    α=30°
  A=O1+(r1*cos(α),r1*sin(α))
  B=O2+(r2*cos(α+β),r2*sin(α+β))    (β=phase offset angle)
  Segment(O1,A)  Segment(A,B)  Segment(B,O2)
  Both cranks can rotate fully if Grashof satisfied.

FOUR-BAR (四连杆机构) — general crank-rocker:
  SAME as crank-rocker above. Adjust lengths.
"""
    elif topic == "animation":
        return """
ANIMATION HOW-TO:

1. CREATE an angle slider: α=30° (or β=60°, or use any Greek letter)
2. DEFINE points that depend on the slider using cos/sin:
   A = O + (r*cos(α), r*sin(α))
3. BUILD segments and circles using those points
4. START animation: geogebra_animate(label="α", animate=true, speed=0.5)
5. STOP animation: geogebra_animate(label="α", animate=false)

The slider automatically cycles through 0°→360°, making all dependent
points move along their paths. Use SetAnimationSpeed(α, s) to adjust.

Speed values: 0.1=slow, 0.5=medium, 1.0=fast, 2.0=very fast
"""
    else:
        return _get_help("commands") + "\n" + _get_help("mechanisms") + "\n" + _get_help("animation")


@mcp.tool()
async def geogebra_status() -> str:
    """检查 GeoGebra 连接状态和当前构造信息。"""
    try:
        status = get_daemon().status()
        return json.dumps(status, ensure_ascii=False)
    except DaemonError as e:
        return json.dumps({"connected": False, "error": str(e)})


@mcp.tool()
async def geogebra_set_view(perspective: str = "G") -> str:
    """
    设置 GeoGebra 视图模式。

    Args:
        perspective: "G"=几何, "A"=代数, "T"=表格, "3D"=三维, "AG"=代数+几何
    """
    try:
        get_daemon().set_perspective(perspective)
        return json.dumps({"success": True, "perspective": perspective})
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
async def geogebra_set_appearance(label: str, color_r: float = -1, color_g: float = -1,
                                   color_b: float = -1, thickness: int = -1,
                                   point_size: int = -1, visible: bool = True,
                                   label_visible: bool = True) -> str:
    """
    设置对象外观（颜色、线宽、点大小、可见性）。

    Args:
        label: 对象标签名
        color_r/g/b: RGB 颜色 0-1 (-1 不修改)
        thickness: 线宽 1-13
        point_size: 点大小 1-9
        visible: 是否可见
        label_visible: 是否显示标签
    """
    try:
        d = get_daemon()
        if color_r >= 0:
            d.set_color(label, color_r, color_g, color_b)
        if thickness >= 0:
            d.set_thickness(label, thickness)
        if point_size >= 0:
            d.set_point_size(label, point_size)
        d.set_visible(label, visible)
        d.set_label_visible(label, label_visible)
        return json.dumps({"success": True, "label": label})
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
async def geogebra_animate(label: str, animate: bool = True, speed: float = 1.0) -> str:
    """
    设置动画——让滑块控制的机构动起来。

    Args:
        label: 滑块标签, 如 "α"
        animate: 是否启动动画
        speed: 速度 (0.1-10)
    """
    try:
        d = get_daemon()
        if animate:
            d.animate(label, True)
            d.animate_speed(label, speed)
        else:
            d.animate(label, False)
        return json.dumps({"success": True, "label": label, "animating": animate})
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
async def geogebra_get_objects() -> str:
    """获取当前构造中所有对象的名称列表。"""
    try:
        objects = get_daemon().get_objects()
        return json.dumps({"success": True, "objects": objects, "count": len(objects) if objects else 0})
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
async def geogebra_draw_mechanism(name: str, design_json: str, output_dir: str = "") -> str:
    """
    Create a complete mechanism: new construction → commands → styles → save .ggb + PNG.
    Use geogebra_batch for commands instead of this tool unless you need one-step save.

    ── MECHANISM TEMPLATES ──

    **Crank-Rocker (曲柄摇杆):**
    O1=(0,0)  O2=(d,0)  α=angle°  crank_len=r  coupler_len=L  rocker_len=R
    A = O1 + (r*cos(α), r*sin(α))
    c1 = Circle(A, L)
    c2 = Circle(O2, R)
    B = Intersect(c1, c2, 1)
    Segment(O1, A)  Segment(A, B)  Segment(B, O2)
    Animate: StartAnimation(α)  Style: thick segments, colored points

    **Slider-Crank (曲柄滑块):**
    O=(0,0)  α=angle°  r=crank  L=coupler
    A = O + (r*cos(α), r*sin(α))
    c = Circle(A, L)
    guide = Line((0,-r), (10,-r))
    B = Intersect(c, guide, 1)
    Segment(O, A)  Segment(A, B)  Circle(B, 0.1)
    Animate: StartAnimation(α)

    **Double-Crank / Drag-Link:**
    O1=(0,0)  O2=(d,0)  α=angle°  r1,r2=crank lengths  L=coupler
    A = O1 + (r1*cos(α), r1*sin(α))
    B = O2 + (r2*cos(α+offset), r2*sin(α+offset))
    Segment(O1,A)  Segment(A,B)  Segment(B,O2)
    Animate: StartAnimation(α)

    **Four-Bar Linkage (general):**
    Same as crank-rocker but adjust lengths. Valid if shortest+longest ≤ sum of other two.

    ── design_json FORMAT ──
    {
      "perspective": "G",
      "animate": "α",
      "speed": 0.5,
      "commands": ["O1=(0,0)", "O2=(6,0)", "α=45°", ...],
      "styles": [
        {"label": "A", "color": [1,0,0], "point_size": 5},
        {"label": "Segment(O1,A)", "thickness": 5},
        {"label": "O1", "point_size": 6, "color": [0,0,0]}
      ]
    }

    ── WORKFLOW ──
    1. New construction (automatic)
    2. Execute commands in order
    3. Apply styles (colors, thickness, point sizes)
    4. Start animation on the angle slider
    5. Auto-zoom and save .ggb + .png

    Args:
        name: Mechanism name (used for filename)
        design_json: JSON string with design (see format above)
        output_dir: Output directory (default: current working directory)
    """
    try:
        design = json.loads(design_json)
        if not output_dir:
            output_dir = os.getcwd()
        d = get_daemon()

        d.new_construction()
        d.set_perspective(design.get('perspective', 'G'))

        commands = design.get('commands', [])
        results = d.batch(commands)
        cmd_ok = sum(1 for r in results
                     if r['result'] not in (False, None) and not str(r['result']).startswith('Error'))

        for style in design.get('styles', []):
            lbl = style['label']
            if 'color' in style:
                c = style['color']
                d.set_color(lbl, c[0], c[1], c[2])
            if 'thickness' in style:
                d.set_thickness(lbl, style['thickness'])
            if 'point_size' in style:
                d.set_point_size(lbl, style['point_size'])
            if 'visible' in style:
                d.set_visible(lbl, style['visible'])
            if 'label_visible' in style:
                d.set_label_visible(lbl, style['label_visible'])

        animate_label = design.get('animate')
        if animate_label:
            d.animate(animate_label, True)
            d.animate_speed(animate_label, design.get('speed', 0.5))

        d.reset_view()

        ggb_path = os.path.join(output_dir, f"{name}.ggb")
        png_path = os.path.join(output_dir, f"{name}.png")
        saved = d.save(ggb_path)
        d.png(png_path)

        return json.dumps({
            "success": True,
            "name": name,
            "commands_executed": f"{cmd_ok}/{len(commands)}",
            "ggb_file": ggb_path,
            "png_file": png_path,
            "objects_count": len(d.get_objects() or []),
        }, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({"success": False, "error": f"design_json 解析错误: {e}"}, ensure_ascii=False)
    except DaemonError as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ── 主入口 ──

def main():
    """MCP Server 入口 - 按需启动 GeoGebra，不使用时不会自动打开"""
    port = get_cdp_port()
    sys.stderr.write(f"[geogebra-mcp] v{__version__}  CDP port / CDP 端口: {port}\n")
    sys.stderr.write("[geogebra-mcp] Lazy mode — GeoGebra will start on first tool call / 按需启动模式\n")

    # 检查守护进程文件是否存在
    if not os.path.exists(DAEMON_JS):
        sys.stderr.write("[geogebra-mcp] WARNING: geogebra_daemon.js not found / 未找到 daemon.js\n")
        sys.stderr.write("[geogebra-mcp] If you installed via pip, please also clone the repo for JS files:\n")
        sys.stderr.write("  git clone https://github.com/123pc/Geogebra_mcp.git\n")
        sys.stderr.write("  cd Geogebra_mcp && npm install\n")
        sys.stderr.write("[geogebra-mcp] Or run: python install_wizard.py\n")

    # 预启动守护进程（Node.js 子进程），但不等待它连接 GeoGebra
    # 实际连接 + 自动启动在第一次工具调用时触发
    try:
        get_daemon(cdp_port=port)
        if _daemon._ready.is_set():
            sys.stderr.write("[geogebra-mcp] Daemon connected to existing GeoGebra / 守护进程已连接\n")
        else:
            sys.stderr.write("[geogebra-mcp] Daemon started (waiting for GeoGebra on first use) / 守护进程已启动，等待首次使用\n")
    except Exception:
        sys.stderr.write("[geogebra-mcp] Daemon process failed to start, will retry on first use / 守护进程启动失败，首次使用时重试\n")

    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
