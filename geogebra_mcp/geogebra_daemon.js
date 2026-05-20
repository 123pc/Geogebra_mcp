/**
 * GeoGebra Daemon - 持久化 Node.js 进程，维持与 GeoGebra 的 CDP 连接
 *
 * 通信协议 (stdin/stdout JSON, 每行一条消息):
 *   请求: {"id": "1", "method": "exec", "params": {"cmd": "A = (0,0)"}}
 *   响应: {"id": "1", "ok": true, "result": true}
 *   错误: {"id": "1", "ok": false, "error": "message"}
 *
 * 支持的方法:
 *   exec     - 执行单条 GeoGebra 命令
 *   batch    - 批量执行命令
 *   new      - 新建构造
 *   save     - 保存 .ggb 文件
 *   png      - 导出 PNG
 *   xml_get  - 获取构造 XML
 *   xml_set  - 设置构造 XML
 *   base64   - 获取 GGB base64
 *   status   - 检查连接状态
 *   perspective - 设置视图
 *   eval     - 执行任意 JS (高级)
 *   shutdown - 关闭守护进程
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const http = require('http');
const readline = require('readline');

const CDP_PORT = process.env.GEOGEBRA_CDP_PORT || '9222';
const BROWSER_URL = `http://localhost:${CDP_PORT}`;

function resolveBackend(raw) {
  const value = (raw || 'auto').toLowerCase();
  if (!['auto', 'web', 'desktop'].includes(value)) return 'auto';
  return value;
}

const BACKEND = resolveBackend(process.env.GEOGEBRA_BACKEND);
const WEB_HEADLESS = process.env.GEOGEBRA_WEB_HEADLESS !== '0';
const WEB_WIDTH = Number(process.env.GEOGEBRA_WEB_WIDTH || 1200);
const WEB_HEIGHT = Number(process.env.GEOGEBRA_WEB_HEIGHT || 800);
const WEB_BUNDLE = (process.env.GEOGEBRA_WEB_BUNDLE || 'cdn').toLowerCase();

function resolveBundlePath() {
  if (WEB_BUNDLE !== 'local') return null;
  if (process.env.GEOGEBRA_WEB_BUNDLE_PATH) return process.env.GEOGEBRA_WEB_BUNDLE_PATH;
  if (process.platform === 'win32') {
    const base = process.env.LOCALAPPDATA || require('os').homedir();
    return path.join(base, 'geogebra_mcp', 'web_bundle');
  }
  if (process.platform === 'darwin') {
    return path.join(require('os').homedir(), 'Library', 'Caches', 'geogebra_mcp', 'web_bundle');
  }
  const cacheHome = process.env.XDG_CACHE_HOME || path.join(require('os').homedir(), '.cache');
  return path.join(cacheHome, 'geogebra_mcp', 'web_bundle');
}

const BUNDLE_PATH = resolveBundlePath();

class GeoGebraDaemon {
  constructor() {
    this.browser = null;
    this.page = null;
    this.connected = false;
    this.configuredBackend = BACKEND;
    this.activeBackend = null;
    this._httpServer = null;
    this._webPort = null;
    this._activeBundle = WEB_BUNDLE;
    this._bundlePath = BUNDLE_PATH;
  }

  async _connectDesktop() {
    try {
      this.browser = await puppeteer.connect({
        browserURL: BROWSER_URL,
        defaultViewport: null,
        protocolTimeout: 30000
      });
      const pages = await this.browser.pages();
      this.page = pages.find(p => p.url().includes('classic')) || pages[0];
      if (!this.page) throw new Error('No GeoGebra page found');
      this.connected = true;
      this.activeBackend = 'desktop';
      return { connected: true, backend: 'desktop', configuredBackend: this.configuredBackend, runtime: 'classic6-cdp', title: await this.page.title() };
    } catch (err) {
      this.connected = false;
      return { connected: false, backend: null, configuredBackend: this.configuredBackend, error: err.message };
    }
  }

  async _startWebServer() {
    if (this._httpServer) return this._webPort;
    const webDir = path.join(__dirname, 'web');
    const bundleDir = BUNDLE_PATH;
    const mimeTypes = {
      '.html': 'text/html', '.js': 'application/javascript',
      '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml',
      '.json': 'application/json', '.wasm': 'application/wasm',
      '.txt': 'text/plain', '.xml': 'application/xml',
    };
    return new Promise((resolve, reject) => {
      this._httpServer = http.createServer((req, res) => {
        const urlPath = (req.url || '/').split('?')[0];
        // Serve bundle files from local cache
        if (urlPath.startsWith('/bundle/') && bundleDir) {
          const bundleFile = path.resolve(bundleDir, urlPath.slice('/bundle/'.length));
          if (!bundleFile.startsWith(path.resolve(bundleDir) + path.sep)) { res.writeHead(403); res.end(); return; }
          try {
            const content = fs.readFileSync(bundleFile);
            const ext = path.extname(bundleFile).toLowerCase();
            res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
            res.end(content);
            return;
          } catch (_) {
            res.writeHead(404);
            res.end('Not found');
            return;
          }
        }
        // Serve web runtime files
        let filePath = path.join(webDir, urlPath === '/' ? 'index.html' : urlPath);
        if (!filePath.startsWith(webDir)) { res.writeHead(403); res.end(); return; }
        try {
          const content = fs.readFileSync(filePath);
          const ext = path.extname(filePath).toLowerCase();
          res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
          res.end(content);
        } catch (_) {
          res.writeHead(404);
          res.end('Not found');
        }
      });
      this._httpServer.on('error', reject);
      this._httpServer.listen(0, '127.0.0.1', () => {
        this._webPort = this._httpServer.address().port;
        resolve(this._webPort);
      });
    });
  }

  async _connectWeb() {
    try {
      await this._startWebServer();
      this.browser = await puppeteer.launch({
        headless: WEB_HEADLESS,
        defaultViewport: { width: WEB_WIDTH, height: WEB_HEIGHT },
        args: ['--no-sandbox', '--disable-setuid-sandbox']
      });
      this.page = await this.browser.newPage();
      const url = `http://127.0.0.1:${this._webPort}/index.html?width=${WEB_WIDTH}&height=${WEB_HEIGHT}&bundle=${WEB_BUNDLE}`;
      const gotoOpts = WEB_BUNDLE === 'local'
        ? { waitUntil: 'networkidle2', timeout: 60000 }
        : { waitUntil: 'domcontentloaded', timeout: 30000 };
      await this.page.goto(url, gotoOpts);
      const loadTimeout = WEB_BUNDLE === 'local' ? 120000 : 30000;
      await this.page.waitForFunction(
        'window.__ggbReady === true || window.__ggbError',
        { timeout: loadTimeout }
      );
      const loadError = await this.page.evaluate(() => window.__ggbError);
      if (loadError) throw new Error(`GEOGEBRA_WEB_LOAD_FAILED: ${loadError}`);
      this.connected = true;
      this.activeBackend = 'web';
      return {
        connected: true,
        backend: 'web',
        configuredBackend: this.configuredBackend,
        runtime: 'geogebra-web',
        headless: WEB_HEADLESS,
        width: WEB_WIDTH,
        height: WEB_HEIGHT,
        bundle: WEB_BUNDLE
      };
    } catch (err) {
      this.connected = false;
      return { connected: false, backend: null, configuredBackend: this.configuredBackend, error: err.message };
    }
  }

  async connect() {
    if (this.configuredBackend === 'web') {
      return this._connectWeb();
    }
    if (this.configuredBackend === 'desktop') {
      const result = await this._connectDesktop();
      if (!result.connected) {
        throw new Error(`GEOGEBRA_NOT_CONNECTED: Cannot connect to GeoGebra at ${BROWSER_URL}: ${result.error}. Start GeoGebra Classic 6 with --remote-debugging-port=${CDP_PORT}`);
      }
      return result;
    }
    // auto: try web first, then desktop fallback
    const webResult = await this._connectWeb();
    if (webResult.connected) return webResult;
    try {
      const desktopResult = await this._connectDesktop();
      if (desktopResult.connected) return desktopResult;
    } catch (e) { /* ignore */ }
    return webResult;
  }

  async ensureConnected() {
    if (this.connected) return true;
    const result = await this.connect();
    if (!result.connected) {
      const hint = this.configuredBackend === 'desktop'
        ? `Start GeoGebra Classic 6 with --remote-debugging-port=${CDP_PORT}`
        : 'GeoGebra Web Runtime failed to start';
      throw new Error(`GEOGEBRA_NOT_CONNECTED: ${hint}: ${result.error}`);
    }
    return true;
  }

  async exec(cmd) {
    await this.ensureConnected();
    return await this.page.evaluate((c) => {
      try {
        return ggbApplet.evalCommand(c);
      } catch (e) {
        return 'Error: ' + e.message;
      }
    }, cmd);
  }

  async batch(commands) {
    await this.ensureConnected();
    const results = [];
    for (const cmd of commands) {
      const r = await this.page.evaluate((c) => {
        try { return ggbApplet.evalCommand(c); } catch (e) { return 'Error: ' + e.message; }
      }, cmd);
      results.push({ command: cmd, result: r });
    }
    return results;
  }

  async newConstruction() {
    await this.ensureConnected();
    await this.page.evaluate(() => ggbApplet.newConstruction());
    return true;
  }

  async save(filepath) {
    await this.ensureConnected();
    const b64 = await this.page.evaluate(() => ggbApplet.getBase64());
    if (!b64) throw new Error('getBase64 returned empty');
    const absPath = path.isAbsolute(filepath) ? filepath : path.join(process.cwd(), filepath);
    fs.mkdirSync(path.dirname(absPath), { recursive: true });
    fs.writeFileSync(absPath, Buffer.from(b64, 'base64'));
    return { saved: absPath, size: Buffer.byteLength(b64, 'base64') };
  }

  async png(filepath, scale = 2) {
    await this.ensureConnected();
    const b64 = await this.page.evaluate((s) => ggbApplet.getPNGBase64(s), scale);
    if (!b64) throw new Error('getPNGBase64 returned empty');
    const absPath = path.isAbsolute(filepath) ? filepath : path.join(process.cwd(), filepath);
    fs.mkdirSync(path.dirname(absPath), { recursive: true });
    fs.writeFileSync(absPath, Buffer.from(b64, 'base64'));
    return { saved: absPath };
  }

  async getXML() {
    await this.ensureConnected();
    return await this.page.evaluate(() => ggbApplet.getXML());
  }

  async setXML(xml) {
    await this.ensureConnected();
    await this.page.evaluate((x) => ggbApplet.setXML(x), xml);
    return true;
  }

  async getBase64() {
    await this.ensureConnected();
    return await this.page.evaluate(() => ggbApplet.getBase64());
  }

  async getStatus() {
    if (!this.connected) {
      try {
        await this.connect();
      } catch (e) {
        return {
          connected: false,
          backend: this.activeBackend,
          configuredBackend: this.configuredBackend,
          runtime: this.activeBackend === 'desktop' ? 'classic6-cdp' : this.activeBackend === 'web' ? 'geogebra-web' : null,
          error: e.message
        };
      }
    }
    try {
      const objCount = await this.page.evaluate(() =>
        ggbApplet.getAllObjectNames ? ggbApplet.getAllObjectNames().length : -1
      );
      const base = {
        connected: true,
        backend: this.activeBackend,
        configuredBackend: this.configuredBackend,
        runtime: this.activeBackend === 'desktop' ? 'classic6-cdp' : 'geogebra-web',
        objectCount: objCount
      };
      if (this.activeBackend === 'desktop') {
        try { base.title = await this.page.title(); } catch (_) {}
      } else {
        base.headless = WEB_HEADLESS;
        base.bundle = WEB_BUNDLE;
      }
      return base;
    } catch (e) {
      this.connected = false;
      return {
        connected: false,
        backend: this.activeBackend,
        configuredBackend: this.configuredBackend,
        error: e.message
      };
    }
  }

  async setPerspective(p) {
    await this.ensureConnected();
    await this.page.evaluate((persp) => ggbApplet.setPerspective(persp), p);
    return true;
  }

  async evalJS(code) {
    await this.ensureConnected();
    return await this.page.evaluate((c) => {
      try {
        const result = eval(c);
        return { value: result, type: typeof result };
      } catch (e) {
        return { error: e.message };
      }
    }, code);
  }

  async getObjectNames() {
    await this.ensureConnected();
    return await this.page.evaluate(() => ggbApplet.getAllObjectNames());
  }

  async setColor(label, r, g, b) {
    await this.ensureConnected();
    await this.page.evaluate((l, cr, cg, cb) => ggbApplet.setColor(l, cr, cg, cb), label, r, g, b);
    return true;
  }

  async setVisible(label, visible) {
    await this.ensureConnected();
    await this.page.evaluate((l, v) => ggbApplet.setVisible(l, v), label, visible);
    return true;
  }

  async setLabelVisible(label, visible) {
    await this.ensureConnected();
    await this.page.evaluate((l, v) => ggbApplet.setLabelVisible(l, v), label, visible);
    return true;
  }

  async setLineThickness(label, thickness) {
    await this.ensureConnected();
    await this.page.evaluate((l, t) => ggbApplet.setLineThickness(l, t), label, thickness);
    return true;
  }

  async setPointSize(label, size) {
    await this.ensureConnected();
    await this.page.evaluate((l, s) => ggbApplet.setPointSize(l, s), label, size);
    return true;
  }

  async setAnimating(label, animate) {
    await this.ensureConnected();
    await this.page.evaluate((l, a) => ggbApplet.setAnimating(l, a), label, animate);
    return true;
  }

  async setAnimationSpeed(label, speed) {
    await this.ensureConnected();
    await this.page.evaluate((l, s) => ggbApplet.setAnimationSpeed(l, s), label, speed);
    return true;
  }

  async resetView() {
    await this.ensureConnected();
    await this.page.evaluate(() => ggbApplet.reset());
    return true;
  }
}

