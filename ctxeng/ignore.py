"""Ignore matching for ctxeng (gitignore-style patterns)."""

from __future__ import annotations

from pathlib import Path

from pathspec.gitignore import GitIgnoreSpec
from pathspec.pathspec import PathSpec


def parse_ctxengignore(root: Path) -> list[str]:
    """
    Read ``.ctxengignore`` at the project root and return non-empty pattern lines.

    Uses the same pattern syntax as ``.gitignore`` (via gitwildmatch). If the file
    is missing, returns an empty list. Blank lines and lines starting with ``#``
    are skipped.

    Args:
        root: Project root directory (must be resolved or absolute for consistent
            behavior).

    Returns:
        List of pattern strings suitable for :class:`pathspec.PathSpec`.
    """
    path = root / ".ctxengignore"
    if not path.is_file():
        return []

    patterns: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    for line in text.splitlines():
        line = line.rstrip("\r\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(line.rstrip())

    return patterns


def parse_gitignore(root: Path) -> list[str]:
    """
    Read `.gitignore` at the project root and return non-empty pattern lines.

    This is intentionally conservative (root `.gitignore` only). It is used to
    prevent accidental inclusion of ignored files when ctxeng walks the filesystem.
    If the file is missing or unreadable, returns [].
    """
    path = root / ".gitignore"
    if not path.is_file():
        return []

    patterns: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    for line in text.splitlines():
        line = line.rstrip("\r\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(line.rstrip())

    return patterns


def ctxengignore_pathspec(patterns: list[str]) -> PathSpec | None:
    """
    Build a :class:`~pathspec.PathSpec` for ignore matching, or ``None`` if empty.

    Args:
        patterns: Output of :func:`parse_ctxengignore`.

    Returns:
        A path spec that matches paths that should be excluded, or ``None``.
    """
    if not patterns:
        return None
    return GitIgnoreSpec.from_lines(patterns)


def combined_ignore_spec(
    *,
    ctxeng_patterns: list[str] | None = None,
    gitignore_patterns: list[str] | None = None,
) -> PathSpec | None:
    """
    Build a single PathSpec that merges `.gitignore` and `.ctxengignore` patterns.

    `.ctxengignore` patterns are appended after `.gitignore` patterns so they can
    further exclude (or negate via `!`) with familiar gitignore semantics.
    """
    patterns: list[str] = []
    patterns.extend(gitignore_patterns or [])
    patterns.extend(ctxeng_patterns or [])
    return ctxengignore_pathspec(patterns)


def is_ctxengignored(rel_path: Path, spec: PathSpec | None) -> bool:
    """
    Return ``True`` if ``rel_path`` (relative to project root, POSIX separators) is ignored.

    Args:
        rel_path: Path relative to the project root.
        spec: Ignore spec from :func:`ctxengignore_pathspec`, or ``None``.
    """
    if spec is None:
        return False
    rel_posix = rel_path.as_posix()
    return spec.match_file(rel_posix)
