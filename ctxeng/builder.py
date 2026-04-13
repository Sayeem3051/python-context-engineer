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
        self._use_semantic = False
        self._semantic_model = "all-MiniLM-L6-v2"
        self._respect_gitignore = True
        self._allow_paths: list[str | Path] = []
        self._deny_paths: list[str | Path] = []
        self._trace = False
        self._trace_dir: str | Path | None = None
        self._trace_id: str | None = None
        self._rag = False
        self._rag_max_chunks = 20
        self._rag_chunk_max_lines = 120
        self._rag_chunk_overlap = 20
        self._rag_embedding_model = "all-MiniLM-L6-v2"
        self._skeleton = False
        self._redact = True
        self._fewshot = False
        self._fewshot_dir: str | Path = ".ctxeng/examples"
        self._fewshot_max_files = 5

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

    def use_semantic(self, model: str = "all-MiniLM-L6-v2") -> ContextBuilder:
        """Enable semantic similarity scoring (requires `sentence-transformers`)."""
        self._use_semantic = True
        self._semantic_model = model
        return self

    def no_gitignore(self) -> ContextBuilder:
        """Do not apply `.gitignore` rules when discovering files."""
        self._respect_gitignore = False
        return self

    def allow(self, *paths: str | Path) -> ContextBuilder:
        """Allowlist path prefixes; only these paths can be included."""
        self._allow_paths.extend(paths)
        return self

    def deny(self, *paths: str | Path) -> ContextBuilder:
        """Denylist path prefixes; these paths will never be included."""
        self._deny_paths.extend(paths)
        return self

    def trace(self, enabled: bool = True, *, trace_dir: str | Path | None = None, trace_id: str | None = None) -> ContextBuilder:
        """Enable local JSONL tracing for builds."""
        self._trace = enabled
        self._trace_dir = trace_dir
        self._trace_id = trace_id
        return self

    def rag(
        self,
        enabled: bool = True,
        *,
        max_chunks: int = 20,
        chunk_max_lines: int = 120,
        chunk_overlap: int = 20,
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> ContextBuilder:
        """Enable chunk-level retrieval (RAG)."""
        self._rag = enabled
        self._rag_max_chunks = max_chunks
        self._rag_chunk_max_lines = chunk_max_lines
        self._rag_chunk_overlap = chunk_overlap
        self._rag_embedding_model = embedding_model
        return self

    def skeleton(self, enabled: bool = True) -> ContextBuilder:
        """Enable AST skeleton output (Python) to reduce context size."""
        self._skeleton = enabled
        return self

    def redact(self, enabled: bool = True) -> ContextBuilder:
        """Enable/disable secrets & PII redaction before output."""
        self._redact = enabled
        return self

    def fewshot(
        self,
        enabled: bool = True,
        *,
        examples_dir: str | Path = ".ctxeng/examples",
        max_files: int = 5,
    ) -> ContextBuilder:
        """Inject few-shot examples loaded from disk into the context."""
        self._fewshot = enabled
        self._fewshot_dir = examples_dir
        self._fewshot_max_files = max_files
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
            use_semantic=self._use_semantic,
            semantic_model=self._semantic_model,
            respect_gitignore=self._respect_gitignore,
            allow_paths=self._allow_paths,
            deny_paths=self._deny_paths,
            trace=self._trace,
            trace_dir=self._trace_dir,
            trace_id=self._trace_id,
            rag=self._rag,
            rag_max_chunks=self._rag_max_chunks,
            rag_chunk_max_lines=self._rag_chunk_max_lines,
            rag_chunk_overlap=self._rag_chunk_overlap,
            rag_embedding_model=self._rag_embedding_model,
            skeleton=self._skeleton,
            redact=self._redact,
            fewshot=self._fewshot,
            fewshot_dir=self._fewshot_dir,
            fewshot_max_files=self._fewshot_max_files,
        )
