"use strict";
/**
 * writingagent — a thin, zero-dependency Node launcher for the (Python) Writing Agent.
 *
 * It resolves how to invoke the agent and forwards your arguments to it, passing stdin/
 * stdout/stderr straight through so the interactive TUI works. Resolution order:
 *   1. $WRITINGAGENT_CMD            — an explicit executable to run (advanced).
 *   2. a console script on PATH     — `writing-agent`, `bookwriter`, or `book`
 *                                     (created by `pip install` of the Python package).
 *   3. `python book.py`             — when the project is found via $WRITING_AGENT_HOME
 *                                     or by searching up from the current directory.
 * Anything but `--version` / `--help` / `doctor` (as the first argument) is forwarded.
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const pkg = require("../package.json");

const CONSOLE_SCRIPTS = ["writing-agent", "bookwriter", "book"];

// Where the launcher keeps the d2 binary it installs (so we never touch the system PATH).
const D2_VERSION = "v0.7.1";
const D2_HOME = path.join(os.homedir(), ".writingagent", "bin");
function d2BinPath() {
  return path.join(D2_HOME, process.platform === "win32" ? "d2.exe" : "d2");
}

/** Locate an executable on PATH (a zero-dependency `which`), respecting PATHEXT on Windows. */
function whichSync(cmd, pathStr = process.env.PATH || "", platform = process.platform) {
  const exts =
    platform === "win32"
      ? (process.env.PATHEXT || ".EXE;.CMD;.BAT;.COM").split(";").filter(Boolean)
      : [""];
  for (const dir of pathStr.split(path.delimiter)) {
    if (!dir) continue;
    for (const ext of exts) {
      const full = path.join(dir, cmd + ext);
      try {
        if (fs.statSync(full).isFile()) return full;
      } catch {
        /* not here */
      }
    }
  }
  return null;
}

/** A Python interpreter, preferring the Windows launcher / python3. */
function findPython(platform = process.platform) {
  const candidates =
    platform === "win32"
      ? [["py", ["-3"]], ["python", []], ["python3", []]]
      : [["python3", []], ["python", []]];
  for (const [name, prefix] of candidates) {
    const found = whichSync(name);
    if (found) return { cmd: found, prefix };
  }
  return null;
}

