"""
ctxeng — Python Context Engineering Library
Automatically build, compress, and inject perfect LLM context from your codebase.
"""

from ctxeng.builder import ContextBuilder
from ctxeng.core import ContextEngine
from ctxeng.costs import COST_PER_1K_INPUT_TOKENS, estimate_cost, matched_pricing_model
from ctxeng.ignore import parse_ctxengignore
from ctxeng.import_graph import build_import_graph, expand_with_imports
from ctxeng.models import Context, ContextFile, TokenBudget
from ctxeng.semantic import compute_semantic_scores
from ctxeng.watcher import ContextWatcher, WatchConfig

__version__ = "0.1.6"
__all__ = [
    "ContextEngine",
    "ContextBuilder",
    "Context",
    "ContextFile",
    "TokenBudget",
    "parse_ctxengignore",
    "build_import_graph",
    "expand_with_imports",
    "COST_PER_1K_INPUT_TOKENS",
    "estimate_cost",
    "matched_pricing_model",
    "ContextWatcher",
    "WatchConfig",
    "compute_semantic_scores",
]
