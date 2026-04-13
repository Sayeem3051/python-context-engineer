"""Chunking utilities for Retrieval-Augmented Generation (RAG)."""

from __future__ import annotations

import ast
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


def chunk_file(
    path: Path,
    text: str,
    *,
    max_lines: int = 120,
    overlap: int = 20,
    context_lines: int = 3,
) -> list[Chunk]:
    """
    Structure-aware chunking:
    - Python: chunk by class/function using AST line spans.
    - Other: fall back to line chunking.

    `context_lines` expands each chunk with surrounding lines for better local context.
    """
    if path.suffix.lower() == ".py":
        chunks = _chunk_python_ast(path, text, max_lines=max_lines, context_lines=context_lines)
        if chunks:
            return chunks
    return chunk_text(path, text, max_lines=max_lines, overlap=overlap, context_lines=context_lines)


def chunk_text(
    path: Path,
    text: str,
    *,
    max_lines: int = 120,
    overlap: int = 20,
    context_lines: int = 0,
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
        start_line = i + 1
        end_line = j

        # Expand with surrounding context
        start0 = max(1, start_line - context_lines)
        end0 = min(n, end_line + context_lines)
        chunk_lines = lines[start0 - 1 : end0]
        start_line = start0
        end_line = end0
        chunks.append(Chunk(path=path, start_line=start_line, end_line=end_line, text="\n".join(chunk_lines)))
        if j >= n:
            break
        i = max(0, j - overlap)

    return chunks


def _chunk_python_ast(
    path: Path,
    text: str,
    *,
    max_lines: int,
    context_lines: int,
) -> list[Chunk]:
    lines = text.splitlines()
    if not lines:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None)
            if isinstance(start, int) and isinstance(end, int) and end >= start:
                spans.append((start, end))

    if not spans:
        return []

    # Dedupe + sort
    spans = sorted(set(spans))

    out: list[Chunk] = []
    n = len(lines)
    for start, end in spans:
        # Expand context window
        s = max(1, start - context_lines)
        e = min(n, end + context_lines)
        if e - s + 1 > max_lines:
            # Too big: fall back to line chunking inside span (no overlap; keep boundaries)
            segment = "\n".join(lines[s - 1 : e])
            for ch in chunk_text(path, segment, max_lines=max_lines, overlap=0, context_lines=0):
                # Rebase line numbers
                out.append(
                    Chunk(
                        path=path,
                        start_line=s + (ch.start_line - 1),
                        end_line=s + (ch.end_line - 1),
                        text=ch.text,
                    )
                )
        else:
            out.append(Chunk(path=path, start_line=s, end_line=e, text="\n".join(lines[s - 1 : e])))

    return out

