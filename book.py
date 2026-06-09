"""Full Book Agent CLI entry point.

Examples:
    python book.py new --abstract "..." --pick 1 --chapters 8
    python book.py run
    python book.py status
    python book.py review --chapter 3 --instruction "Make the confrontation colder."
    python book.py read --manuscript
    python book.py memory
    python book.py skills
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from book_agent.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
