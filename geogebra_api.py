"""
GeoGebra 机构运动简图 Python 接口

通过 Node.js puppeteer 桥接操控 GeoGebra Classic 6，支持：
- 直接操控 GeoGebra 创建几何构造
- 批量执行 GeoGebra 命令
- 保存为 .ggb 文件
- 导出 PNG 截图
"""

import json
import subprocess
import os
import base64

BRIDGE_JS = os.path.join(os.path.dirname(__file__), "geogebra_bridge.js")
NODE = r"D:\tool\Node\node.exe"


def _run_bridge(args):
    """执行 Node.js 桥接脚本"""
    cmd = [NODE, BRIDGE_JS] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"Bridge 错误:\n{result.stderr}")
    return result.stdout


def exec_commands(commands, save=None, png=None, perspective="G"):
    """
    在 GeoGebra 中执行命令列表

    参数:
        commands: GeoGebra 命令列表
        save: 保存的 .ggb 文件路径
        png: 导出 PNG 截图路径
        perspective: 视图模式 (G=几何, A=代数, 3D=三维)
    """
    config = {
        "perspective": perspective,
        "new_construction": True,
        "commands": commands,
    }
    tmpfile = os.path.join(os.path.dirname(__file__), "_ggb_temp.json")
    with open(tmpfile, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    args = [tmpfile]
    if save:
        args += ["--save", save]
    if png:
        args += ["--png", png]

    return _run_bridge(args)


def save_ggb(filepath):
    """保存当前 GeoGebra 构造为 .ggb 文件"""
    _run_bridge(["--save", filepath])


def new_construction():
    """新建空白构造"""
    _run_bridge(["--inline", '["ZoomIn(1)"]'])
    return exec_commands(["A = (0,0)"], save=None)


def mechanism_to_ggb(name, design_commands, output_dir=None, perspective="G"):
    """
    将机构设计命令发送到 GeoGebra 并保存为 .ggb 和 PNG

    参数:
        name: 机构名称
        design_commands: GeoGebra 命令列表
        output_dir: 输出目录
        perspective: 视图

    返回:
        (ggb_path, png_path)
    """
    if output_dir is None:
        output_dir = os.path.dirname(__file__) or "."

    ggb_path = os.path.join(output_dir, f"{name}.ggb")
    png_path = os.path.join(output_dir, f"{name}.png")

    exec_commands(
        commands=design_commands,
        save=ggb_path,
        png=png_path,
        perspective=perspective
    )

    return ggb_path, png_path
