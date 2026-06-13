# writingagent

A tiny, zero-dependency **global CLI launcher** for the [Writing Agent](../README.md) — a
self-correcting, autonomous writing system for books and articles. The heavy lifting is done by
the Python engine; this package just gives you a `writingagent` command on your PATH that forwards
to it (passing your terminal straight through, so the interactive TUI works).

## Install

```bash
# from this directory
npm install -g .
# or, once published:
npm install -g writingagent
```

Then, from anywhere:

```bash
writingagent                      # launch the interactive TUI
writingagent write "an article on vector databases"
writingagent new --abstract "..." # create a project
writingagent run                  # drive it to completion
writingagent status               # where things stand
writingagent export --format pdf
```

`writingagent --version`, `writingagent --help`, and `writingagent doctor` are handled by the
launcher itself; **everything else is forwarded to the agent** (so `writingagent run --help` shows
the agent's own help for `run`).

## How it finds the engine

The launcher tries, in order:

1. **`$WRITINGAGENT_CMD`** — an explicit executable you point it at (advanced).
2. **A console script on PATH** — `writing-agent`, `bookwriter`, or `book`, created when you
   `pip install` the Python package. This is the normal path.
3. **`python book.py`** — when the project directory is found via **`$WRITING_AGENT_HOME`** or by
   searching upward from your current directory for `book.py`.

If none is found it prints how to fix it. Run **`writingagent doctor`** to see exactly what was
detected (Python interpreter, console scripts, project directory, and the command it will use).

## Prerequisites

- **Node.js ≥ 16** (to run this launcher).
- The **Python engine installed** — from the project root:
  ```bash
  pip install -e .          # gives you the `writing-agent` console script
  ```
  …or set `WRITING_AGENT_HOME` to the project directory so the launcher can run `python book.py`.

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
