"""
Entry point for running ctxeng as a Python module.

Usage:
    python -m ctxeng build "query"
    python -m ctxeng info
    python -m ctxeng watch "query"
"""

from ctxeng.cli import main

if __name__ == "__main__":
    main()