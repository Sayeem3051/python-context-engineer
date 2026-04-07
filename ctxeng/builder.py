"""Fluent builder API for constructing context step by step."""

from __future__ import annotations

from pathlib import Path

from ctxeng.core import ContextEngine
from ctxeng.models import Context, TokenBudget


class ContextBuilder:
    """
    Fluent, chainable API for building context.

    Example::

        from ctxeng import ContextBuilder

        ctx = (
            ContextBuilder(root=".")
            .for_model("gpt-4o")
            .only("**/*.py")
            .exclude("tests/**")
            .from_git_diff()
            .with_system("You are a senior Python engineer.")
            .build("Refactor the payment module to use async/await")
        )
        print(ctx.to_string("markdown"))
    """

    def __init__(self, root: str | Path = ".") -> None:
        self._root = Path(root).resolve()
        self._model = "claude-sonnet-4"
        self._budget: TokenBudget | None = None
        self._include: list[str] = []
        self._exclude: list[str] = []
        self._explicit_files: list[Path] = []
        self._use_git_diff = False
        self._git_base = "HEAD"
        self._system = ""
        self._max_file_size_kb = 500
        self._use_git = True
        self._use_import_graph = True
        self._import_graph_depth = 1

    def for_model(self, model: str) -> ContextBuilder:
        """Set the target model (determines token budget)."""
        self._model = model
        return self

    def with_budget(self, total: int, reserved_output: int = 2048) -> ContextBuilder:
        """Set an explicit token budget."""
        self._budget = TokenBudget(total=total, reserved_output=reserved_output)
        return self

    def only(self, *patterns: str) -> ContextBuilder:
        """Only include files matching these glob patterns."""
        self._include.extend(patterns)
        return self

    def exclude(self, *patterns: str) -> ContextBuilder:
        """Exclude files matching these glob patterns."""
        self._exclude.extend(patterns)
        return self

    def include_files(self, *paths: str | Path) -> ContextBuilder:
        """Explicitly include specific files (bypasses auto-discovery)."""
        self._explicit_files.extend(Path(p) for p in paths)
        return self

    def from_git_diff(self, base: str = "HEAD") -> ContextBuilder:
        """Only include files changed since `base`."""
        self._use_git_diff = True
        self._git_base = base
        return self

    def with_system(self, prompt: str) -> ContextBuilder:
        """Set a system prompt (counts against token budget)."""
        self._system = prompt
        return self

    def max_file_size(self, kb: int) -> ContextBuilder:
        """Skip files larger than this size in KB."""
        self._max_file_size_kb = kb
        return self

    def no_git(self) -> ContextBuilder:
        """Disable git-based recency scoring."""
        self._use_git = False
        return self

    def use_import_graph(self, depth: int = 1) -> ContextBuilder:
        """Follow local Python imports from scored files (default depth 1)."""
        self._use_import_graph = True
        self._import_graph_depth = depth
        return self

    def no_import_graph(self) -> ContextBuilder:
        """Disable import-graph expansion."""
        self._use_import_graph = False
        return self

    def build(self, query: str = "") -> Context:
        """
        Build and return the optimized Context.

        Args:
            query: What you want the LLM to do. Be specific for best results.

        Returns:
            :class:`~ctxeng.models.Context`
        """
        engine = self._build_engine()
        return engine.build(
            query=query,
            files=self._explicit_files or None,
            git_diff=self._use_git_diff,
            git_base=self._git_base,
            system_prompt=self._system,
        )

    def _build_engine(self) -> ContextEngine:
        """Internal helper for CLI/watch integrations."""
        return ContextEngine(
            root=self._root,
            model=self._model,
            budget=self._budget,
            max_file_size_kb=self._max_file_size_kb,
            include_patterns=self._include or None,
            exclude_patterns=self._exclude or None,
            use_git=self._use_git,
            use_import_graph=self._use_import_graph,
            import_graph_depth=self._import_graph_depth,
        )
