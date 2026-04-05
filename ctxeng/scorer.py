"""Relevance scoring for source files relative to a query."""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path


def score_file(path: Path, content: str, query: str, root: Path) -> float:
    """
    Score how relevant a file is to the given query (0.0 – 1.0).

    Combines multiple signals:
        - Keyword overlap with query
        - AST symbol extraction (Python)
        - File path proximity / naming
        - Git recency (recently changed files score higher)
        (Import graph expansion runs separately in :class:`~ctxeng.core.ContextEngine`.)

    Returns a float in [0, 1].
    """
    scores: list[float] = []

    scores.append(_keyword_score(content, query))
    scores.append(_path_score(path, query))

    if path.suffix == ".py":
        scores.append(_ast_score(content, query))

    git_score = _git_recency_score(path, root)
    if git_score is not None:
        scores.append(git_score)

    # Weighted average — keyword + AST matter most
    weights = [0.4, 0.2, 0.25, 0.15]
    while len(weights) > len(scores):
        weights.pop()
    # Renormalize
    total_w = sum(weights)
    weights = [w / total_w for w in weights]

    return min(1.0, sum(s * w for s, w in zip(scores, weights, strict=False)))


def _keyword_score(content: str, query: str) -> float:
    """Fraction of query keywords that appear in the file content."""
    if not query:
        return 0.5
    # Extract meaningful tokens from query (ignore stopwords)
    stopwords = {"the", "a", "an", "in", "on", "at", "to", "for", "of",
                 "and", "or", "is", "it", "my", "me", "how", "what", "why",
                 "can", "do", "i", "with", "from", "this", "that"}
    tokens = [
        t.lower() for t in re.findall(r'\b\w{3,}\b', query)
        if t.lower() not in stopwords
    ]
    if not tokens:
        return 0.5
    content_lower = content.lower()
    hits = sum(1 for t in tokens if t in content_lower)
    # Boost for multiple occurrences
    freq_bonus = min(0.3, sum(content_lower.count(t) for t in tokens) / (len(tokens) * 20))
    return min(1.0, hits / len(tokens) + freq_bonus)


def _path_score(path: Path, query: str) -> float:
    """Score based on filename and directory names matching query terms."""
    if not query:
        return 0.3
    path_str = str(path).lower().replace("_", " ").replace("-", " ")
    tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', query)]
    if not tokens:
        return 0.3
    hits = sum(1 for t in tokens if t in path_str)
    return min(1.0, hits / len(tokens))


def _ast_score(content: str, query: str) -> float:
    """
    Parse Python AST and score based on symbol name overlap with query.

    Extracts: class names, function names, variable names, decorators.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return 0.0

    symbols: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name.lower())
        elif isinstance(node, ast.Name):
            symbols.append(node.id.lower())
        elif isinstance(node, ast.Import):
            for alias in node.names:
                symbols.append(alias.name.split(".")[0].lower())
        elif isinstance(node, ast.ImportFrom) and node.module:
            symbols.append(node.module.split(".")[0].lower())

    if not symbols or not query:
        return 0.3

    query_tokens = set(re.findall(r'\b\w{3,}\b', query.lower()))
    symbol_set = set(symbols)
    overlap = query_tokens & symbol_set
    return min(1.0, len(overlap) / max(1, len(query_tokens)))


def _git_recency_score(path: Path, root: Path) -> float | None:
    """
    Score based on how recently this file was modified in git.
    Returns None if git is unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-20", "--", str(path)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode != 0:
            return None
        lines = result.stdout.strip().splitlines()
        if not lines:
            return 0.1  # never touched in last 20 commits
        # More recent commits = higher score
        return min(1.0, len(lines) / 10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def rank_files(
    files: list[tuple[Path, str]],
    query: str,
    root: Path,
) -> list[tuple[Path, str, float]]:
    """
    Score and rank a list of (path, content) tuples.

    Returns sorted list of (path, content, score) descending by score.
    """
    scored = [
        (path, content, score_file(path, content, query, root))
        for path, content in files
    ]
    return sorted(scored, key=lambda x: x[2], reverse=True)
