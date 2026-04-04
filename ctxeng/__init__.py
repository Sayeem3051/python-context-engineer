"""
ctxeng — Python Context Engineering Library
Automatically build, compress, and inject perfect LLM context from your codebase.
"""

from ctxeng.core import ContextEngine
from ctxeng.models import Context, ContextFile, TokenBudget
from ctxeng.builder import ContextBuilder

__version__ = "0.1.0"
__all__ = ["ContextEngine", "ContextBuilder", "Context", "ContextFile", "TokenBudget"]
