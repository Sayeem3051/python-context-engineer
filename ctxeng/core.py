"""Main ContextEngine — the primary public API."""

from __future__ import annotations

from pathlib import Path

from ctxeng.costs import estimate_cost, matched_pricing_model
from ctxeng.import_graph import build_import_graph, expand_with_imports
from ctxeng.fewshot import load_fewshot_examples
from ctxeng.models import Context, ContextFile, TokenBudget
from ctxeng.optimizer import count_tokens, detect_language, optimize_budget
from ctxeng.ast_skeleton import python_skeleton
from ctxeng.redaction import redact_text
from ctxeng.retrieval import retrieve_chunks_embeddings, retrieve_chunks_lexical
from ctxeng.scorer import rank_files
from ctxeng.sources import collect_explicit, collect_filesystem, collect_git_changed
from ctxeng.tracing import TraceConfig, TraceWriter


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
        respect_gitignore: bool = True,
        allow_paths: list[str | Path] | None = None,
        deny_paths: list[str | Path] | None = None,
        trace: bool = False,
        trace_dir: str | Path | None = None,
        trace_id: str | None = None,
        rag: bool = False,
        rag_max_chunks: int = 20,
        rag_chunk_max_lines: int = 120,
        rag_chunk_overlap: int = 20,
        rag_embedding_model: str = "all-MiniLM-L6-v2",
        skeleton: bool = False,
        fewshot: bool = False,
        fewshot_dir: str | Path = ".ctxeng/examples",
        fewshot_max_files: int = 5,
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
        self.respect_gitignore = respect_gitignore
        self.allow_paths = allow_paths or []
        self.deny_paths = deny_paths or []
        self.trace_config = TraceConfig(
            enabled=trace,
            trace_dir=Path(trace_dir).resolve() if trace_dir else None,
            trace_id=trace_id,
        )
        self.rag = rag
        self.rag_max_chunks = rag_max_chunks
        self.rag_chunk_max_lines = rag_chunk_max_lines
        self.rag_chunk_overlap = rag_chunk_overlap
        self.rag_embedding_model = rag_embedding_model
        self.skeleton = skeleton
        self.fewshot = fewshot
        self.fewshot_dir = fewshot_dir
        self.fewshot_max_files = fewshot_max_files

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
        trace_writer: TraceWriter | None = None
        if self.trace_config.enabled:
            trace_writer = TraceWriter(self.root, self.trace_config)
            trace_writer.emit(
                "build_start",
                root=str(self.root),
                model=self.model,
                budget_total=self.budget.total,
                budget_available=self.budget.available,
                fmt=fmt,
                git_diff=git_diff,
                import_graph=self.use_import_graph,
                import_graph_depth=self.import_graph_depth,
                semantic=self.use_semantic,
                respect_gitignore=self.respect_gitignore,
            )

        # 1. Collect raw files
        raw: list[tuple[Path, str]] = []

        if files:
            explicit_paths = [Path(f) for f in files]
            raw.extend(
                collect_explicit(
                    explicit_paths,
                    self.root,
                    respect_gitignore=self.respect_gitignore,
                    allow_paths=self.allow_paths,
                    deny_paths=self.deny_paths,
                )
            )
        elif git_diff:
            raw.extend(
                collect_git_changed(
                    self.root,
                    base=git_base,
                    respect_gitignore=self.respect_gitignore,
                    allow_paths=self.allow_paths,
                    deny_paths=self.deny_paths,
                )
            )
        else:
            raw.extend(
                collect_filesystem(
                    self.root,
                    max_file_size_kb=self.max_file_size_kb,
                    include_patterns=self.include_patterns,
                    exclude_patterns=self.exclude_patterns,
                    respect_gitignore=self.respect_gitignore,
                    allow_paths=self.allow_paths,
                    deny_paths=self.deny_paths,
                )
            )

        if trace_writer:
            trace_writer.emit("collected_files", count=len(raw))

        # 2. Score and rank
        ranked = rank_files(
            raw,
            query,
            self.root,
            use_semantic=self.use_semantic,
            semantic_model=self.semantic_model,
        )

        if trace_writer:
            trace_writer.emit(
                "ranked_files",
                top=[
                    {"path": p, "score": float(s)}
                    for p, _c, s in ranked[: min(25, len(ranked))]
                ],
            )

        # 2b. Optional RAG chunk retrieval (replaces whole-file content with top chunks)
        if self.rag and query:
            # Candidate set: take top K files so chunking stays fast.
            candidates = [(p, c) for p, c, _s in ranked[: min(40, len(ranked))]]
            retrieved = []
            method = "lexical"
            try:
                retrieved = retrieve_chunks_embeddings(
                    candidates,
                    query,
                    max_chunks=self.rag_max_chunks,
                    chunk_max_lines=self.rag_chunk_max_lines,
                    chunk_overlap=self.rag_chunk_overlap,
                    model_name=self.rag_embedding_model,
                )
                method = "embedding"
            except ImportError:
                retrieved = retrieve_chunks_lexical(
                    candidates,
                    query,
                    max_chunks=self.rag_max_chunks,
                    chunk_max_lines=self.rag_chunk_max_lines,
                    chunk_overlap=self.rag_chunk_overlap,
                )
                method = "lexical"

            # Build pseudo-files for each retrieved chunk (same underlying path).
            # We encode span in content header for now; later we’ll add structured spans.
            ranked = [
                (
                    rc.chunk.path,
                    f"# [ctxeng:chunk {rc.chunk.start_line}-{rc.chunk.end_line} method={rc.method} score={rc.score:.4f}]\n"
                    + rc.chunk.text,
                    min(1.0, float(rc.score) if method == "embedding" else 1.0),
                )
                for rc in retrieved
            ]
            if trace_writer:
                trace_writer.emit(
                    "rag_retrieval",
                    method=method,
                    retrieved=len(retrieved),
                    chunks=[
                        {
                            "id": rc.chunk.id(),
                            "path": rc.chunk.path,
                            "start_line": rc.chunk.start_line,
                            "end_line": rc.chunk.end_line,
                            "score": float(rc.score),
                            "method": rc.method,
                        }
                        for rc in retrieved[: min(50, len(retrieved))]
                    ],
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

        # 3b. Optional skeleton mode (Python only): replace full body with AST outline
        if self.skeleton:
            for f in context_files:
                if (f.language or "").lower() == "python" or f.path.suffix.lower() == ".py":
                    sk = python_skeleton(f.content)
                    f.content = sk.text

        if self.use_import_graph and self.import_graph_depth > 0:
            paths_in_raw = [p for p, _ in raw]
            graph = build_import_graph(self.root, paths_in_raw)
            context_files = expand_with_imports(
                context_files,
                graph,
                self.root,
                max_depth=self.import_graph_depth,
            )

        # 4. Redact sensitive info before budgeting/output
        redacted_files = 0
        redacted_total = 0
        for f in context_files:
            r = redact_text(f.content, redact_secrets=True, redact_pii=True)
            if r.total:
                f.content = r.text
                f.redaction_count = r.total
                redacted_files += 1
                redacted_total += r.total

        if trace_writer:
            trace_writer.emit(
                "redaction_summary",
                files_with_redactions=redacted_files,
                total_redactions=redacted_total,
            )

        # 5. Optimize for token budget
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

        # 6. Gather metadata and cost hint
        metadata = self._gather_metadata()
        metadata["model"] = self.model
        if trace_writer:
            metadata["trace_id"] = trace_writer.trace_id
            metadata["trace_path"] = str(trace_writer.path)
        pk = matched_pricing_model(self.model)
        if pk:
            metadata["pricing_model"] = pk
        cost_estimate = estimate_cost(total_tokens, self.model)

        fewshot_examples = (
            load_fewshot_examples(self.root, examples_dir=self.fewshot_dir, max_files=self.fewshot_max_files)
            if self.fewshot
            else []
        )

        ctx = Context(
            files=included,
            system_prompt=system_prompt,
            query=query,
            total_tokens=total_tokens,
            budget=self.budget,
            skipped_files=skipped,
            metadata=metadata,
            cost_estimate=cost_estimate,
            fewshot_examples=fewshot_examples,
        )

        if trace_writer:
            trace_writer.emit(
                "budget_result",
                query_tokens=query_tokens,
                system_tokens=system_tokens,
                included=len(included),
                skipped=len(skipped),
                total_tokens=total_tokens,
                included_files=[
                    {
                        "path": f.path,
                        "score": float(f.relevance_score),
                        "tokens": int(f.token_count),
                        "truncated": bool(f.is_truncated),
                        "redactions": int(getattr(f, "redaction_count", 0)),
                    }
                    for f in included
                ],
            )
            trace_writer.emit("build_done", cost_estimate=cost_estimate)
            trace_writer.close()

        return ctx

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
