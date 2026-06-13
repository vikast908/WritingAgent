"use strict";
// Zero-dependency tests via Node's built-in runner: `node --test` (or `npm test`).
// These cover the pure resolution/arg logic without spawning Python.
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const L = require("../lib/launcher");

test("parse classifies launcher flags vs forwarded args", () => {
  assert.equal(L.parse([]).kind, "forward"); // no args -> launch TUI
  assert.equal(L.parse(["--version"]).kind, "version");
  assert.equal(L.parse(["-V"]).kind, "version");
  assert.equal(L.parse(["--help"]).kind, "help");
  assert.equal(L.parse(["-h"]).kind, "help");
  assert.equal(L.parse(["doctor"]).kind, "doctor");
  assert.equal(L.parse(["write", "a topic"]).kind, "forward");
  assert.equal(L.parse(["run", "--help"]).kind, "forward"); // forwards the agent's own --help
});

test("whichSync finds an executable on a synthetic PATH (cross-platform)", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wa-which-"));
  try {
    const name = process.platform === "win32" ? "tool.EXE" : "tool";
    fs.writeFileSync(path.join(dir, name), "");
    if (process.platform !== "win32") fs.chmodSync(path.join(dir, name), 0o755);
    assert.ok(L.whichSync("tool", dir));
    assert.equal(L.whichSync("nope-not-here", dir), null);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("findProjectDir locates the dir holding book.py and honors WRITING_AGENT_HOME", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wa-proj-"));
  const nested = path.join(root, "a", "b");
  try {
    fs.mkdirSync(nested, { recursive: true });
    fs.writeFileSync(path.join(root, "book.py"), "# stub");
    // upward search from a nested dir finds the root
    assert.equal(L.findProjectDir(nested, undefined), fs.realpathSync(root));
    // explicit home wins
    assert.equal(L.findProjectDir(os.tmpdir(), root), fs.realpathSync(root));
    // no book.py anywhere -> null
    const empty = fs.mkdtempSync(path.join(os.tmpdir(), "wa-empty-"));
    assert.equal(L.findProjectDir(empty, undefined), null);
    fs.rmSync(empty, { recursive: true, force: true });
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("resolveAgent honors the WRITINGAGENT_CMD override", () => {
  const prev = process.env.WRITINGAGENT_CMD;
  process.env.WRITINGAGENT_CMD = "/opt/custom/agent";
  try {
    const a = L.resolveAgent();
    assert.equal(a.cmd, "/opt/custom/agent");
    assert.equal(a.how, "env:WRITINGAGENT_CMD");
    assert.deepEqual(a.baseArgs, []);
  } finally {
    if (prev === undefined) delete process.env.WRITINGAGENT_CMD;
    else process.env.WRITINGAGENT_CMD = prev;
  }
});

test("version and help output are sensible", () => {
  const lines = [];
  L.printVersion((s) => lines.push(s));
  assert.match(lines[0], /^writingagent \d+\.\d+\.\d+$/);
  assert.ok(L.HELP.includes("writingagent <command>"));
});
