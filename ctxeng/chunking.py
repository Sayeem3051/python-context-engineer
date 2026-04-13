"""Chunking utilities for Retrieval-Augmented Generation (RAG)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    path: Path
    start_line: int  # 1-indexed
    end_line: int    # inclusive, 1-indexed
    text: str

    def id(self) -> str:
        return f"{self.path.as_posix()}:{self.start_line}-{self.end_line}"


def chunk_text(
    path: Path,
    text: str,
    *,
    max_lines: int = 120,
    overlap: int = 20,
) -> list[Chunk]:
    """
    Split file content into overlapping line chunks.

    This is a robust default that works for any language. AST-aware chunking
    for Python will be layered on later.
    """
    if max_lines <= 0:
        raise ValueError("max_lines must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")

    lines = text.splitlines()
    if not lines:
        return []

    chunks: list[Chunk] = []
    i = 0
    n = len(lines)
    while i < n:
        j = min(n, i + max_lines)
        chunk_lines = lines[i:j]
        start_line = i + 1
        end_line = j
        chunks.append(Chunk(path=path, start_line=start_line, end_line=end_line, text="\n".join(chunk_lines)))
        if j >= n:
            break
        i = max(0, j - overlap)

    return chunks

