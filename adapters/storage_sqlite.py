from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Iterable, List

from core.entities import Position

logger = logging.getLogger(__name__)


class SQLiteStorage:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if self.path.parent and not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    qty INTEGER,
                    price REAL,
                    ts TEXT
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    qty INTEGER,
                    avg_price REAL,
                    updated_at TEXT
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT,
                    msg TEXT,
                    ts TEXT
                )
                """
            )

    def record_trade(self, trade_id: str, **fields) -> None:
        try:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO trades(id, symbol, side, qty, price, ts)
                    VALUES(:id, :symbol, :side, :qty, :price, :ts)
                    """,
                    {"id": trade_id, **fields},
                )
        except sqlite3.DatabaseError as exc:
            logger.warning("트레이드 기록 실패: %s", exc)

    def upsert_position(self, position: Position, ts: str) -> None:
        try:
            with self.conn:
                self.conn.execute(
                    """
                    INSERT INTO positions(symbol, qty, avg_price, updated_at)
                    VALUES(:symbol, :qty, :avg_price, :updated_at)
                    ON CONFLICT(symbol) DO UPDATE SET
                        qty=excluded.qty,
                        avg_price=excluded.avg_price,
                        updated_at=excluded.updated_at
                    """,
                    {
                        "symbol": position.symbol,
                        "qty": position.qty,
                        "avg_price": position.avg_price,
                        "updated_at": ts,
                    },
                )
        except sqlite3.DatabaseError as exc:
            logger.warning("포지션 업데이트 실패: %s", exc)

    def get_positions(self) -> List[Position]:
        try:
            cur = self.conn.execute("SELECT symbol, qty, avg_price FROM positions")
            rows = cur.fetchall()
            return [Position(row["symbol"], row["qty"], row["avg_price"]) for row in rows]
        except sqlite3.DatabaseError as exc:
            logger.warning("포지션 조회 실패: %s", exc)
            return []

    def log_event(self, level: str, msg: str) -> None:
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO logs(level, msg, ts) VALUES(?, ?, datetime('now'))",
                    (level, msg),
                )
        except sqlite3.DatabaseError as exc:
            logger.warning("로그 기록 실패: %s", exc)

    def close(self) -> None:
        self.conn.close()
