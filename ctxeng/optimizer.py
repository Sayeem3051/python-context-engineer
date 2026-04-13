"""Token counting and budget optimization."""

from __future__ import annotations

import re
from pathlib import Path

from ctxeng.models import ContextFile, TokenBudget


def count_tokens(text: str, model: str = "") -> int:
    """
    Estimate token count for a string.

    Uses tiktoken when available (accurate), falls back to a fast
    word-based heuristic (~4 chars/token) that's within ~10% for code.
    """
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding("cl100k_base")
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Fast heuristic: split on whitespace + punctuation boundaries
        return max(1, len(re.findall(r'\S+', text)) * 4 // 3)


def detect_language(path: Path) -> str:
    """Return the language identifier for syntax highlighting."""
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "jsx", ".tsx": "tsx", ".go": "go", ".rs": "rust",
        ".java": "java", ".kt": "kotlin", ".swift": "swift",
        ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
        ".cs": "csharp", ".rb": "ruby", ".php": "php",
        ".sh": "bash", ".bash": "bash", ".zsh": "bash",
        ".sql": "sql", ".html": "html", ".css": "css",
        ".scss": "scss", ".less": "less", ".yaml": "yaml",
        ".yml": "yaml", ".json": "json", ".toml": "toml",
        ".md": "markdown", ".mdx": "mdx", ".rst": "rst",
        ".tf": "hcl", ".dockerfile": "dockerfile",
    }
    name_map = {
        "dockerfile": "dockerfile", "makefile": "makefile",
        "procfile": "bash", ".env": "bash", ".gitignore": "bash",
    }
    name = path.name.lower()
    if name in name_map:
        return name_map[name]
    return ext_map.get(path.suffix.lower(), "")


def optimize_budget(
    files: list[ContextFile],
    budget: TokenBudget,
    query_tokens: int = 0,
    system_tokens: int = 0,
    model: str = "",
) -> tuple[list[ContextFile], list[ContextFile]]:
    """
    Fit as many files as possible within the token budget.

    Files are sorted by relevance_score descending. For files that would
    exceed the budget, we attempt smart truncation before skipping entirely.

    Returns:
        (included, skipped) — two lists of ContextFile.
    """
    available = budget.available - query_tokens - system_tokens
    if available <= 0:
        return [], files

    included: list[ContextFile] = []
    skipped: list[ContextFile] = []

    # Sort highest relevance first
    ranked = sorted(files, key=lambda f: f.relevance_score, reverse=True)

    remaining = available
    for f in ranked:
        tokens = count_tokens(f.content, model)
        f.token_count = tokens

        if tokens <= remaining:
            remaining -= tokens
            included.append(f)
        elif remaining > 200:
            # Try smart truncation: keep head + tail
            f = _smart_truncate(f, remaining, model)
            included.append(f)
            remaining = 0
        else:
            skipped.append(f)

    return included, skipped


def _smart_truncate(f: ContextFile, max_tokens: int, model: str) -> ContextFile:
    """
    Truncate a file to fit within max_tokens, keeping the most valuable parts.

    Strategy:
      - Always keep the first 40% (imports, class defs, docstrings)
      - Fill remaining budget with lines from the end (recent changes tend to be relevant)
    """
    lines = f.content.splitlines()
    head_lines = lines[: max(1, len(lines) * 2 // 5)]
    tail_lines = lines[len(lines) * 3 // 5 :]

    head = "\n".join(head_lines)
    tail = "\n".join(tail_lines)
    separator = "\n\n# ... [ctxeng: truncated for token budget] ...\n\n"

    head_tokens = count_tokens(head, model)
    sep_tokens = count_tokens(separator, model)
    tail_budget = max_tokens - head_tokens - sep_tokens

    # Trim tail from the top if needed (ensure progress even for short tails)
    while tail and count_tokens(tail, model) > tail_budget:
        if len(tail_lines) <= 1:
            tail_lines = []
            tail = ""
            break
        cut = max(1, len(tail_lines) // 4)
        tail_lines = tail_lines[cut:]
        tail = "\n".join(tail_lines)

    truncated_content = head + separator + tail if tail else head + separator
    import copy
    result = copy.copy(f)
    result.content = truncated_content
    result.token_count = count_tokens(truncated_content, model)
    result.is_truncated = True
    return result
