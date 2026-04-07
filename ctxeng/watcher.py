"""Filesystem watcher that rebuilds ctxeng context on changes."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ctxeng.models import Context


@dataclass(frozen=True)
class WatchConfig:
    """Configuration for watching and rebuilding context."""

    debounce_seconds: float = 0.5
    interval_seconds: float = 1.0


class ContextWatcher:
    """
    Watch a project for file changes and rebuild context automatically.

    This is an optional feature that requires the ``watchdog`` dependency:

        pip install "ctxeng[watch]"

    Args:
        query: Query to build context for.
        engine: A configured :class:`~ctxeng.core.ContextEngine` instance.
        output_file: If set, write context output to this file on rebuild.
        callback: If set, called with the freshly built :class:`~ctxeng.models.Context`.
        fmt: Output format passed to ``Context.to_string()`` when writing to file.
        config: Watch timing configuration (debounce + polling interval).
    """

    def __init__(
        self,
        query: str,
        *,
        engine,
        output_file: str | Path | None = None,
        callback: Callable[[Context], None] | None = None,
        fmt: str = "xml",
        config: WatchConfig | None = None,
    ) -> None:
        self.query = query
        self.engine = engine
        self.root = Path(engine.root).resolve()
        self.output_file = Path(output_file) if output_file else None
        self.callback = callback
        self.fmt = fmt
        self.config = config or WatchConfig()

        self._changed: set[Path] = set()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def run(self) -> None:
        """
        Block forever, rebuilding context when files change.

        Gracefully exits on Ctrl+C.
        """
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers.polling import PollingObserver
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "watch mode requires watchdog. Install with: pip install \"ctxeng[watch]\""
            ) from e

        watcher = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event) -> None:  # type: ignore[override]
                # event has .is_directory and .src_path; moved events also have .dest_path
                if getattr(event, "is_directory", False):
                    return
                src = getattr(event, "src_path", None)
                if src:
                    watcher.notify_change(Path(src))
                dest = getattr(event, "dest_path", None)
                if dest:
                    watcher.notify_change(Path(dest))

        obs = PollingObserver(timeout=self.config.interval_seconds)
        obs.schedule(Handler(), str(self.root), recursive=True)
        obs.start()

        try:
            while True:
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        finally:
            obs.stop()
            obs.join(timeout=5)

    def notify_change(self, abs_path: Path) -> None:
        """Record a changed path and schedule a debounced rebuild."""
        rel = self._to_rel(abs_path)
        ts = self._timestamp()
        print(f"[{ts}] File changed: {rel.as_posix()}")
        with self._lock:
            self._changed.add(rel)
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.config.debounce_seconds, self._rebuild)
            self._timer.daemon = True
            self._timer.start()

    def _rebuild(self) -> None:
        changed: list[Path]
        with self._lock:
            changed = sorted(self._changed)
            self._changed.clear()
            self._timer = None

        ts = self._timestamp()
        print(f"[{ts}] Rebuilding context...")
        ctx = self.engine.build(self.query, fmt=self.fmt)

        done_ts = self._timestamp()
        cost = f", ~${ctx.cost_estimate:.3f}" if ctx.cost_estimate is not None else ""
        print(f"[{done_ts}] Done. {len(ctx.files)} files, {ctx.total_tokens:,} tokens{cost}")

        if self.output_file:
            out = self.output_file
            out.write_text(ctx.to_string(self.fmt), encoding="utf-8")
            print(f"[{self._timestamp()}] Written to: {out}")

        if self.callback:
            self.callback(ctx)

        # changed is currently only printed as individual lines on notify; keep for future hooks
        _ = changed

    def _to_rel(self, abs_path: Path) -> Path:
        try:
            return abs_path.resolve().relative_to(self.root)
        except Exception:
            return abs_path

    @staticmethod
    def _timestamp() -> str:
        return time.strftime("%H:%M:%S", time.localtime())

