"""Local-first retrieval for ctxeng (lexical + optional embeddings)."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ctxeng.chunking import Chunk, chunk_text


def _tokens(text: str) -> list[str]:
    # Simple tokenizer; good enough for lexical retrieval fallback.
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)]


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float
    method: str  # "lexical" | "embedding"


def retrieve_chunks_lexical(
    files: list[tuple[Path, str]],
    query: str,
    *,
    max_chunks: int = 20,
    chunk_max_lines: int = 120,
    chunk_overlap: int = 20,
) -> list[RetrievedChunk]:
    """
    Lexical retrieval over chunks using a lightweight BM25-ish score.

    This is dependency-free and acts as a fallback when embeddings aren't available.
    """
    q_toks = _tokens(query)
    if not q_toks:
        return []

    q_counts = Counter(q_toks)

    # Build document frequencies over chunks
    chunks: list[Chunk] = []
    chunk_tf: list[Counter[str]] = []
    df: Counter[str] = Counter()

    for path, content in files:
        for ch in chunk_text(path, content, max_lines=chunk_max_lines, overlap=chunk_overlap):
            toks = _tokens(ch.text)
            if not toks:
                continue
            tf = Counter(toks)
            chunks.append(ch)
            chunk_tf.append(tf)
            df.update(set(tf.keys()))

    if not chunks:
        return []

    N = len(chunks)
    avgdl = sum(sum(tf.values()) for tf in chunk_tf) / max(1, N)

    def idf(term: str) -> float:
        n = df.get(term, 0)
        # smoothed IDF
        return math.log(1.0 + (N - n + 0.5) / (n + 0.5))

    k1 = 1.2
    b = 0.75

    scored: list[RetrievedChunk] = []
    for ch, tf in zip(chunks, chunk_tf, strict=False):
        dl = sum(tf.values())
        s = 0.0
        for term, qf in q_counts.items():
            f = tf.get(term, 0)
            if f == 0:
                continue
            denom = f + k1 * (1 - b + b * (dl / (avgdl or 1.0)))
            s += idf(term) * (f * (k1 + 1) / denom) * (1 + math.log(1 + qf))
        if s > 0:
            scored.append(RetrievedChunk(chunk=ch, score=float(s), method="lexical"))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:max_chunks]


def retrieve_chunks_embeddings(
    files: list[tuple[Path, str]],
    query: str,
    *,
    max_chunks: int = 20,
    chunk_max_lines: int = 120,
    chunk_overlap: int = 20,
    model_name: str = "all-MiniLM-L6-v2",
) -> list[RetrievedChunk]:
    """
    Embedding-based retrieval over chunks.

    Uses sentence-transformers when installed. If unavailable, raises ImportError
    so callers can fall back to lexical retrieval.
    """
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as e:
        raise ImportError(
            'Embedding retrieval requires sentence-transformers. Install with: pip install "ctxeng[semantic]"'
        ) from e

    chunks: list[Chunk] = []
    for path, content in files:
        chunks.extend(chunk_text(path, content, max_lines=chunk_max_lines, overlap=chunk_overlap))
    if not chunks:
        return []

    model = SentenceTransformer(model_name)
    q = model.encode([query], normalize_embeddings=True)
    c = model.encode([ch.text for ch in chunks], normalize_embeddings=True)

    # cosine similarity for normalized vectors = dot product
    scores = (c @ q.T).reshape(-1)
    out: list[RetrievedChunk] = []
    for ch, s in zip(chunks, scores.tolist(), strict=False):
        out.append(RetrievedChunk(chunk=ch, score=float(s), method="embedding"))
    out.sort(key=lambda r: r.score, reverse=True)
    return out[:max_chunks]

