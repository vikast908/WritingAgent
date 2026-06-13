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
const path = require("path");
const { spawn } = require("child_process");

const pkg = require("../package.json");

const CONSOLE_SCRIPTS = ["writing-agent", "bookwriter", "book"];

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

/** Spawn the resolved target with stdio inherited; handles Windows .cmd/.bat shims. */
function spawnAgent(target, args, cwd) {
  const opts = { stdio: "inherit", cwd: cwd || process.cwd() };
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
  return { kind: "forward", argv };
}

const HELP = `writingagent — launcher for the Writing Agent (books + articles)

Usage:
  writingagent                 Launch the interactive TUI
  writingagent <command> ...   Forward to the agent (write, new, run, status, export, …)
  writingagent doctor          Diagnose how the agent will be found
  writingagent --version       Show this launcher's version + the resolved agent
  writingagent --help          Show this help

Examples:
  writingagent write "an article on vector databases"
  writingagent new --abstract "..." && writingagent run
  writingagent status

It forwards everything (except the flags above) to the Python engine. Resolution:
  1. $WRITINGAGENT_CMD              an explicit executable to run
  2. writing-agent / bookwriter / book   a pip-installed console script on PATH
  3. python book.py                via $WRITING_AGENT_HOME or an upward search for book.py

If none is found, install the engine (pip install -e .) or set WRITING_AGENT_HOME to the
project directory. Run "writingagent doctor" to see what was detected.`;

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
  const agent = resolveAgent();
  out(agent ? `  -> will run via ${agent.how}: ${agent.cmd}` : "  -> NO agent found (see writingagent --help)");
}

function printNoAgent(err = console.error) {
  err("writingagent: could not find the Writing Agent engine.");
  err("Fix it one of these ways:");
  err("  • pip install -e .   (from the project dir, to get the `writing-agent` command)");
  err("  • set WRITING_AGENT_HOME to the project directory (the one with book.py)");
  err("  • set WRITINGAGENT_CMD to an explicit executable to run");
  err("Then run `writingagent doctor` to confirm.");
}

/** Entry point: run the launcher with the given args (defaults to process args). */
function run(argv = process.argv.slice(2)) {
  const action = parse(argv);
  if (action.kind === "version") return printVersion();
  if (action.kind === "help") return printHelp();
  if (action.kind === "doctor") return printDoctor();

  const agent = resolveAgent();
  if (!agent) {
    printNoAgent();
    process.exitCode = 1;
    return;
  }
  const child = spawnAgent(agent.cmd, [...agent.baseArgs, ...action.argv], agent.cwd);
  child.on("error", (e) => {
    console.error(`writingagent: failed to launch the agent (${agent.how}): ${e.message}`);
    process.exit(1);
  });
  child.on("exit", (code, signal) => {
    process.exit(code == null ? (signal ? 1 : 0) : code);
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
  run,
  HELP,
  CONSOLE_SCRIPTS,
};
