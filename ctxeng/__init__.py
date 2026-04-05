"""
ctxeng — Python Context Engineering Library
Automatically build, compress, and inject perfect LLM context from your codebase.
"""

from ctxeng.builder import ContextBuilder
from ctxeng.core import ContextEngine
from ctxeng.ignore import parse_ctxengignore
from ctxeng.models import Context, ContextFile, TokenBudget

__version__ = "0.1.1"
__all__ = [
    "ContextEngine",
    "ContextBuilder",
    "Context",
    "ContextFile",
    "TokenBudget",
    "parse_ctxengignore",
]
