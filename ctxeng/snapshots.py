"""Context snapshotting (versioned, reproducible context builds)."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ctxeng.models import Context


@dataclass(frozen=True)
class SnapshotManifest:
    snapshot_id: str
    created_at: str
    root: str
    model: str
    fmt: str
    query: str
    total_tokens: int
    included_paths: list[str]
    metadata: dict[str, Any]


def snapshot_dir(root: Path) -> Path:
    return root / ".ctxeng" / "snapshots"


def write_snapshot(root: Path, ctx: Context, *, fmt: str, snapshot_id: str | None = None) -> Path:
    root = root.resolve()
    sid = snapshot_id or uuid.uuid4().hex
    out_dir = snapshot_dir(root) / sid
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered = ctx.to_string(fmt)
    (out_dir / "context.txt").write_text(rendered, encoding="utf-8")

    manifest = SnapshotManifest(
        snapshot_id=sid,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        root=str(root),
        model=str(ctx.metadata.get("model", "")),
        fmt=fmt,
        query=ctx.query,
        total_tokens=ctx.total_tokens,
        included_paths=[str(f.path) for f in ctx.files],
        metadata=dict(ctx.metadata),
    )
    (out_dir / "manifest.json").write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    return out_dir


def list_snapshots(root: Path) -> list[Path]:
    base = snapshot_dir(root.resolve())
    if not base.is_dir():
        return []
    return sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True)

