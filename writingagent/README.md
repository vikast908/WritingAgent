# writingagent

A tiny, zero-dependency **global CLI launcher** for the [Writing Agent](../README.md) — a
self-correcting (and optionally self-directing) autonomous writing system for books and articles. The heavy lifting is done by
the Python engine; this package just gives you a `writingagent` command on your PATH that forwards
to it (passing your terminal straight through, so the interactive TUI works).

## Install

```bash
npm install -g writingagent       # the CLI  (needs Node >= 16)
writingagent setup                # one-time: installs the whole stack (needs Python 3.10+ & pip)
```

`setup` installs everything for you: the **Python engine** (pip, straight from GitHub — no clone),
**cairosvg** (crisp PDF diagrams), and the **d2 binary** (downloaded for your platform, used for
diagrams). All best-effort — the app degrades gracefully if cairosvg/d2 can't install. You can even
skip `setup`: the first run of `writingagent` offers to do it. Then, from anywhere:

```bash
writingagent                      # launch the interactive TUI
writingagent write "an article on vector databases"
writingagent new --abstract "..." # create a project
writingagent run                  # drive it to completion
writingagent status               # where things stand
writingagent export --format pdf
writingagent update               # update the engine to the latest version
writingagent doctor               # show how the engine was resolved
```

On a fresh machine you can even skip `setup` — the first run of `writingagent` offers to install
the engine for you.

`writingagent --version`, `writingagent --help`, and `writingagent doctor` are handled by the
launcher itself; **everything else is forwarded to the agent** (so `writingagent run --help` shows
the agent's own help for `run`).

## How it finds the engine

The launcher tries, in order:

1. **`$WRITINGAGENT_CMD`** — an explicit executable you point it at (advanced).
2. **A console script on PATH** — `writing-agent`, created when you
   `pip install` the Python package. This is the normal path.
3. **`python writingagent.py`** — when the project directory is found via **`$WRITINGAGENT_HOME`** or by
   searching upward from your current directory for `writingagent.py`.

If none is found it prints how to fix it. Run **`writingagent doctor`** to see exactly what was
detected (Python interpreter, console scripts, project directory, and the command it will use).

## Prerequisites

- **Node.js ≥ 16** (to run this launcher).
- **Python 3.10+ with pip** — `writingagent setup` uses it to install the engine. (Already have a
  clone? `pip install -e .` from the repo, or set `WRITINGAGENT_HOME` to it, works too.)

## Why a separate name?

The Python package's own console script is `writing-agent` (with a hyphen). This npm launcher is
`writingagent` (no hyphen) so the two never collide on PATH; the launcher will happily call the
`writing-agent` script under the hood.

## Develop / test

```bash
npm test        # node --test — covers PATH resolution, arg parsing, project discovery
```

## License

MIT
