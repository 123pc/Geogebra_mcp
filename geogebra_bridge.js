/**
 * GeoGebra Bridge - 通过 Puppeteer/CDP 直接操控 GeoGebra Classic 6
 *
 * 用法:
 *   node geogebra_bridge.js <command_file.json>
 *   node geogebra_bridge.js --inline '["A = (0,0)", "B = (6,0)", "Segment(A,B)"]'
 */

const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

class GeoGebraController {
  constructor() {
    this.browser = null;
    this.page = null;
  }

  async connect() {
    this.browser = await puppeteer.connect({
      browserURL: 'http://localhost:9222',
      defaultViewport: null
    });
    const pages = await this.browser.pages();
    this.page = pages.find(p => p.url().includes('classic')) || pages[0];
    const title = await this.page.title();
    console.log(`[GeoGebra] 已连接: ${title}`);
    return this;
  }

  async eval(jsCode) {
    return await this.page.evaluate(jsCode);
  }

  async cmd(command) {
    const result = await this.page.evaluate((cmd) => {
      try {
        return ggbApplet.evalCommand(cmd);
      } catch (e) {
        return 'Error: ' + e.message;
      }
    }, command);
    return result;
  }

  async cmdBatch(commands) {
    const results = [];
    for (const cmd of commands) {
      const r = await this.cmd(cmd);
      results.push({ command: cmd, result: r });
      if (r === true || r === 'true') {
        console.log(`  ✓ ${cmd}`);
      } else {
        console.log(`  ✗ ${cmd} → ${r}`);
      }
    }
    return results;
  }

  async resetView() {
    await this.eval(() => ggbApplet.reset());
  }

  async setPerspective(p) {
    await this.eval((persp) => ggbApplet.setPerspective(persp), p);
  }

  async getXML() {
    return await this.eval(() => ggbApplet.getXML());
  }

  async setXML(xml) {
    await this.eval((x) => ggbApplet.setXML(x), xml);
  }

  async getBase64() {
    return await this.eval(() => ggbApplet.getBase64());
  }

  async saveGGB(filepath) {
    const b64 = await this.getBase64();
    if (b64) {
      fs.writeFileSync(filepath, Buffer.from(b64, 'base64'));
      console.log(`[GeoGebra] 已保存: ${filepath}`);
      return true;
    }
    return false;
  }

  async exportPNG(filepath, scale = 2) {
    await this.eval((s) => ggbApplet.writePNGtoFile('__temp_export.png', s), scale);
    // writePNGtoFile saves to a fixed location; use getPNGBase64 instead
    const b64 = await this.eval((s) => ggbApplet.getPNGBase64(s), scale);
    if (b64) {
      fs.writeFileSync(filepath, Buffer.from(b64, 'base64'));
      console.log(`[GeoGebra] PNG 已保存: ${filepath}`);
      return true;
    }
    return false;
  }

  async newConstruction() {
    await this.eval(() => ggbApplet.newConstruction());
  }

  async disconnect() {
    if (this.browser) {
      await this.browser.disconnect();
      console.log('[GeoGebra] 已断开');
    }
  }
}

// ── 机构运动简图构建器 ──

class MechanismBuilder {
  constructor(ggb) {
    this.ggb = ggb;
  }

  /** 固定铰链 (机架铰点) */
  async fixedHinge(label, x, y) {
    await this.ggb.cmd(`${label} = (${x}, ${y})`);
    // 绘制固定铰链符号：小圆 + 填充
    const r = Math.max(0.15, Math.abs(Math.min(x, y) * 0.05 + 0.1));
    await this.ggb.cmd(`Circle(${label}, ${r.toFixed(3)})`);
    return label;
  }

  /** 活动铰链 (连杆铰点) */
  async revoluteJoint(label, x, y) {
    await this.ggb.cmd(`${label} = (${x}, ${y})`);
    return label;
  }

  /** 连杆 (连接两个铰链) */
  async link(label, pointA, pointB) {
    await this.ggb.cmd(`Segment(${pointA}, ${pointB})`);
    return label;
  }

