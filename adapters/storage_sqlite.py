from __future__ import annotations

import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import List

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
                    last_price REAL DEFAULT 0,
                    pnl_pct REAL DEFAULT 0,
                    trail_stop REAL DEFAULT 0,
                    hard_stop REAL DEFAULT 0,
                    take_profit_price REAL DEFAULT 0,
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
        self._migrate_positions()

    def _migrate_positions(self) -> None:
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(positions)")}
        required = {
            "last_price": "ALTER TABLE positions ADD COLUMN last_price REAL DEFAULT 0",
            "pnl_pct": "ALTER TABLE positions ADD COLUMN pnl_pct REAL DEFAULT 0",
            "trail_stop": "ALTER TABLE positions ADD COLUMN trail_stop REAL DEFAULT 0",
            "hard_stop": "ALTER TABLE positions ADD COLUMN hard_stop REAL DEFAULT 0",
            "take_profit_price": "ALTER TABLE positions ADD COLUMN take_profit_price REAL DEFAULT 0",
        }
        with self.conn:
            for column, stmt in required.items():
                if column not in columns:
                    try:
                        self.conn.execute(stmt)
                    except sqlite3.DatabaseError as exc:
                        logger.warning("positions 테이블 마이그레이션 실패(%s): %s", column, exc)

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
                    INSERT INTO positions(
                        symbol, qty, avg_price, last_price, pnl_pct,
                        trail_stop, hard_stop, take_profit_price, updated_at
                    )
                    VALUES(
                        :symbol, :qty, :avg_price, :last_price, :pnl_pct,
                        :trail_stop, :hard_stop, :take_profit_price, :updated_at
                    )
                    ON CONFLICT(symbol) DO UPDATE SET
                        qty=excluded.qty,
                        avg_price=excluded.avg_price,
                        last_price=excluded.last_price,
                        pnl_pct=excluded.pnl_pct,
                        trail_stop=excluded.trail_stop,
                        hard_stop=excluded.hard_stop,
                        take_profit_price=excluded.take_profit_price,
                        updated_at=excluded.updated_at
                    """,
                    {
                        "symbol": position.symbol,
                        "qty": position.qty,
                        "avg_price": position.avg_price,
                        "last_price": position.last_price,
                        "pnl_pct": position.pnl_pct,
                        "trail_stop": position.trail_stop,
                        "hard_stop": position.hard_stop,
                        "take_profit_price": position.take_profit_price,
                        "updated_at": ts,
                    },
                )
        except sqlite3.DatabaseError as exc:
            logger.warning("포지션 업데이트 실패: %s", exc)

    def get_positions(self) -> List[Position]:
        try:
            cur = self.conn.execute(
                """
                SELECT symbol, qty, avg_price, last_price, pnl_pct,
                       trail_stop, hard_stop, take_profit_price, updated_at
                FROM positions
                """
            )
            rows = cur.fetchall()
            return [
                Position(
                    row["symbol"],
                    row["qty"],
                    row["avg_price"],
                    last_price=row["last_price"],
                    pnl_pct=row["pnl_pct"],
                    trail_stop=row["trail_stop"],
                    hard_stop=row["hard_stop"],
                    take_profit_price=row["take_profit_price"],
                    updated_at=None,
                )
                for row in rows
            ]
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

    def remember_alert(self, symbol: str, signal_type: str, event_date: date) -> bool:
        key = f"{symbol}:{signal_type}:{event_date.isoformat()}"
        try:
            cur = self.conn.execute(
                "SELECT 1 FROM logs WHERE level = ? AND msg = ? LIMIT 1",
                ("alert", key),
            )
            if cur.fetchone():
                return False
            with self.conn:
                self.conn.execute(
                    "INSERT INTO logs(level, msg, ts) VALUES(?, ?, datetime('now'))",
                    ("alert", key),
                )
            return True
        except sqlite3.DatabaseError as exc:
            logger.warning("알림 기록 실패: %s", exc)
            return False

    def close(self) -> None:
        self.conn.close()
