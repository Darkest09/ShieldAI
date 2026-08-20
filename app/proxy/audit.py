"""Append-only SQLite audit log with tamper-evident SHA-256 hash chain (no raw PII spans)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.core.models import ScrubStats


def _migrate(conn: sqlite3.Connection) -> None:
    stmts = [
        "ALTER TABLE audit_events ADD COLUMN semantic_risk TEXT NOT NULL DEFAULT 'low'",
        "ALTER TABLE audit_events ADD COLUMN shadow_mode INTEGER NOT NULL DEFAULT 0",
    ]
    for sql in stmts:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass


class AuditLog:
    def __init__(self, sqlite_path: str) -> None:
        self._path = Path(sqlite_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._connect() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    corr_id TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    semantic_risk TEXT NOT NULL DEFAULT 'low',
                    shadow_mode INTEGER NOT NULL DEFAULT 0,
                    kinds_json TEXT NOT NULL,
                    threats_json TEXT NOT NULL,
                    scrub_entity_count INTEGER NOT NULL,
                    prev_hash TEXT NOT NULL,
                    row_hash TEXT NOT NULL
                );
                """
            )
            c.commit()
            _migrate(c)
            c.commit()

    def append_event(
        self,
        *,
        corr_id: str,
        ts_iso: str,
        risk_level: str,
        semantic_risk: str,
        shadow_mode_applied: bool,
        kinds_counts: dict[str, int],
        threats: list[str],
        stats: ScrubStats,
        extra: dict[str, Any] | None = None,
    ) -> str:
        extra = extra or {}
        event_body = {
            "corr_id": corr_id,
            "risk": risk_level,
            "semantic_risk": semantic_risk,
            "shadow_mode": bool(shadow_mode_applied),
            "kinds": kinds_counts,
            "threats": threats,
            "scrub_entity_count": stats.entity_count,
            "extra_keys": sorted(extra.keys()),
        }
        event_data = json.dumps(event_body, sort_keys=True, separators=(",", ":"))
        chain_material = f"{ts_iso}|{event_data}"

        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT row_hash FROM audit_events ORDER BY id DESC LIMIT 1"
                )
                row = cur.fetchone()
                prev_hash = row[0] if row else "GENESIS"
                row_hash = hashlib.sha256(
                    (chain_material + prev_hash).encode("utf-8")
                ).hexdigest()
                conn.execute(
                    """
                    INSERT INTO audit_events
                    (ts, corr_id, risk, semantic_risk, shadow_mode,
                     kinds_json, threats_json, scrub_entity_count,
                     prev_hash, row_hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        ts_iso,
                        corr_id,
                        risk_level,
                        semantic_risk,
                        1 if shadow_mode_applied else 0,
                        json.dumps(kinds_counts, sort_keys=True),
                        json.dumps(threats, sort_keys=True),
                        stats.entity_count,
                        prev_hash,
                        row_hash,
                    ),
                )
                conn.commit()
        return row_hash

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    SELECT ts, corr_id, risk, semantic_risk, shadow_mode,
                           kinds_json, threats_json, scrub_entity_count, row_hash
                    FROM audit_events
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            (
                ts,
                corr_id,
                risk,
                sem,
                shard,
                kinds_json,
                threats_json,
                scrub_n,
                rh,
            ) = row
            out.append(
                {
                    "time": ts,
                    "correlation_id": corr_id,
                    "risk_level": risk,
                    "semantic_risk": sem,
                    "shadow_mode": bool(shard),
                    "pii_types": json.loads(kinds_json),
                    "scrub_entities": scrub_n,
                    "threats": json.loads(threats_json),
                    "audit_row_hash_suffix": rh[:12],
                }
            )
        return out

    @staticmethod
    def _recompute_row_hash(
        *,
        ts: str,
        corr_id: str,
        risk: str,
        semantic_risk: str,
        shadow_mode: int,
        kinds_json: str,
        threats_json: str,
        scrub_entity_count: int,
        prev_hash: str,
    ) -> str:
        """Reproduce the stored ``row_hash`` from a row's columns.

        Mirrors the serialization in :meth:`append_event` exactly. ``extra`` is
        never persisted, so ``extra_keys`` is reconstructed as an empty list.
        """
        event_body = {
            "corr_id": corr_id,
            "risk": risk,
            "semantic_risk": semantic_risk,
            "shadow_mode": bool(shadow_mode),
            "kinds": json.loads(kinds_json),
            "threats": json.loads(threats_json),
            "scrub_entity_count": scrub_entity_count,
            "extra_keys": [],
        }
        event_data = json.dumps(event_body, sort_keys=True, separators=(",", ":"))
        chain_material = f"{ts}|{event_data}"
        return hashlib.sha256((chain_material + prev_hash).encode("utf-8")).hexdigest()

    def verify_chain(self) -> dict[str, Any]:
        """Walk the full chain and confirm it is unbroken and untampered.

        Returns a summary: whether the chain is ``ok``, how many rows were
        checked, and (if broken) the ``id`` of the first bad row plus why.
        """
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    SELECT id, ts, corr_id, risk, semantic_risk, shadow_mode,
                           kinds_json, threats_json, scrub_entity_count,
                           prev_hash, row_hash
                    FROM audit_events
                    ORDER BY id ASC
                    """
                )
                rows = cur.fetchall()

        expected_prev = "GENESIS"
        for row in rows:
            (
                rid,
                ts,
                corr_id,
                risk,
                sem,
                shadow,
                kinds_json,
                threats_json,
                scrub_n,
                prev_hash,
                row_hash,
            ) = row
            if prev_hash != expected_prev:
                return {
                    "ok": False,
                    "rows_checked": len(rows),
                    "broken_at_id": rid,
                    "reason": "prev_hash does not match previous row_hash (row inserted/removed)",
                }
            recomputed = self._recompute_row_hash(
                ts=ts,
                corr_id=corr_id,
                risk=risk,
                semantic_risk=sem,
                shadow_mode=shadow,
                kinds_json=kinds_json,
                threats_json=threats_json,
                scrub_entity_count=scrub_n,
                prev_hash=prev_hash,
            )
            if recomputed != row_hash:
                return {
                    "ok": False,
                    "rows_checked": len(rows),
                    "broken_at_id": rid,
                    "reason": "row_hash mismatch (row contents were modified)",
                }
            expected_prev = row_hash

        return {
            "ok": True,
            "rows_checked": len(rows),
            "broken_at_id": None,
            "reason": None,
            "head_hash": expected_prev if rows else "GENESIS",
        }

    def export_all(self, max_rows: int = 5000) -> list[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    SELECT id, ts, corr_id, risk, semantic_risk, shadow_mode, kinds_json, threats_json,
                           scrub_entity_count, prev_hash, row_hash
                    FROM audit_events
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (max_rows,),
                )
                rows = cur.fetchall()
        keys = [
            "id",
            "ts",
            "corr_id",
            "risk",
            "semantic_risk",
            "shadow_mode",
            "kinds_json",
            "threats_json",
            "scrub_entity_count",
            "prev_hash",
            "row_hash",
        ]
        return [dict(zip(keys, row)) for row in rows]
