"""Where the agent keeps its writable state - one home directory for everything:

    <home>/.env       API keys (written by /setkey, auto-loaded on startup)
    <home>/config/    models.yaml + settings.yaml (user-editable)
    <home>/brain/     users, projects, manuscripts (the durable memory)
    <home>/.index/    derived caches, SQLite indexes, telemetry (disposable)

Resolution order:

1. ``$WRITINGAGENT_HOME`` - explicit override. Useful for tests, portable setups,
   or keeping state off a synced folder (OneDrive/Dropbox sync adds latency to every
   atomic write and its file locks can make ``os.replace`` fail).
2. The OS per-user data dir: ``%LOCALAPPDATA%\\writingagent`` on Windows,
   ``~/Library/Application Support/writingagent`` on macOS, and
   ``$XDG_DATA_HOME/writingagent`` (default ``~/.local/share/writingagent``) elsewhere.

Never the current directory and never the install/repo tree - running the tool from
any directory must not scatter state there, and a pip install tree may be read-only.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_home() -> Path:
    """The agent home per the resolution order above. Pure computation - nothing is
    created here; writers mkdir on demand so read paths never touch the disk."""
    env = os.environ.get("WRITINGAGENT_HOME")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "writingagent"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "writingagent"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "writingagent"


# Resolved once at import; modules derive their locations from this. Tests monkeypatch
# the derived module-level names (brain.BRAIN, config._SETTINGS, ...), not this.
HOME = resolve_home()