/** The Writing Agent project directory (the one holding book.py), or null. */
function findProjectDir(start = process.cwd(), home = process.env.WRITING_AGENT_HOME) {
  if (home && fs.existsSync(path.join(home, "book.py"))) return path.resolve(home);
  let dir = path.resolve(start);
  for (let i = 0; i < 8; i++) {
    if (fs.existsSync(path.join(dir, "book.py"))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return null;
}

/**
 * Decide how to run the agent.
 * @returns {{cmd:string, baseArgs:string[], cwd:(string|undefined), how:string}|null}
 */
function resolveAgent() {
  const override = process.env.WRITINGAGENT_CMD;
  if (override) return { cmd: override, baseArgs: [], cwd: undefined, how: "env:WRITINGAGENT_CMD" };

  for (const name of CONSOLE_SCRIPTS) {
    const found = whichSync(name);
    if (found) return { cmd: found, baseArgs: [], cwd: undefined, how: `console:${name}` };
  }

  const home = findProjectDir();
  if (home) {
    const py = findPython();
    if (py) {
      return {
        cmd: py.cmd,
        baseArgs: [...py.prefix, path.join(home, "book.py")],
        cwd: home,
        how: "python book.py",
      };
    }
  }
  return null;
}

/** Spawn the resolved target with stdio inherited; handles Windows .cmd/.bat shims.
 *  Points the engine at the launcher-installed d2 (BOOK_AGENT_D2) so `diagram_engine: auto`
 *  uses D2+ELK without any PATH changes. */
function spawnAgent(target, args, cwd) {
  const env = { ...process.env };
  if (!env.BOOK_AGENT_D2 && fs.existsSync(d2BinPath())) env.BOOK_AGENT_D2 = d2BinPath();
  const opts = { stdio: "inherit", cwd: cwd || process.cwd(), env };
  if (process.platform === "win32" && /\.(cmd|bat)$/i.test(target)) {
    // .cmd/.bat must go through the shell; quote everything for spaces.
    return spawn(`"${target}"`, args.map((a) => `"${a}"`), { ...opts, shell: true });
  }
  return spawn(target, args, opts);
}

/** Classify the leading argument into a launcher action. */
function parse(argv) {
  const first = argv[0];
  if (argv.length === 0) return { kind: "forward", argv };
  if (first === "--version" || first === "-V") return { kind: "version" };
  if (first === "--help" || first === "-h") return { kind: "help" };
  if (first === "doctor") return { kind: "doctor" };
  if (first === "setup") return { kind: "setup" };
  if (first === "update") return { kind: "update" };
  return { kind: "forward", argv };
}

// The Python engine isn't on PyPI; we install it straight from GitHub (a source tarball, so
// plain pip works — no git required, just Python 3.10+ and pip).
const ENGINE_PIP_SPEC =
  "https://github.com/vikast908/WritingAgent/archive/refs/heads/master.tar.gz";

/** Run `pip install --upgrade <pkgs>` for the resolved Python. Calls `done(ok)`; never exits. */
function pipInstall(pkgs, label, done) {
  const py = findPython();
  if (!py) {
    console.error("writingagent: Python 3.10+ with pip is required, but no Python was found on PATH.");
    console.error("Install Python from https://python.org, then re-run writingagent.");
    return done(false);
  }
  console.log(`writingagent: ${label} …\n`);
  const child = spawn(py.cmd, [...py.prefix, "-m", "pip", "install", "--upgrade", ...pkgs], {
    stdio: "inherit",
  });
  child.on("error", (e) => {
    console.error(`writingagent: could not run pip (${e.message}). Is pip installed for this Python?`);
    done(false);
  });
  child.on("exit", (code) => done(code === 0));
}

/** Back-compat alias: install just the engine. */
function installEngine(done, verb = "installing") {
  pipInstall([ENGINE_PIP_SPEC], `${verb} the Writing Agent engine`, done);
}

// ── d2 binary install (per-platform, from the d2 GitHub release) ──────────────
function _d2Asset() {
  const osName =
    process.platform === "win32" ? "windows" : process.platform === "darwin" ? "macos" : "linux";
  const arch = process.arch === "arm64" ? "arm64" : "amd64";
  return `d2-${D2_VERSION}-${osName}-${arch}.tar.gz`;
}

/** GET a URL to a file, following GitHub's redirects, with no dependencies. */
function _download(url, dest, done, depth = 0) {
  if (depth > 6) return done(new Error("too many redirects"));
  const https = require("https");
  https
    .get(url, { headers: { "User-Agent": "writingagent" } }, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        res.resume();
        return _download(res.headers.location, dest, done, depth + 1);
      }
      if (res.statusCode !== 200) {
        res.resume();
        return done(new Error("HTTP " + res.statusCode));
      }
      const file = fs.createWriteStream(dest);
      res.pipe(file);
      file.on("finish", () => file.close(() => done(null)));
      file.on("error", (e) => done(e));
    })
    .on("error", (e) => done(e));
}

function _findFile(dir, name) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      const r = _findFile(p, name);
      if (r) return r;
    } else if (e.name === name) {
      return p;
    }
  }
  return null;
}

/** Download + install the d2 binary into ~/.writingagent/bin. Best-effort: on any failure it
 *  warns and calls done(null) — diagrams just fall back to the built-in engine. */
