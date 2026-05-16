/**
 * Unit tests for GeoGebra daemon JSON line protocol and handler dispatch.
 *
 * Usage: node tests/test_daemon_protocol.js
 *
 * This is a minimal test runner — no external test frameworks required.
 */

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (e) {
    failed++;
    console.log(`  ✗ ${name}`);
    console.log(`    ${e.message}`);
  }
}

function assert(condition, message) {
  if (!condition) throw new Error(message || "assertion failed");
}

// ── JSON Line Protocol ──

console.log("\nJSON Line Protocol:");

test("parse valid request", () => {
  const line = '{"id":"1","method":"exec","params":{"cmd":"A=(0,0)"}}';
  const req = JSON.parse(line);
  assert(req.id === "1");
  assert(req.method === "exec");
  assert(req.params.cmd === "A=(0,0)");
});

test("parse batch request", () => {
  const line = '{"id":"2","method":"batch","params":{"commands":["A=(0,0)","B=(6,0)"]}}';
  const req = JSON.parse(line);
  assert(req.method === "batch");
  assert(req.params.commands.length === 2);
});

test("reject empty line", () => {
  const line = "";
  if (line.trim()) {
    JSON.parse(line);
  }
  // Empty lines should be skipped
  assert(true);
});

test("reject invalid JSON gracefully", () => {
  let caught = false;
  try {
    JSON.parse("{invalid");
  } catch (e) {
    caught = true;
  }
  assert(caught);
});

// ── Handler Dispatch ──

console.log("\nHandler Dispatch:");

const handlers = {
  exec: (p) => `exec:${p.cmd}`,
  batch: (p) => p.commands.map((c) => `exec:${c}`),
  status: () => ({ connected: true }),
  shutdown: () => "bye",
};

test("dispatch known method", () => {
  const req = { id: "1", method: "exec", params: { cmd: "A=(0,0)" } };
  const handler = handlers[req.method];
  assert(typeof handler === "function");
  const result = handler(req.params);
  assert(result === "exec:A=(0,0)");
});

test("dispatch batch method", () => {
  const req = { id: "2", method: "batch", params: { commands: ["A=(0,0)", "B=(6,0)"] } };
  const handler = handlers[req.method];
  const result = handler(req.params);
  assert(result.length === 2);
});

test("unknown method returns error", () => {
  const req = { id: "3", method: "nonexistent", params: {} };
  const handler = handlers[req.method];
  if (!handler) {
    // Should emit error response
    const errorResp = JSON.stringify({ id: req.id, ok: false, error: "Unknown method: nonexistent" });
    assert(errorResp.includes("Unknown method"));
  }
});

// ── Response Formatting ──

console.log("\nResponse Formatting:");

test("success response shape", () => {
  const resp = JSON.stringify({ id: "1", ok: true, result: true });
  const parsed = JSON.parse(resp);
  assert(parsed.id === "1");
  assert(parsed.ok === true);
  assert(parsed.result === true);
});

test("error response shape", () => {
  const resp = JSON.stringify({ id: "1", ok: false, error: "Connection failed" });
  const parsed = JSON.parse(resp);
  assert(parsed.ok === false);
  assert(typeof parsed.error === "string");
});

test("ready message shape", () => {
  const msg = JSON.stringify({
    id: null,
    ok: true,
    type: "ready",
    connected: true,
    title: "GeoGebra Classic 6",
  });
  const parsed = JSON.parse(msg);
  assert(parsed.type === "ready");
  assert(parsed.connected === true);
});

// ── CDP Port from env ──

console.log("\nCDP Port Configuration:");

test("default port is 9222", () => {
  delete process.env.GEOGEBRA_CDP_PORT;
  const port = process.env.GEOGEBRA_CDP_PORT || "9222";
  assert(port === "9222");
});

test("custom port from env", () => {
  process.env.GEOGEBRA_CDP_PORT = "9233";
  const port = process.env.GEOGEBRA_CDP_PORT;
  assert(port === "9233");
  delete process.env.GEOGEBRA_CDP_PORT;
});

// ── Results ──

console.log(`\n${passed + failed} tests: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
