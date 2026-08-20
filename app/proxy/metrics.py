from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_counts: dict[str, float] = {
    "pii_intercepted": 0,
    "tokens_scrubbed": 0,
    "threats_blocked": 0,
    "relay_ok": 0,
}

# Optional disk persistence so counters survive a restart.
_store_path: Path | None = None


def configure_persistence(path: str | None) -> None:
    """Point metrics at a JSON file and load any prior values."""
    global _store_path
    if not path:
        _store_path = None
        return
    _store_path = Path(path)
    try:
        if _store_path.exists():
            data = json.loads(_store_path.read_text(encoding="utf-8"))
            with _lock:
                for k, v in data.items():
                    _counts[k] = float(v)
    except Exception:  # noqa: BLE001 — never let a bad file block startup
        pass


def _flush_locked() -> None:
    if _store_path is None:
        return
    try:
        _store_path.parent.mkdir(parents=True, exist_ok=True)
        _store_path.write_text(json.dumps(_counts), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def incr(name: str, by: float = 1.0) -> None:
    with _lock:
        _counts[name] = _counts.get(name, 0.0) + by
        _flush_locked()


def snapshot() -> dict[str, Any]:
    with _lock:
        return dict(_counts)
