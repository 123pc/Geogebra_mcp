/**
 * Phase 1 smoke test for GeoGebra Web Runtime.
 *
 * Starts the daemon as a child process, sends JSON line protocol commands,
 * and verifies the full flow: status -> new -> batch -> objects -> save -> png.
 *
 * Usage: node scripts/smoke_web_runtime.js
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const readline = require('readline');

const PROJECT_DIR = path.resolve(__dirname, '..');
const DAEMON_JS = path.join(PROJECT_DIR, 'geogebra_mcp', 'geogebra_daemon.js');
const TMP_DIR = path.join(PROJECT_DIR, 'tmp');
const GGB_PATH = path.join(TMP_DIR, 'web_runtime_triangle.ggb');
const PNG_PATH = path.join(TMP_DIR, 'web_runtime_triangle.png');

fs.mkdirSync(TMP_DIR, { recursive: true });

const env = {
  ...process.env,
  GEOGEBRA_BACKEND: 'web',
  GEOGEBRA_WEB_HEADLESS: '1',
};

console.log('Starting GeoGebra Web Runtime daemon...');
const proc = spawn('node', [DAEMON_JS], { env, stdio: ['pipe', 'pipe', 'pipe'] });

let nextId = 0;
const pending = {};
let ready = false;
let readyData = null;

const rl = readline.createInterface({ input: proc.stdout });

rl.on('line', (line) => {
  line = line.trim();
  if (!line) return;
  let msg;
  try { msg = JSON.parse(line); } catch (e) { return; }
  if (msg.type === 'ready') {
    ready = true;
    readyData = msg;
    return;
  }
  if (msg.id && msg.id in pending) {
    pending[msg.id] = msg;
  }
});

proc.stderr.on('data', (d) => process.stderr.write(d));

function send(method, params) {
  const id = String(++nextId);
  const req = JSON.stringify({ id, method, params: params || {} });
  pending[id] = null;
  proc.stdin.write(req + '\n');
  return id;
}

function waitFor(id, timeoutMs) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + (timeoutMs || 30000);
    const check = () => {
      const resp = pending[id];
      if (resp !== null && resp !== undefined) {
        delete pending[id];
        resolve(resp);
        return;
      }
      if (Date.now() > deadline) {
        delete pending[id];
        reject(new Error(`Timeout waiting for msg ${id}`));
        return;
      }
      if (proc.exitCode !== null) {
        delete pending[id];
        reject(new Error(`Daemon exited with code ${proc.exitCode}`));
        return;
      }
      setTimeout(check, 50);
    };
    check();
  });
}

async function call(method, params, timeoutMs) {
  const id = send(method, params);
  const resp = await waitFor(id, timeoutMs);
  if (!resp.ok) throw new Error(`${method} failed: ${resp.error}`);
  return resp.result;
}

async function run() {
  // Wait for ready (longer timeout for local bundle mode)
  const readyTimeout = (env.GEOGEBRA_WEB_BUNDLE === 'local') ? 180000 : 45000;
  await new Promise((resolve, reject) => {
    const deadline = Date.now() + readyTimeout;
    const check = () => {
      if (ready) { resolve(); return; }
      if (Date.now() > deadline) { reject(new Error('Daemon ready timeout')); return; }
      setTimeout(check, 100);
    };
    check();
  });

  console.log('ready:', JSON.stringify(readyData));

  // 1. Status
  const status = await call('status');
  console.log('status:', JSON.stringify(status));
  if (!status.connected) throw new Error('Status not connected');
  if (status.backend !== 'web') throw new Error(`Expected backend=web, got ${status.backend}`);

  // 2. New construction
  await call('new');
  console.log('new: ok');

  // 3. Draw triangle
  const batchResult = await call('batch', {
    commands: [
      'A = (0, 0)',
      'B = (6, 0)',
      'C = (2, 4)',
      'Segment(A, B)',
      'Segment(B, C)',
      'Segment(C, A)',
    ]
  });
  console.log('batch:', JSON.stringify(batchResult));

  // 4. Get objects
  const objects = await call('objects');
  console.log('objects:', JSON.stringify(objects));
  if (!Array.isArray(objects)) throw new Error('Objects is not an array');
  ['A', 'B', 'C'].forEach(name => {
    if (!objects.includes(name)) throw new Error(`Missing object: ${name}`);
  });

  // 5. Save .ggb
  const saved = await call('save', { path: GGB_PATH });
  console.log('ggb:', saved.saved, saved.size);

  // 6. Export .png
  const png = await call('png', { path: PNG_PATH, scale: 2 });
  console.log('png:', png.saved);

  // Verify files
  const ggbStat = fs.statSync(GGB_PATH);
  if (ggbStat.size === 0) throw new Error('.ggb is empty');
  console.log('ggb bytes:', ggbStat.size);

  const pngStat = fs.statSync(PNG_PATH);
  if (pngStat.size === 0) throw new Error('.png is empty');
  console.log('png bytes:', pngStat.size);

  console.log('web runtime smoke ok');
}

run()
  .then(() => {
    send('shutdown');
    setTimeout(() => proc.kill(), 2000);
  })
  .catch((err) => {
    console.error('SMOKE FAILED:', err.message);
    send('shutdown');
    setTimeout(() => proc.kill(), 2000);
    process.exitCode = 1;
  });