  /** 曲柄 (绕固定铰链旋转的杆) */
  async crank(center, length, angleDeg = 0) {
    const rad = angleDeg * Math.PI / 180;
    const x = length * Math.cos(rad);
    const y = length * Math.sin(rad);
    const label = `CrankEnd`;
    await this.ggb.cmd(`${label} = ${center} + (${x.toFixed(4)}, ${y.toFixed(4)})`);
    await this.ggb.cmd(`Segment(${center}, ${label})`);
    // 给端点加圆标记
    await this.ggb.cmd(`Circle(${label}, 0.1)`);
    return label;
  }

  /** 滑块 (沿直线导轨移动) */
  async slider(label, railPoint1, railPoint2, initialRatio = 0.5) {
    await this.ggb.cmd(`${label}_rail = Segment(${railPoint1}, ${railPoint2})`);
    await this.ggb.cmd(`${label} = Point(${label}_rail, ${initialRatio})`);
    // 绘制滑块矩形符号
    return label;
  }

  /** 给点添加轨迹追踪 */
  async trace(pointLabel) {
    await this.ggb.eval((label) => ggbApplet.setTrace(label, true), pointLabel);
  }

  /** 设置点/线的颜色 */
  async setColor(label, r, g, b) {
    await this.ggb.eval(
      (l, cr, cg, cb) => ggbApplet.setColor(l, cr, cg, cb),
      label, r, g, b
    );
  }

  /** 设置线宽 */
  async setThickness(label, t) {
    await this.ggb.eval(
      (l, thickness) => ggbApplet.setLineThickness(l, thickness),
      label, t
    );
  }

  /** 隐藏标签 */
  async hideLabel(label) {
    await this.ggb.eval(
      (l) => ggbApplet.setLabelVisible(l, false),
      label
    );
  }
}

// ── CLI ──

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    console.log(`GeoGebra Bridge - 通过 CDP 操控 GeoGebra Classic 6

用法:
  node geogebra_bridge.js <commands.json>  [--save output.ggb] [--png output.png]
  node geogebra_bridge.js --inline <json_array>
  node geogebra_bridge.js --xml <xml_string>
  node geogebra_bridge.js --base64

示例 JSON 文件格式:
{
  "perspective": "G",
  "commands": [
    "A = (0, 0)",
    "B = (6, 0)",
    "C = (2, 4)",
    "Segment(A, B)",
    "Segment(B, C)",
    "Segment(C, A)"
  ],
  "save": "output.ggb",
  "png": "output.png"
}
`);
    process.exit(0);
  }

  const ggb = new GeoGebraController();
  await ggb.connect();

  try {
    let savePath = null;
    let pngPath = null;

    if (args.includes('--inline')) {
      const idx = args.indexOf('--inline');
      const cmds = JSON.parse(args[idx + 1]);
      ggb.newConstruction();
      await ggb.cmdBatch(cmds);
      ggb.resetView();

    } else if (args.includes('--xml')) {
      const idx = args.indexOf('--xml');
      const xml = args[idx + 1];
      await ggb.setXML(xml);

    } else {
      // 从文件加载
      const filepath = args[0];
      const config = JSON.parse(fs.readFileSync(filepath, 'utf-8'));

      if (config.perspective) {
        await ggb.setPerspective(config.perspective);
      }

      if (config.new_construction !== false) {
        await ggb.newConstruction();
      }

      if (config.commands && config.commands.length > 0) {
        console.log(`[GeoGebra] 执行 ${config.commands.length} 条命令:`);
        await ggb.cmdBatch(config.commands);
      }

      if (config.xml) {
        await ggb.setXML(config.xml);
      }

      await ggb.resetView();

      savePath = config.save || config.output;
      pngPath = config.png || config.screenshot;
    }

    // 处理 --save 和 --png 参数覆盖
    const saveIdx = args.indexOf('--save');
    if (saveIdx >= 0) savePath = args[saveIdx + 1];
    const pngIdx = args.indexOf('--png');
    if (pngIdx >= 0) pngPath = args[pngIdx + 1];

    if (savePath) {
      await ggb.saveGGB(savePath);
    }
    if (pngPath) {
      await ggb.exportPNG(pngPath);
    }

    if (args.includes('--base64')) {
      const b64 = await ggb.getBase64();
      console.log(b64);
    }

  } finally {
    await ggb.disconnect();
  }
}

main().catch(err => {
  console.error('错误:', err.message);
  process.exit(1);
});

module.exports = { GeoGebraController, MechanismBuilder };
