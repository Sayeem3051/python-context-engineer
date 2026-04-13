"""JSONL tracing for ctxeng context builds (local-first observability)."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe(obj: Any) -> Any:
    """Best-effort JSON serialization for trace payloads."""
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe(v) for v in obj]
    return str(obj)


@dataclass
class TraceConfig:
    enabled: bool = False
    trace_dir: Path | None = None
    trace_id: str | None = None


class TraceWriter:
    """
    Append-only JSONL trace writer.

    Important: do not log raw file contents. Only log metadata and counts.
    """

    def __init__(self, root: Path, config: TraceConfig) -> None:
        self.root = root
        self.config = config
        self.trace_id = config.trace_id or uuid.uuid4().hex
        base_dir = config.trace_dir or (root / ".ctxeng" / "traces")
        self.dir = base_dir
        self.dir.mkdir(parents=True, exist_ok=True)

        ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        pid = os.getpid()
        self.path = self.dir / f"{ts}-{pid}-{self.trace_id}.jsonl"
        self._fp = self.path.open("a", encoding="utf-8")

    def emit(self, event: str, **fields: Any) -> None:
        payload = {"ts_ms": _now_ms(), "event": event, "trace_id": self.trace_id, **fields}
        self._fp.write(json.dumps(_safe(payload), ensure_ascii=False) + "\n")
        self._fp.flush()

    def close(self) -> None:
        try:
            self._fp.close()
        except Exception:
            pass

