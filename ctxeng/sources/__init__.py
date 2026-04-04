"""Source collectors: gather raw files from different origins."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

# File extensions that are likely source code / config (not binary)
TEXT_EXTENSIONS: set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".kt",
    ".swift", ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".sh",
    ".bash", ".zsh", ".fish", ".sql", ".html", ".css", ".scss", ".less",
    ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".md", ".mdx", ".rst", ".txt", ".tf", ".hcl", ".dockerfile",
    ".makefile", ".r", ".scala", ".ex", ".exs", ".erl", ".clj", ".hs",
    ".ml", ".mli", ".lua", ".vim", ".el",
}

# Directories to always skip
SKIP_DIRS: set[str] = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "venv", ".venv", "env", ".env",
    "dist", "build", "target", ".next", ".nuxt", "out", "coverage",
    ".tox", "htmlcov", "eggs", ".eggs", "*.egg-info",
    ".idea", ".vscode", ".DS_Store",
}


def _is_text_file(path: Path) -> bool:
    """Return True if the path looks like a readable text/source file."""
    name = path.name.lower()
    if name in {"dockerfile", "makefile", "procfile", "gemfile", "pipfile"}:
        return True
    if name.startswith(".env"):
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS


def _should_skip_dir(dir_path: Path) -> bool:
    name = dir_path.name
    return name in SKIP_DIRS or name.endswith(".egg-info")


def collect_filesystem(
    root: Path,
    max_file_size_kb: int = 500,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> Iterator[tuple[Path, str]]:
    """
    Walk the filesystem from `root` and yield (path, content) for source files.

    Args:
        root:               Root directory to walk.
        max_file_size_kb:   Skip files larger than this (default 500 KB).
        include_patterns:   If set, only include files matching these glob patterns.
        exclude_patterns:   Skip files matching these glob patterns.

    Yields:
        (relative_path, file_content) tuples.
    """
    max_bytes = max_file_size_kb * 1024

    for path in sorted(root.rglob("*")):
        # Skip directories themselves
        if path.is_dir():
            continue

        # Skip excluded directories anywhere in the path
        if any(_should_skip_dir(p) for p in path.parents):
            continue

        if not _is_text_file(path):
            continue

        # Size guard
        try:
            if path.stat().st_size > max_bytes:
                continue
        except OSError:
            continue

        # Pattern filtering
        rel = path.relative_to(root)
        if include_patterns and not any(path.match(p) for p in include_patterns):
            continue
        if exclude_patterns and any(path.match(p) for p in exclude_patterns):
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if content.strip():
            yield rel, content


def collect_git_changed(
    root: Path,
    base: str = "HEAD",
    include_untracked: bool = True,
) -> Iterator[tuple[Path, str]]:
    """
    Yield files that have changed relative to `base` (git diff).

    Great for building focused context around a PR or current working changes.

    Args:
        root:               Repository root.
        base:               Git ref to diff against (default: HEAD).
        include_untracked:  Also yield untracked (new) files.

    Yields:
        (relative_path, content) for each changed file.
    """
    changed: list[str] = []

    # Staged + unstaged changes
    for flag in ["--cached", ""]:
        cmd = ["git", "diff", flag, "--name-only", base]
        cmd = [c for c in cmd if c]  # remove empty strings
        try:
            result = subprocess.run(
                cmd, cwd=root, capture_output=True, text=True, timeout=5
            )
            changed.extend(result.stdout.strip().splitlines())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    if include_untracked:
        try:
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=root, capture_output=True, text=True, timeout=5
            )
            changed.extend(result.stdout.strip().splitlines())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    seen: set[str] = set()
    for rel_str in changed:
        if rel_str in seen:
            continue
        seen.add(rel_str)
        path = root / rel_str
        if not path.exists() or not _is_text_file(path):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            yield Path(rel_str), content
        except OSError:
            continue


def collect_explicit(
    paths: list[Path],
    root: Path,
) -> Iterator[tuple[Path, str]]:
    """Yield content for explicitly specified files."""
    for path in paths:
        abs_path = path if path.is_absolute() else root / path
        if not abs_path.exists():
            continue
        try:
            content = abs_path.read_text(encoding="utf-8", errors="replace")
            rel = abs_path.relative_to(root) if abs_path.is_relative_to(root) else abs_path
            yield rel, content
        except OSError:
            continue