function installD2(done) {
  if (fs.existsSync(d2BinPath())) return done(d2BinPath());
  const onPath = whichSync("d2");
  if (onPath) return done(onPath); // user already has d2
  const tgz = path.join(os.tmpdir(), `wa-d2-${process.pid}.tar.gz`);
  const xdir = path.join(os.tmpdir(), `wa-d2x-${process.pid}`);
  const cleanup = () => {
    try { fs.unlinkSync(tgz); } catch {}
    try { fs.rmSync(xdir, { recursive: true, force: true }); } catch {}
  };
  console.log(`writingagent: installing d2 for diagrams (${_d2Asset()}) …`);
  const url = `https://github.com/terrastruct/d2/releases/download/${D2_VERSION}/${_d2Asset()}`;
  _download(url, tgz, (err) => {
    if (err) {
      console.warn(`writingagent: d2 download failed (${err.message}); diagrams will use the built-in engine.`);
      cleanup();
      return done(null);
    }
    try { fs.mkdirSync(xdir, { recursive: true }); } catch {}
    const tar = spawn("tar", ["-xzf", tgz, "-C", xdir], { stdio: "ignore" });
    tar.on("error", () => {
      console.warn("writingagent: `tar` not available; skipping d2 (built-in diagrams will be used).");
      cleanup();
      done(null);
    });
    tar.on("exit", (code) => {
      const exe = process.platform === "win32" ? "d2.exe" : "d2";
      const found = code === 0 ? _findFile(xdir, exe) : null;
      if (!found) {
        console.warn("writingagent: could not extract d2; built-in diagrams will be used.");
        cleanup();
        return done(null);
      }
      try {
        fs.mkdirSync(D2_HOME, { recursive: true });
        fs.copyFileSync(found, d2BinPath());
        if (process.platform !== "win32") fs.chmodSync(d2BinPath(), 0o755);
        console.log(`✓ d2 installed → ${d2BinPath()}`);
        done(d2BinPath());
      } catch (e) {
        console.warn(`writingagent: could not place d2 (${e.message}); built-in diagrams will be used.`);
        done(null);
      } finally {
        cleanup();
      }
    });
  });
}

/** Install the whole stack: the engine, cairosvg (crisp PDF), and the d2 binary. Engine is
 *  required; cairosvg and d2 are best-effort (the app degrades gracefully without them). */
function setupAll(done, verb = "installing") {
  pipInstall([ENGINE_PIP_SPEC], `${verb} the Writing Agent engine`, (okEngine) => {
    if (!okEngine) return done(false);
    pipInstall(["cairosvg"], `${verb} cairosvg (crisp PDF diagrams)`, (okCairo) => {
      if (!okCairo)
        console.warn(
          "writingagent: cairosvg didn't install — PDF falls back to the built-in svglib path.\n" +
            "  (On Windows, cairosvg also needs the native cairo runtime to actually render.)",
        );
      installD2(() => done(true));
    });
  });
}

/** `writingagent setup` — install the full stack, report, and exit. */
function runSetup() {
  setupAll((ok) => {
    if (ok) {
      const agent = resolveAgent();
      console.log(
        agent
          ? '\n✓ Ready. Try:  writingagent write "an article on …"'
          : "\n✓ Installed, but the `writing-agent` command isn't on PATH yet.\n" +
              "  Add your Python scripts directory to PATH (see `writingagent doctor`), then reopen your shell.",
      );
    }
    process.exit(ok ? 0 : 1);
  });
}

/** `writingagent update` — re-install the engine + tools to pull the latest versions. */
function runUpdate() {
  setupAll((ok) => {
    if (ok) console.log("\n✓ Updated to the latest engine + tools.");
    process.exit(ok ? 0 : 1);
  }, "updating");
}

/** Ask Y/n (default yes). Non-interactive stdin -> proceed without prompting. */
function confirmInstall(done) {
  if (!process.stdin.isTTY) return done(true);
  const rl = require("readline").createInterface({ input: process.stdin, output: process.stdout });
  rl.question("Writing Agent isn't installed yet. Install it now (engine + cairosvg + d2)? [Y/n] ", (ans) => {
    rl.close();
    const a = String(ans || "").trim().toLowerCase();
    done(a === "" || a === "y" || a === "yes");
  });
}

const HELP = `writingagent — launcher for the Writing Agent (books + articles)

Usage:
  writingagent                 Launch the studio (installs the engine on first run)
  writingagent setup           Install the Python engine explicitly (needs Python 3.10+ & pip)
  writingagent update          Update the Python engine to the latest version
  writingagent <command> ...   Forward to the agent (write, new, run, status, export, …)
  writingagent doctor          Diagnose how the agent will be found
  writingagent --version       Show this launcher's version + the resolved agent
  writingagent --help          Show this help

Examples:
  writingagent setup
  writingagent write "an article on vector databases"
  writingagent new --abstract "..." && writingagent run
  writingagent status

It forwards everything (except the flags above) to the Python engine. Resolution:
  1. $WRITINGAGENT_CMD              an explicit executable to run
  2. writing-agent / bookwriter / book   a pip-installed console script on PATH
  3. python book.py                via $WRITING_AGENT_HOME or an upward search for book.py

On first run with nothing installed, writingagent offers to install the whole stack for you —
the Python engine, cairosvg (crisp PDF), and the d2 diagram binary. You can also run
"writingagent setup" explicitly, or set WRITING_AGENT_HOME to a local clone. Run
"writingagent doctor" to see what was detected.`;

