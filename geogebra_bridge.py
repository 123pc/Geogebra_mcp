"""
GeoGebra CDP Bridge - 通过 Chrome DevTools Protocol 直接操控 GeoGebra Classic 6
"""
import json
import time
import websocket

class GeoGebraBridge:
    """通过 CDP WebSocket 连接 GeoGebra，执行 JavaScript 控制几何构造"""

    def __init__(self, host="localhost", port=9222):
        self.host = host
        self.port = port
        self.ws = None
        self._msg_id = 0
        self._pending = {}

    def connect(self):
        """连接到 GeoGebra 的 CDP 端点"""
        # 获取可调试页面列表
        import urllib.request
        resp = urllib.request.urlopen(f"http://{self.host}:{self.port}/json")
        pages = json.loads(resp.read())

        # 找到 GeoGebra 经典页面
        geo_page = None
        for p in pages:
            if "GeoGebra" in p.get("title", "") or "classic" in p.get("url", ""):
                geo_page = p
                break
        if not geo_page and pages:
            geo_page = pages[0]

        if not geo_page:
            raise RuntimeError("没有找到 GeoGebra 页面")

        ws_url = geo_page["webSocketDebuggerUrl"]
        print(f"[Bridge] 连接到: {geo_page.get('title', 'GeoGebra')}")

        self.ws = websocket.create_connection(ws_url, header={
            "Origin": "http://127.0.0.1:9222",
            "User-Agent": "GeoGebraBridge/1.0"
        })
        self.ws.settimeout(10)
        return self

    def _send(self, method, params=None):
        self._msg_id += 1
        msg = {
            "id": self._msg_id,
            "method": method,
            "params": params or {}
        }
        self.ws.send(json.dumps(msg))
        # 等待响应
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get("id") == self._msg_id:
                if "error" in resp:
                    raise RuntimeError(f"CDP Error: {resp['error']}")
                return resp.get("result", {})
            # 可能是事件消息，继续等待

    def eval(self, js_code, timeout=10):
        """在 GeoGebra 上下文中执行 JavaScript 代码"""
        result = self._send("Runtime.evaluate", {
            "expression": js_code,
            "returnByValue": True,
            "timeout": timeout * 1000
        })
        return result

    def ggb_command(self, cmd):
        """执行 GeoGebra 命令（如创建点、线等）"""
        result = self.eval(f"ggbApplet.evalCommand({json.dumps(cmd)})")
        val = result.get("result", {}).get("value", None)
        return val

    def ggb_get_xml(self):
        """获取当前构造的 XML"""
        result = self.eval("ggbApplet.getXML()")
        return result.get("result", {}).get("value", "")

    def ggb_get_base64(self):
        """获取当前构造的 GGB 文件 (base64)"""
        result = self.eval("ggbApplet.getBase64()")
        return result.get("result", {}).get("value", "")

    def ggb_save(self, filepath):
        """保存当前构造为 .ggb 文件"""
        import base64
        b64 = self.ggb_get_base64()
        if b64:
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"[Bridge] 已保存: {filepath}")
            return True
        return False

    def ggb_set_perspective(self, perspective="G"):
        """设置视图: G=几何, A=代数, T=表格, 3D=三维"""
        self.eval(f"ggbApplet.setPerspective('{perspective}')")

    def ggb_new(self):
        """新建空白构造"""
        self.eval("ggbApplet.newConstruction()")

    def ggb_zoom_all(self):
        """缩放以适应所有对象"""
        self.eval("ggbApplet.zoomAll()")

    def ggb_export_png(self, filepath, scale=2):
        """导出为 PNG 图片"""
        import base64
        result = self.eval(f"ggbApplet.exportPNG(1, false, {scale})")
        data = result.get("result", {}).get("value", "")
        if data:
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(data.split(",")[1] if "," in data else data))
            print(f"[Bridge] PNG 已保存: {filepath}")
            return True
        return False

    def close(self):
        if self.ws:
            self.ws.close()


# ── 便捷函数 ──

def create_mechanism(name, commands, output_dir="D:/tool"):
    """
    用 GeoGebra 命令列表创建机构运动简图并保存为 .ggb 和 PNG

    参数:
        name: 机构名称
        commands: GeoGebra 命令列表，如 ["A = (0, 0)", "B = (4, 0)", ...]
        output_dir: 输出目录
    """
    import os
    ggb = GeoGebraBridge().connect()
    ggb.ggb_new()

    for cmd in commands:
        result = ggb.ggb_command(cmd)
        if result is not None:
            print(f"  ✓ {cmd} → {result}")
        else:
            print(f"  ✗ {cmd} (可能失败)")

    ggb.ggb_zoom_all()
    time.sleep(0.5)

    ggb_path = os.path.join(output_dir, f"{name}.ggb")
    png_path = os.path.join(output_dir, f"{name}.png")
    ggb.ggb_save(ggb_path)
    ggb.ggb_export_png(png_path)
    ggb.close()
    return ggb_path, png_path
