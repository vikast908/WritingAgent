"""Entry point for the vertical slice.

Usage:
    python run.py --abstract "..." --pick 1 --chapters 8 --chapter 1
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from book_agent.slice import main  # noqa: E402

if __name__ == "__main__":
    main()