function printHelp(out = console.log) {
  out(HELP);
}

function printVersion(out = console.log) {
  const agent = resolveAgent();
  out(`writingagent ${pkg.version}`);
  out(agent ? `agent: ${agent.how} (${agent.cmd})` : "agent: NOT FOUND (run: writingagent doctor)");
}

function printDoctor(out = console.log) {
  out(`writingagent ${pkg.version} — diagnostics`);
  out(`  platform: ${process.platform}  node: ${process.version}`);
  const py = findPython();
  out(`  python:   ${py ? `${py.cmd} ${py.prefix.join(" ")}`.trim() : "not found"}`);
  for (const name of CONSOLE_SCRIPTS) {
    const p = whichSync(name);
    out(`  ${name}:${" ".repeat(Math.max(1, 14 - name.length))}${p || "not on PATH"}`);
  }
  out(`  project:  ${findProjectDir() || "book.py not found (set WRITING_AGENT_HOME)"}`);
  const d2 = process.env.BOOK_AGENT_D2 || (fs.existsSync(d2BinPath()) ? d2BinPath() : whichSync("d2"));
  out(`  d2:       ${d2 || "not installed (diagrams use the built-in engine)"}`);
  const agent = resolveAgent();
  out(agent ? `  -> will run via ${agent.how}: ${agent.cmd}` : "  -> NO agent found (see writingagent --help)");
}

function printNoAgent(err = console.error) {
  err("writingagent: the Python engine isn't installed yet.");
  err("Fix it one of these ways:");
  err("  • writingagent setup   ← installs the engine for you (needs Python 3.10+ & pip)");
  err("  • set WRITING_AGENT_HOME to a local clone of the repo (the dir with book.py)");
  err("  • set WRITINGAGENT_CMD to an explicit executable to run");
  err("Then run `writingagent doctor` to confirm.");
}

/** Spawn the resolved agent with our args, inherit the terminal, and propagate its exit code. */
function launchAgent(agent, argv) {
  const child = spawnAgent(agent.cmd, [...agent.baseArgs, ...argv], agent.cwd);
  child.on("error", (e) => {
    console.error(`writingagent: failed to launch the agent (${agent.how}): ${e.message}`);
    process.exit(1);
  });
  child.on("exit", (code, signal) => {
    process.exit(code == null ? (signal ? 1 : 0) : code);
  });
}

/** Entry point: run the launcher with the given args (defaults to process args). */
function run(argv = process.argv.slice(2)) {
  const action = parse(argv);
  if (action.kind === "version") return printVersion();
  if (action.kind === "help") return printHelp();
  if (action.kind === "doctor") return printDoctor();
  if (action.kind === "setup") return runSetup();
  if (action.kind === "update") return runUpdate();

  const agent = resolveAgent();
  if (agent) return launchAgent(agent, action.argv);

  // First run after `npm install -g writingagent`: the engine isn't there yet. Offer to
  // bootstrap it once, then launch — so plain `writingagent` just works.
  if (!findPython()) {
    printNoAgent();
    process.exitCode = 1;
    return;
  }
  confirmInstall((yes) => {
    if (!yes) {
      printNoAgent();
      process.exitCode = 1;
      return;
    }
    setupAll((ok) => {
      const ready = ok ? resolveAgent() : null;
      if (!ready) {
        if (ok) printNoAgent(); // installed, but the console script isn't on PATH yet
        process.exit(1);
      }
      console.log(""); // a blank line between the install log and the app
      launchAgent(ready, action.argv);
    });
  });
}

module.exports = {
  whichSync,
  findPython,
  findProjectDir,
  resolveAgent,
  parse,
  printHelp,
  printVersion,
  printDoctor,
  pipInstall,
  installEngine,
  installD2,
  setupAll,
  confirmInstall,
  runSetup,
  runUpdate,
  launchAgent,
  d2BinPath,
  run,
  HELP,
  ENGINE_PIP_SPEC,
  CONSOLE_SCRIPTS,
};
