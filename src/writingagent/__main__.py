"""`python -m writingagent` - same entry point as the installed `writing-agent` command.

Examples:
    python -m writingagent new --abstract "..." --pick 1 --chapters 8
    python -m writingagent run
    python -m writingagent status
    python -m writingagent review --chapter 3 --instruction "Make the confrontation colder."
    python -m writingagent read --manuscript
"""
from writingagent.cli import main

if __name__ == "__main__":
    main()
