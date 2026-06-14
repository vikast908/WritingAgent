"""Full Writing Agent CLI entry point.

Examples:
    python writingagent.py new --abstract "..." --pick 1 --chapters 8
    python writingagent.py run
    python writingagent.py status
    python writingagent.py review --chapter 3 --instruction "Make the confrontation colder."
    python writingagent.py read --manuscript
    python writingagent.py memory
    python writingagent.py skills
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from writingagent.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
