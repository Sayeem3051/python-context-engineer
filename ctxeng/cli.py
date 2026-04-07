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


def cmd_build(args: argparse.Namespace) -> None:
    from ctxeng import ContextBuilder

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
    else:
        print(ctx.to_string(args.fmt))


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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
