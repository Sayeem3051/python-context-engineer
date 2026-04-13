"""Relevance scoring for source files relative to a query."""

from __future__ import annotations

import ast
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from ctxeng.multilang_ast import extract_symbols
from ctxeng.scoring_config import ScoringWeights
from ctxeng.semantic import compute_semantic_scores


def score_file(
    path: Path,
    content: str,
    query: str,
    root: Path,
    *,
    semantic_score: float | None = None,
    weights: ScoringWeights | None = None,
) -> float:
    """
    Score how relevant a file is to the given query (0.0 – 1.0).

    Combines multiple signals:
        - Keyword overlap with query
        - AST symbol extraction (Python)
        - File path proximity / naming
        - Git recency (recently changed files score higher)
        (Import graph expansion runs separately in :class:`~ctxeng.core.ContextEngine`.)
        - Semantic similarity (optional; requires `sentence-transformers`)

    Returns a float in [0, 1].
    """
    w = (weights or ScoringWeights()).normalized_base()
    scores: list[float] = []

    scores.append(_keyword_score(content, query))
    scores.append(_path_score(path, query))

    if path.suffix == ".py":
        scores.append(_ast_score(content, query))
    else:
        lang = path.suffix.lower()
        if lang in {".js", ".jsx"}:
            scores.append(_ast_score_multilang(content, query, language="javascript"))
        elif lang in {".ts", ".tsx"}:
            scores.append(_ast_score_multilang(content, query, language="typescript"))
        elif lang == ".go":
            scores.append(_ast_score_multilang(content, query, language="go"))

    git_score = _git_recency_score(path, root)
    if git_score is not None:
        scores.append(git_score)

    # Weighted average — keyword/path/ast/git.
    weights_list = [w.keyword, w.path, w.ast, w.git]
    while len(weights_list) > len(scores):
        weights_list.pop()

    if semantic_score is not None:
        semantic_w = max(0.0, float((weights or ScoringWeights()).semantic))
        base_total = sum(weights_list) or 1.0
        scaled = [(x / base_total) * (1.0 - semantic_w) for x in weights_list]
        return min(
            1.0,
            sum(s * w for s, w in zip(scores, scaled, strict=False)) + semantic_score * semantic_w,
        )

    total_w = sum(weights_list) or 1.0
    norm = [x / total_w for x in weights_list]
    return min(1.0, sum(s * x for s, x in zip(scores, norm, strict=False)))


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


def _ast_score_multilang(content: str, query: str, *, language: str) -> float:
    """
    Extract symbols via optional tree-sitter and score overlap with query tokens.

    If the optional dependency isn't installed, returns 0.0 so we fall back to
    other signals (keyword/path/git/semantic).
    """
    if not query:
        return 0.3

    sym = extract_symbols(content, language=language).symbols
    if not sym:
        return 0.0

    query_tokens = set(re.findall(r"\b\w{3,}\b", query.lower()))
    overlap = query_tokens & sym
    return min(1.0, len(overlap) / max(1, len(query_tokens)))


@lru_cache(maxsize=4096)
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
    *,
    use_semantic: bool = False,
    semantic_model: str = "all-mpnet-base-v2",
    weights: ScoringWeights | None = None,
) -> list[tuple[Path, str, float]]:
    """
    Score and rank a list of (path, content) tuples.

    Returns sorted list of (path, content, score) descending by score.
    """
    semantic_scores: dict[Path, float] = {}
    if use_semantic and files and query:
        semantic_scores = compute_semantic_scores(files, query, model_name=semantic_model, root=root)

    def _score_one(pc: tuple[Path, str]) -> tuple[Path, str, float]:
        path, content = pc
        sem = semantic_scores.get(path) if use_semantic else None
        return path, content, score_file(path, content, query, root, semantic_score=sem, weights=weights)

    # Parallelize scoring for large repos.
    if len(files) >= 256:
        max_workers = min(32, (os.cpu_count() or 4) + 4)
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            scored = list(ex.map(_score_one, files))
    else:
        scored = [_score_one(pc) for pc in files]
    return sorted(scored, key=lambda x: x[2], reverse=True)
