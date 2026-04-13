"""
ctxeng CLI — build and inspect context from the command line.

Usage:
    ctxeng build "Fix the auth bug"
    ctxeng build "Refactor payment module" --model gpt-4o --fmt markdown
    ctxeng build "Review my changes" --git-diff
    ctxeng build "Explain this file" --files src/core.py src/models.py
    ctxeng info
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_ci(args: argparse.Namespace) -> None:
    """
    CI-friendly wrapper around `build` that always writes to a file and exits
    non-interactively.
    """
    from ctxeng import ContextBuilder
    from ctxeng.snapshots import write_snapshot

    builder = (
        ContextBuilder(root=args.root)
        .for_model(args.model)
        .max_file_size(args.max_size)
    )
    if args.allow:
        builder = builder.allow(*args.allow)
    if args.deny:
        builder = builder.deny(*args.deny)
    if not args.gitignore:
        builder = builder.no_gitignore()
    if args.trace:
        builder = builder.trace(True, trace_dir=args.trace_dir, trace_id=args.trace_id)
    if args.rag:
        builder = builder.rag(
            True,
            max_chunks=args.rag_max_chunks,
            chunk_max_lines=args.rag_chunk_max_lines,
            chunk_overlap=args.rag_chunk_overlap,
            embedding_model=args.rag_embedding_model,
        )
    if args.skeleton:
        builder = builder.skeleton(True)
    if args.fewshot:
        builder = builder.fewshot(True, examples_dir=args.fewshot_dir, max_files=args.fewshot_max_files)
    if args.budget:
        builder = builder.with_budget(args.budget)
    if args.git_diff:
        builder = builder.from_git_diff(args.git_base)

    query = " ".join(args.query) if args.query else ""
    ctx = builder.build(query)
    out_path = Path(args.output)
    out_path.write_text(ctx.to_string(args.fmt), encoding="utf-8")
    print(ctx.summary(show_cost=True), file=sys.stderr)
    print(f"Written to: {out_path}", file=sys.stderr)
    if args.snapshot:
        snap_dir = write_snapshot(Path(args.root), ctx, fmt=args.fmt, snapshot_id=args.snapshot_id)
        print(f"Snapshot saved: {snap_dir}", file=sys.stderr)


def cmd_build(args: argparse.Namespace) -> None:
    from ctxeng import ContextBuilder
    from ctxeng.snapshots import write_snapshot

    builder = (
        ContextBuilder(root=args.root)
        .for_model(args.model)
        .max_file_size(args.max_size)
    )

    if args.only:
        builder = builder.only(*args.only)
    if args.exclude:
        builder = builder.exclude(*args.exclude)
    if args.files:
        builder = builder.include_files(*args.files)
    if args.git_diff:
        builder = builder.from_git_diff(args.git_base)
    if args.system:
        builder = builder.with_system(args.system)
    if args.no_git:
        builder = builder.no_git()
    if not args.gitignore:
        builder = builder.no_gitignore()
    if args.allow:
        builder = builder.allow(*args.allow)
    if args.deny:
        builder = builder.deny(*args.deny)
    if args.trace:
        builder = builder.trace(True, trace_dir=args.trace_dir, trace_id=args.trace_id)
    if args.rag:
        builder = builder.rag(
            True,
            max_chunks=args.rag_max_chunks,
            chunk_max_lines=args.rag_chunk_max_lines,
            chunk_overlap=args.rag_chunk_overlap,
            embedding_model=args.rag_embedding_model,
        )
    if args.skeleton:
        builder = builder.skeleton(True)
    if args.fewshot:
        builder = builder.fewshot(True, examples_dir=args.fewshot_dir, max_files=args.fewshot_max_files)
    if not args.import_graph:
        builder = builder.no_import_graph()
    else:
        builder = builder.use_import_graph(depth=args.import_graph_depth)
    if args.semantic:
        builder = builder.use_semantic(model=args.semantic_model)
    if args.budget:
        builder = builder.with_budget(args.budget)

    query = " ".join(args.query) if args.query else ""

    print(f"Building context for: {query!r}", file=sys.stderr)
    print(f"Root: {Path(args.root).resolve()}", file=sys.stderr)
    print(f"Model: {args.model}", file=sys.stderr)
    print("", file=sys.stderr)

    ctx = builder.build(query)

    print(ctx.summary(show_cost=args.show_cost), file=sys.stderr)
    print("", file=sys.stderr)
    print("─" * 60, file=sys.stderr)
    print("Context output:", file=sys.stderr)
    print("─" * 60, file=sys.stderr)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(ctx.to_string(args.fmt), encoding="utf-8")
        print(f"Written to: {out_path}", file=sys.stderr)
        if args.snapshot:
            snap_dir = write_snapshot(Path(args.root), ctx, fmt=args.fmt, snapshot_id=args.snapshot_id)
            print(f"Snapshot saved: {snap_dir}", file=sys.stderr)
    else:
        # Handle Unicode encoding for Windows console
        try:
            print(ctx.to_string(args.fmt))
        except UnicodeEncodeError:
            # Fallback: encode with error handling for Windows console
            output = ctx.to_string(args.fmt)
            # Replace problematic Unicode characters with ASCII equivalents
            output = output.replace('🔐', '[KEY]').replace('📁', '[FOLDER]').replace('📄', '[FILE]')
            output = output.replace('✅', '[OK]').replace('❌', '[ERROR]').replace('⚠️', '[WARN]')
            output = output.replace('💡', '[TIP]').replace('🔧', '[TOOL]').replace('📊', '[STATS]')
            # Remove other Unicode characters that might cause issues
            output = output.encode('ascii', errors='replace').decode('ascii')
            print(output)
        except Exception as e:
            # Last resort: output without special characters
            print(f"Context generated successfully but output encoding failed: {e}", file=sys.stderr)
            print("Context contains Unicode characters that cannot be displayed in this console.", file=sys.stderr)
            print("Try using --output flag to save to a file instead.", file=sys.stderr)
        finally:
            if args.snapshot:
                snap_dir = write_snapshot(Path(args.root), ctx, fmt=args.fmt, snapshot_id=args.snapshot_id)
                print(f"Snapshot saved: {snap_dir}", file=sys.stderr)


def cmd_info(args: argparse.Namespace) -> None:
    import subprocess

    from ctxeng.optimizer import count_tokens, detect_language
    from ctxeng.sources import collect_filesystem

    root = Path(args.root).resolve()
    print(f"Project: {root}")

    # Git info
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           cwd=root, capture_output=True, text=True, timeout=2)
        if r.returncode == 0:
            print(f"Branch:  {r.stdout.strip()}")
        r2 = subprocess.run(["git", "log", "-1", "--format=%h %s"],
                             cwd=root, capture_output=True, text=True, timeout=2)
        if r2.returncode == 0:
            print(f"Commit:  {r2.stdout.strip()}")
    except Exception:
        print("Git:     not available")

    print()
    files = list(collect_filesystem(root))
    lang_counts: dict[str, int] = {}
    total_tokens = 0
    for path, content in files:
        lang = detect_language(path) or "other"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        total_tokens += count_tokens(content)

    print(f"Files found: {len(files)}")
    print(f"Estimated total tokens: {total_tokens:,}")
    print()
    print("By language:")
    for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1])[:10]:
        bar = "█" * min(20, count)
        print(f"  {lang:<15} {bar}  {count}")


def cmd_watch(args: argparse.Namespace) -> None:
    from ctxeng import ContextBuilder
    from ctxeng.watcher import ContextWatcher, WatchConfig

    builder = (
        ContextBuilder(root=args.root)
        .for_model(args.model)
        .max_file_size(args.max_size)
    )

    if args.only:
        builder = builder.only(*args.only)
    if args.exclude:
        builder = builder.exclude(*args.exclude)
    if args.files:
        builder = builder.include_files(*args.files)
    if args.system:
        builder = builder.with_system(args.system)
    if args.no_git:
        builder = builder.no_git()
    if not args.gitignore:
        builder = builder.no_gitignore()
    if args.allow:
        builder = builder.allow(*args.allow)
    if args.deny:
        builder = builder.deny(*args.deny)
    if args.trace:
        builder = builder.trace(True, trace_dir=args.trace_dir, trace_id=args.trace_id)
    if args.rag:
        builder = builder.rag(
            True,
            max_chunks=args.rag_max_chunks,
            chunk_max_lines=args.rag_chunk_max_lines,
            chunk_overlap=args.rag_chunk_overlap,
            embedding_model=args.rag_embedding_model,
        )
    if args.skeleton:
        builder = builder.skeleton(True)
    if not args.import_graph:
        builder = builder.no_import_graph()
    else:
        builder = builder.use_import_graph(depth=args.import_graph_depth)
    if args.semantic:
        builder = builder.use_semantic(model=args.semantic_model)
    if args.budget:
        builder = builder.with_budget(args.budget)

    query = " ".join(args.query) if args.query else ""

    engine = builder._build_engine()
    watcher = ContextWatcher(
        query,
        engine=engine,
        output_file=args.output,
        fmt=args.fmt,
        config=WatchConfig(interval_seconds=args.interval),
    )
    watcher.run()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ctxeng",
        description="Build perfect LLM context from your codebase.",
    )
    parser.add_argument("--root", default=".", help="Project root (default: cwd)")

    sub = parser.add_subparsers(dest="command", required=True)

    # --- build ---
    build_p = sub.add_parser("build", help="Build context for a query")
    build_p.add_argument("query", nargs="*", help="What you want the LLM to do")
    build_p.add_argument("--model", "-m", default="claude-sonnet-4",
                         help="Target model (default: claude-sonnet-4)")
    build_p.add_argument("--fmt", "-f", default="xml",
                         choices=["xml", "markdown", "plain"],
                         help="Output format (default: xml)")
    build_p.add_argument("--output", "-o", help="Write output to file instead of stdout")
    build_p.add_argument(
        "--snapshot",
        action="store_true",
        help="Save a versioned context snapshot under <root>/.ctxeng/snapshots/",
    )
    build_p.add_argument(
        "--snapshot-id",
        help="Optional snapshot id (default: random uuid)",
    )
    build_p.add_argument("--only", nargs="+", metavar="PATTERN",
                         help='Include only matching globs, e.g. "**/*.py"')
    build_p.add_argument("--exclude", nargs="+", metavar="PATTERN",
                         help="Exclude matching globs")
    build_p.add_argument("--files", nargs="+", metavar="FILE",
                         help="Explicit list of files to include")
    build_p.add_argument("--git-diff", action="store_true",
                         help="Only include git-changed files")
    build_p.add_argument("--git-base", default="HEAD",
                         help="Git base ref for diff (default: HEAD)")
    build_p.add_argument("--system", help="System prompt text")
    build_p.add_argument("--no-git", action="store_true",
                         help="Disable git recency scoring")
    build_p.add_argument(
        "--gitignore",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Respect .gitignore in addition to .ctxengignore (default: on)",
    )
    build_p.add_argument(
        "--allow",
        nargs="+",
        metavar="PATH",
        help="Allowlist path prefixes; only these paths may be included",
    )
    build_p.add_argument(
        "--deny",
        nargs="+",
        metavar="PATH",
        help="Denylist path prefixes; these paths will never be included",
    )
    build_p.add_argument(
        "--trace",
        action="store_true",
        help="Write a JSONL trace of selection/budget decisions to .ctxeng/traces/",
    )
    build_p.add_argument(
        "--trace-dir",
        help="Override trace output directory (default: <root>/.ctxeng/traces/)",
    )
    build_p.add_argument(
        "--trace-id",
        help="Provide a custom trace id (default: random)",
    )
    build_p.add_argument(
        "--rag",
        action="store_true",
        help="Enable chunk-level retrieval (RAG) instead of whole-file inclusion",
    )
    build_p.add_argument(
        "--rag-max-chunks",
        type=int,
        default=20,
        help="Max chunks to retrieve when --rag is enabled (default: 20)",
    )
    build_p.add_argument(
        "--rag-chunk-max-lines",
        type=int,
        default=120,
        help="Chunk size in lines for --rag (default: 120)",
    )
    build_p.add_argument(
        "--rag-chunk-overlap",
        type=int,
        default=20,
        help="Chunk overlap in lines for --rag (default: 20)",
    )
    build_p.add_argument(
        "--rag-embedding-model",
        default="all-MiniLM-L6-v2",
        help="Sentence-transformers model name for --rag embeddings (default: all-MiniLM-L6-v2)",
    )
    build_p.add_argument(
        "--skeleton",
        action="store_true",
        help="Use AST skeletons for Python files (signatures/outline instead of full bodies)",
    )
    build_p.add_argument(
        "--fewshot",
        action="store_true",
        help="Inject few-shot examples from .ctxeng/examples into the context",
    )
    build_p.add_argument(
        "--fewshot-dir",
        default=".ctxeng/examples",
        help="Few-shot examples directory (default: .ctxeng/examples)",
    )
    build_p.add_argument(
        "--fewshot-max-files",
        type=int,
        default=5,
        help="Max few-shot example files to include (default: 5)",
    )
    build_p.add_argument("--budget", type=int,
                         help="Override token budget total")
    build_p.add_argument("--max-size", type=int, default=500,
                         help="Max file size in KB (default: 500)")
    build_p.add_argument(
        "--import-graph",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Expand context using local Python import graph (default: on)",
    )
    build_p.add_argument(
        "--import-graph-depth",
        type=int,
        default=1,
        metavar="N",
        help="Import hops when --import-graph is on (default: 1)",
    )
    build_p.add_argument(
        "--show-cost",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show estimated API cost in stderr summary (default: on)",
    )
    build_p.add_argument(
        "--semantic",
        action="store_true",
        help="Enable semantic similarity scoring (requires sentence-transformers)",
    )
    build_p.add_argument(
        "--semantic-model",
        default="all-MiniLM-L6-v2",
        help="Sentence-transformers model name (default: all-MiniLM-L6-v2)",
    )
    build_p.set_defaults(func=cmd_build)

    # --- info ---
    info_p = sub.add_parser("info", help="Show project info and file stats")
    info_p.set_defaults(func=cmd_info)

    # --- watch ---
    watch_p = sub.add_parser("watch", help="Watch files and auto-rebuild context")
    watch_p.add_argument("query", nargs="*", help="What you want the LLM to do")
    watch_p.add_argument("--model", "-m", default="claude-sonnet-4",
                         help="Target model (default: claude-sonnet-4)")
    watch_p.add_argument("--fmt", "-f", default="xml",
                         choices=["xml", "markdown", "plain"],
                         help="Output format (default: xml)")
    watch_p.add_argument("--output", "-o", help="Write output to file after each rebuild")
    watch_p.add_argument("--only", nargs="+", metavar="PATTERN",
                         help='Include only matching globs, e.g. "**/*.py"')
    watch_p.add_argument("--exclude", nargs="+", metavar="PATTERN",
                         help="Exclude matching globs")
    watch_p.add_argument("--files", nargs="+", metavar="FILE",
                         help="Explicit list of files to include")
    watch_p.add_argument("--system", help="System prompt text")
    watch_p.add_argument("--no-git", action="store_true",
                         help="Disable git recency scoring")
    watch_p.add_argument(
        "--gitignore",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Respect .gitignore in addition to .ctxengignore (default: on)",
    )
    watch_p.add_argument(
        "--allow",
        nargs="+",
        metavar="PATH",
        help="Allowlist path prefixes; only these paths may be included",
    )
    watch_p.add_argument(
        "--deny",
        nargs="+",
        metavar="PATH",
        help="Denylist path prefixes; these paths will never be included",
    )
    watch_p.add_argument(
        "--trace",
        action="store_true",
        help="Write a JSONL trace of selection/budget decisions to .ctxeng/traces/",
    )
    watch_p.add_argument(
        "--trace-dir",
        help="Override trace output directory (default: <root>/.ctxeng/traces/)",
    )
    watch_p.add_argument(
        "--trace-id",
        help="Provide a custom trace id (default: random)",
    )
    watch_p.add_argument(
        "--rag",
        action="store_true",
        help="Enable chunk-level retrieval (RAG) instead of whole-file inclusion",
    )
    watch_p.add_argument(
        "--rag-max-chunks",
        type=int,
        default=20,
        help="Max chunks to retrieve when --rag is enabled (default: 20)",
    )
    watch_p.add_argument(
        "--rag-chunk-max-lines",
        type=int,
        default=120,
        help="Chunk size in lines for --rag (default: 120)",
    )
    watch_p.add_argument(
        "--rag-chunk-overlap",
        type=int,
        default=20,
        help="Chunk overlap in lines for --rag (default: 20)",
    )
    watch_p.add_argument(
        "--rag-embedding-model",
        default="all-MiniLM-L6-v2",
        help="Sentence-transformers model name for --rag embeddings (default: all-MiniLM-L6-v2)",
    )
    watch_p.add_argument(
        "--skeleton",
        action="store_true",
        help="Use AST skeletons for Python files (signatures/outline instead of full bodies)",
    )
    watch_p.add_argument(
        "--fewshot",
        action="store_true",
        help="Inject few-shot examples from .ctxeng/examples into the context",
    )
    watch_p.add_argument(
        "--fewshot-dir",
        default=".ctxeng/examples",
        help="Few-shot examples directory (default: .ctxeng/examples)",
    )
    watch_p.add_argument(
        "--fewshot-max-files",
        type=int,
        default=5,
        help="Max few-shot example files to include (default: 5)",
    )
    watch_p.add_argument("--budget", type=int,
                         help="Override token budget total")
    watch_p.add_argument("--max-size", type=int, default=500,
                         help="Max file size in KB (default: 500)")
    watch_p.add_argument(
        "--import-graph",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Expand context using local Python import graph (default: on)",
    )
    watch_p.add_argument(
        "--import-graph-depth",
        type=int,
        default=1,
        metavar="N",
        help="Import hops when --import-graph is on (default: 1)",
    )
    watch_p.add_argument(
        "--interval",
        type=float,
        default=1.0,
        metavar="S",
        help="Polling interval in seconds (default: 1.0)",
    )
    watch_p.add_argument(
        "--semantic",
        action="store_true",
        help="Enable semantic similarity scoring (requires sentence-transformers)",
    )
    watch_p.add_argument(
        "--semantic-model",
        default="all-MiniLM-L6-v2",
        help="Sentence-transformers model name (default: all-MiniLM-L6-v2)",
    )
    watch_p.set_defaults(func=cmd_watch)

    # --- ci ---
    ci_p = sub.add_parser("ci", help="CI-friendly context generation")
    ci_p.add_argument("query", nargs="*", help="What you want the LLM to do")
    ci_p.add_argument("--model", "-m", default="claude-sonnet-4",
                      help="Target model (default: claude-sonnet-4)")
    ci_p.add_argument("--fmt", "-f", default="xml",
                      choices=["xml", "markdown", "plain"],
                      help="Output format (default: xml)")
    ci_p.add_argument("--output", "-o", required=True, help="Write context output to this file")
    ci_p.add_argument("--budget", type=int, help="Override token budget total")
    ci_p.add_argument("--max-size", type=int, default=500, help="Max file size in KB (default: 500)")
    ci_p.add_argument("--git-diff", action="store_true", help="Only include git-changed files")
    ci_p.add_argument("--git-base", default="HEAD", help="Git base ref for diff (default: HEAD)")
    ci_p.add_argument("--gitignore", action=argparse.BooleanOptionalAction, default=True,
                      help="Respect .gitignore in addition to .ctxengignore (default: on)")
    ci_p.add_argument("--allow", nargs="+", metavar="PATH", help="Allowlist path prefixes")
    ci_p.add_argument("--deny", nargs="+", metavar="PATH", help="Denylist path prefixes")
    ci_p.add_argument("--trace", action="store_true", help="Write JSONL trace under .ctxeng/traces/")
    ci_p.add_argument("--trace-dir", help="Override trace output directory")
    ci_p.add_argument("--trace-id", help="Provide a custom trace id")
    ci_p.add_argument("--rag", action="store_true", help="Enable chunk-level retrieval (RAG)")
    ci_p.add_argument("--rag-max-chunks", type=int, default=20)
    ci_p.add_argument("--rag-chunk-max-lines", type=int, default=120)
    ci_p.add_argument("--rag-chunk-overlap", type=int, default=20)
    ci_p.add_argument("--rag-embedding-model", default="all-MiniLM-L6-v2")
    ci_p.add_argument("--skeleton", action="store_true", help="Use AST skeletons for Python files")
    ci_p.add_argument("--fewshot", action="store_true", help="Inject few-shot examples from disk")
    ci_p.add_argument("--fewshot-dir", default=".ctxeng/examples")
    ci_p.add_argument("--fewshot-max-files", type=int, default=5)
    ci_p.add_argument("--snapshot", action="store_true", help="Save snapshot under .ctxeng/snapshots/")
    ci_p.add_argument("--snapshot-id", help="Optional snapshot id")
    ci_p.set_defaults(func=_cmd_ci)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
