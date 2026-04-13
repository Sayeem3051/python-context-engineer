"""Few-shot examples library loader."""

from __future__ import annotations

from pathlib import Path


def load_fewshot_examples(root: Path, *, examples_dir: str | Path = ".ctxeng/examples", max_files: int = 5) -> list[str]:
    """
    Load a small set of markdown/text few-shot examples to inject into context.

    Files are loaded in name-sorted order for determinism.
    """
    base = (root / examples_dir) if not Path(examples_dir).is_absolute() else Path(examples_dir)
    if not base.is_dir():
        return []
    paths = sorted([p for p in base.iterdir() if p.is_file() and p.suffix.lower() in {".md", ".txt"}])[:max_files]
    out: list[str] = []
    for p in paths:
        try:
            out.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return out

