"""Main ContextEngine — the primary public API."""

from __future__ import annotations

from pathlib import Path

from ctxeng.costs import estimate_cost, matched_pricing_model
from ctxeng.import_graph import build_import_graph, expand_with_imports
from ctxeng.models import Context, ContextFile, TokenBudget
from ctxeng.optimizer import count_tokens, detect_language, optimize_budget
from ctxeng.scorer import rank_files
from ctxeng.sources import collect_explicit, collect_filesystem, collect_git_changed


class ContextEngine:
    """
    Build perfect LLM context from your codebase.

    Example::

        from ctxeng import ContextEngine

        engine = ContextEngine(root=".", model="claude-sonnet-4")
        ctx = engine.build("Fix the authentication bug in the login flow")
        print(ctx.summary())
        # → paste ctx.to_string() into your LLM

    Args:
        root:               Root directory of your project (default: cwd).
        model:              Target model name — used to set token budget.
        budget:             Explicit TokenBudget, overrides `model`.
        max_file_size_kb:   Skip files larger than this (default: 500 KB).
        include_patterns:   Only include files matching these glob patterns.
        exclude_patterns:   Skip files matching these glob patterns.
        use_git:            Score files using git recency signal (default: True).
        use_import_graph:   Pull in files imported by high-scoring Python modules (default: True).
        import_graph_depth: How many import hops to follow (default: 1).
        use_semantic:       Use local embedding similarity as an extra scoring signal (default: False).
        semantic_model:     Sentence-transformers model name (default: all-MiniLM-L6-v2).
    """

    def __init__(
        self,
        root: str | Path = ".",
        model: str = "claude-sonnet-4",
        budget: TokenBudget | None = None,
        max_file_size_kb: int = 500,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        use_git: bool = True,
        use_import_graph: bool = True,
        import_graph_depth: int = 1,
        use_semantic: bool = False,
        semantic_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        self.root = Path(root).resolve()
        self.model = model
        self.budget = budget or TokenBudget.for_model(model)
        self.max_file_size_kb = max_file_size_kb
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.use_git = use_git
        self.use_import_graph = use_import_graph
        self.import_graph_depth = import_graph_depth
        self.use_semantic = use_semantic
        self.semantic_model = semantic_model

    def build(
        self,
        query: str = "",
        *,
        files: list[str | Path] | None = None,
        git_diff: bool = False,
        git_base: str = "HEAD",
        system_prompt: str = "",
        fmt: str = "xml",
    ) -> Context:
        """
        Build and return a Context object optimized for your query.

        Args:
            query:          What you're asking the LLM to do. More specific = better scoring.
            files:          Explicit list of files to include (bypasses auto-discovery).
            git_diff:       Only include files changed since `git_base`.
            git_base:       Git ref for diff base (default: HEAD).
            system_prompt:  Optional system prompt (counts against token budget).
            fmt:            Output format hint, passed through to Context.

        Returns:
            A :class:`Context` object. Call ``.to_string()`` to get the LLM-ready string,
            or ``.summary()`` to see what was included and why.
        """
        # 1. Collect raw files
        raw: list[tuple[Path, str]] = []

        if files:
            explicit_paths = [Path(f) for f in files]
            raw.extend(collect_explicit(explicit_paths, self.root))
        elif git_diff:
            raw.extend(collect_git_changed(self.root, base=git_base))
        else:
            raw.extend(
                collect_filesystem(
                    self.root,
                    max_file_size_kb=self.max_file_size_kb,
                    include_patterns=self.include_patterns,
                    exclude_patterns=self.exclude_patterns,
                )
            )

        # 2. Score and rank
        ranked = rank_files(
            raw,
            query,
            self.root,
            use_semantic=self.use_semantic,
            semantic_model=self.semantic_model,
        )

        # 3. Build ContextFile objects
        context_files = [
            ContextFile(
                path=path,
                content=content,
                relevance_score=score,
                language=detect_language(path),
            )
            for path, content, score in ranked
        ]

        if self.use_import_graph and self.import_graph_depth > 0:
            paths_in_raw = [p for p, _ in raw]
            graph = build_import_graph(self.root, paths_in_raw)
            context_files = expand_with_imports(
                context_files,
                graph,
                self.root,
                max_depth=self.import_graph_depth,
            )

        # 4. Optimize for token budget
        query_tokens = count_tokens(query, self.model) if query else 0
        system_tokens = count_tokens(system_prompt, self.model) if system_prompt else 0

        included, skipped = optimize_budget(
            context_files,
            self.budget,
            query_tokens=query_tokens,
            system_tokens=system_tokens,
            model=self.model,
        )

        total_tokens = sum(f.token_count for f in included) + query_tokens + system_tokens

        # 5. Gather metadata and cost hint
        metadata = self._gather_metadata()
        metadata["model"] = self.model
        pk = matched_pricing_model(self.model)
        if pk:
            metadata["pricing_model"] = pk
        cost_estimate = estimate_cost(total_tokens, self.model)

        return Context(
            files=included,
            system_prompt=system_prompt,
            query=query,
            total_tokens=total_tokens,
            budget=self.budget,
            skipped_files=skipped,
            metadata=metadata,
            cost_estimate=cost_estimate,
        )

    def _gather_metadata(self) -> dict:
        meta: dict = {"project_root": str(self.root)}
        try:
            import subprocess
            r = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.root, capture_output=True, text=True, timeout=2
            )
            if r.returncode == 0:
                meta["git_branch"] = r.stdout.strip()
            r2 = subprocess.run(
                ["git", "log", "-1", "--format=%h %s"],
                cwd=self.root, capture_output=True, text=True, timeout=2
            )
            if r2.returncode == 0:
                meta["last_commit"] = r2.stdout.strip()
        except Exception:
            pass
        return meta
