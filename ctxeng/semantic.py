"""Optional semantic similarity scoring using local embeddings."""

from __future__ import annotations

import hashlib
import json
from contextlib import suppress
from pathlib import Path


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cache_dir(root: Path) -> Path:
    return root / ".ctxeng_cache"


def _cache_key(content: str, model_name: str) -> str:
    payload = (model_name + "\n" + content).encode("utf-8", errors="replace")
    return _sha256_hex(payload)


def _cosine(a: list[float], b: list[float]) -> float:
    import math

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def compute_semantic_scores(
    files: list[tuple[Path, str]],
    query: str,
    model_name: str = "all-mpnet-base-v2",
    *,
    root: Path | None = None,
) -> dict[Path, float]:
    """
    Compute semantic similarity scores (0–1) between ``query`` and each file.

    Uses `sentence-transformers` locally when installed. Embeddings are cached in
    ``.ctxeng_cache/`` using a key based on (content hash + model name).

    Args:
        files: List of (relative_path, content).
        query: The user query.
        model_name: Sentence-transformers model name.
        root: Project root for caching (defaults to cwd).

    Returns:
        Mapping of file path to similarity score (0.0–1.0).
    """
    if not query:
        return {p: 0.0 for p, _ in files}

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as e:
        raise ImportError(
            'Semantic scoring requires sentence-transformers. Install with: pip install "ctxeng[semantic]"'
        ) from e

    root = (root or Path(".")).resolve()
    cache = _cache_dir(root)
    cache.mkdir(parents=True, exist_ok=True)

    model = SentenceTransformer(model_name)

    # Query embedding (not cached; cheap and avoids subtle staleness)
    q_vec = model.encode([query], normalize_embeddings=False)[0]
    q_list = [float(x) for x in q_vec]

    scores: dict[Path, float] = {}
    for path, content in files:
        key = _cache_key(content, model_name)
        cache_path = cache / f"{key}.json"
        vec: list[float] | None = None

        if cache_path.is_file():
            try:
                vec = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                vec = None

        if vec is None:
            v = model.encode([content], normalize_embeddings=False)[0]
            vec = [float(x) for x in v]
            with suppress(OSError):
                cache_path.write_text(json.dumps(vec), encoding="utf-8")

        sim = _cosine(q_list, vec)
        # cosine is [-1, 1]; map to [0, 1]
        scores[path] = max(0.0, min(1.0, (sim + 1.0) / 2.0))

    return scores