// ── 主循环：stdin/stdout JSON 行协议 ──

async function main() {
  const daemon = new GeoGebraDaemon();
  const rl = readline.createInterface({ input: process.stdin, terminal: false });

  // 启动时尝试连接
  const initStatus = await daemon.connect();
  process.stdout.write(JSON.stringify({
    id: null,
    ok: initStatus.connected,
    type: 'ready',
    ...initStatus
  }) + '\n');

  const handlers = {
    exec:       (p) => daemon.exec(p.cmd),
    batch:      (p) => daemon.batch(p.commands),
    new:        ()   => daemon.newConstruction(),
    save:       (p) => daemon.save(p.path),
    png:        (p) => daemon.png(p.path, p.scale || 2),
    xml_get:    ()   => daemon.getXML(),
    xml_set:    (p) => daemon.setXML(p.xml),
    base64:     ()   => daemon.getBase64(),
    status:     ()   => daemon.getStatus(),
    connect:    ()   => daemon.connect(),
    perspective:(p) => daemon.setPerspective(p.perspective || 'G'),
    eval:       (p) => daemon.evalJS(p.code),
    objects:    ()   => daemon.getObjectNames(),
    set_color:  (p) => daemon.setColor(p.label, p.r, p.g, p.b),
    set_visible: (p) => daemon.setVisible(p.label, p.visible),
    set_label_visible: (p) => daemon.setLabelVisible(p.label, p.visible),
    set_thickness: (p) => daemon.setLineThickness(p.label, p.thickness),
    set_point_size: (p) => daemon.setPointSize(p.label, p.size),
    animate:    (p) => daemon.setAnimating(p.label, p.animate !== false),
    animate_speed: (p) => daemon.setAnimationSpeed(p.label, p.speed),
    reset_view: ()   => daemon.resetView(),
    shutdown:   async () => {
      if (daemon._httpServer) { await new Promise(r => daemon._httpServer.close(r)); }
      if (daemon.browser) { await daemon.browser.close().catch(() => {}); }
      process.exit(0);
    },
  };

  rl.on('line', async (line) => {
    let req;
    try { req = JSON.parse(line.trim()); } catch { return; }
    if (!req || !req.method) return;

    const handler = handlers[req.method];
    if (!handler) {
      process.stdout.write(JSON.stringify({
        id: req.id, ok: false, error: `Unknown method: ${req.method}`
      }) + '\n');
      return;
    }

    try {
      const result = await handler(req.params || {});
      process.stdout.write(JSON.stringify({ id: req.id, ok: true, result }) + '\n');
    } catch (err) {
      process.stdout.write(JSON.stringify({ id: req.id, ok: false, error: err.message }) + '\n');
    }
  });

  process.on('SIGTERM', () => process.exit(0));
  process.on('SIGINT', () => process.exit(0));
}

main().catch(err => {
  process.stdout.write(JSON.stringify({ id: null, ok: false, type: 'fatal', error: err.message }) + '\n');
  process.exit(1);
});
