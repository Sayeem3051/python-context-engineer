"""Scoring weights configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScoringWeights:
    keyword: float = 0.4
    path: float = 0.2
    ast: float = 0.25
    git: float = 0.15
    semantic: float = 0.2  # used only when semantic is enabled

    def normalized_base(self) -> ScoringWeights:
        total = self.keyword + self.path + self.ast + self.git
        if total <= 0:
            return self
        return ScoringWeights(
            keyword=self.keyword / total,
            path=self.path / total,
            ast=self.ast / total,
            git=self.git / total,
            semantic=self.semantic,
        )


def load_scoring_config(path: str | Path) -> ScoringWeights:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    return _parse_weights(raw)


def load_default_scoring_config(root: Path) -> ScoringWeights | None:
    p = root / ".ctxeng" / "config.json"
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return _parse_weights(raw)


def _parse_weights(raw: Any) -> ScoringWeights:
    scoring = raw.get("scoring", {}) if isinstance(raw, dict) else {}
    def getf(k: str, default: float) -> float:
        v = scoring.get(k, default)
        try:
            return float(v)
        except Exception:
            return default
    return ScoringWeights(
        keyword=getf("keyword", 0.4),
        path=getf("path", 0.2),
        ast=getf("ast", 0.25),
        git=getf("git", 0.15),
        semantic=getf("semantic", 0.2),
    )

