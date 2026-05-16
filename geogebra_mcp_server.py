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

# ── 守护进程管理器 ──

NODE = "node"  # 依赖 PATH 环境变量，不再硬编码路径
DAEMON_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geogebra_daemon.js")


class DaemonError(Exception):
    pass


class GeoGebraDaemonClient:
    """管理 Node.js 守护进程，通过 stdin/stdout JSON 行协议通信"""

    def __init__(self):
        self.proc = None
        self._lock = threading.Lock()
        self._pending = {}
        self._next_id = 0
        self._reader_thread = None
        self._ready = threading.Event()
        self._shutdown = False
        self._stderr_lines = []

    def start(self):
        self.proc = subprocess.Popen(
            [NODE, DAEMON_JS],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self._reader_thread = threading.Thread(target=self._read_responses, daemon=True)
        self._reader_thread.start()
        # stderr 也单独读取，避免阻塞
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self._stderr_thread.start()

        if not self._ready.wait(15):
            self.proc.kill()
            stderr_output = '\n'.join(self._stderr_lines[-10:])
            raise DaemonError(f"守护进程启动超时\nstderr: {stderr_output}")

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

    def _call(self, method, params=None, timeout=30):
        with self._lock:
            self._next_id += 1
            msg_id = str(self._next_id)
            req = json.dumps({"id": msg_id, "method": method, "params": params or {}})
            self._pending[msg_id] = None
            try:
                self.proc.stdin.write(req + '\n')
                self.proc.stdin.flush()
            except BrokenPipeError:
                raise DaemonError("守护进程已崩溃")

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
        raise DaemonError(f"调用 '{method}' 超时 ({timeout}s)")

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

def get_daemon():
    global _daemon
    if _daemon is None:
        _daemon = GeoGebraDaemonClient()
        _daemon.start()
    return _daemon


# ── FastMCP Server ──

mcp = FastMCP("geogebra")


@mcp.tool()
async def geogebra_exec(command: str) -> str:
    """
    在 GeoGebra 中执行一条命令。支持所有 GeoGebra 命令语法。

    常用示例:
    - 创建点: "A = (0, 0)", "B = (3, 4)"
    - 创建线段: "Segment(A, B)"
    - 创建圆: "Circle(A, 3)"
    - 创建角度滑块: "α = 30°"
    - 创建向量点: "C = A + (2*cos(α), 2*sin(α))"
    - 求交点: "P = Intersect(c1, c2, 1)"

    Args:
        command: GeoGebra 命令字符串
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
    一站式机构绘制: 新建 → 执行命令 → 应用样式 → 保存 .ggb + PNG。

    design_json 格式:
    {
      "perspective": "G",
      "animate": "α",
      "speed": 0.5,
      "commands": ["O1=(0,0)", "O2=(6,0)", "α=45°", ...],
      "styles": [
        {"label": "A", "color": [1,0,0], "point_size": 5},
        {"label": "Segment(O1,A)", "thickness": 5}
      ]
    }

    Args:
        name: 机构名称 (用于文件名)
        design_json: 机构设计的 JSON 字符串
        output_dir: 输出目录
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
    """MCP Server 入口 - 通过 stdio 与 Claude Code 通信"""
    # 后台启动守护进程
    try:
        get_daemon()
        sys.stderr.write("[geogebra-mcp] 守护进程已连接\n")
    except DaemonError as e:
        sys.stderr.write(f"[geogebra-mcp] 警告: {e}\n")
        sys.stderr.write("[geogebra-mcp] 请确保 GeoGebra 已启动: --remote-debugging-port=9222\n")
        # 不退出 - 让用户有机会启动 GeoGebra

    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
