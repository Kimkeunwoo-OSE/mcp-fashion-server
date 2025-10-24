"""Database utilities for v5 Trader.

This module defines the SQLite schema, helper functions for database access,
and a simple CLI for bootstrapping the local database file. The schema is kept
minimal to focus on price history, order tracking, and holdings snapshots.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from v5_trader.core.utils.config import Settings, load_settings


class Base(DeclarativeBase):
    """Base declarative class."""


class PriceCandle(Base):
    """Daily OHLCV candle."""

    __tablename__ = "price_candles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    date: Mapped[datetime] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)


class Holding(Base):
    """Represents a daily snapshot of a portfolio holding."""

    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    average_price: Mapped[float] = mapped_column(Float)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Order(Base):
    """Records manual orders the user executed with optional notes."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[Optional[str]] = mapped_column(String(255))


class Recommendation(Base):
    """Stores the v5 surge probability output for transparency."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    run_date: Mapped[datetime] = mapped_column(Date, index=True)
    surge_probability: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)


class DatabaseManager:
    """Simple façade to the SQLAlchemy engine and sessions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        db_path = Path(settings.database.path)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        """Return a new session bound to the engine."""

        return Session(self.engine, expire_on_commit=False)

    def upsert_prices(self, candles: Iterable[PriceCandle]) -> None:
        """Persist a batch of price candles, replacing duplicates."""

        with self.session() as session:
            for candle in candles:
                session.merge(candle)
            session.commit()

    def record_order(self, *, symbol: str, side: str, quantity: float, price: float, note: str | None = None) -> Order:
        """Insert a new manual order entry."""

        order = Order(symbol=symbol, side=side, quantity=quantity, price=price, note=note)
        with self.session() as session:
            session.add(order)
            session.commit()
            session.refresh(order)
        return order

    def list_orders(self, limit: int | None = None) -> List[Order]:
        """Return recorded orders sorted by most recent first."""

        with self.session() as session:
            query = session.query(Order).order_by(Order.timestamp.desc())
            if limit is not None:
                query = query.limit(limit)
            return list(query.all())

    def update_holding(self, *, symbol: str, quantity: float, average_price: float) -> Holding:
        """Create or update a holding snapshot."""

        with self.session() as session:
            holding = session.query(Holding).filter_by(symbol=symbol).one_or_none()
            if holding is None:
                holding = Holding(symbol=symbol, quantity=quantity, average_price=average_price)
                session.add(holding)
            else:
                holding.quantity = quantity
                holding.average_price = average_price
                holding.last_updated = datetime.utcnow()
            session.commit()
            session.refresh(holding)
            return holding

    def list_holdings(self) -> List[Holding]:
        """Fetch all holding snapshots ordered alphabetically."""

        with self.session() as session:
            return list(session.query(Holding).order_by(Holding.symbol).all())

    def list_recommendations(self, limit: int = 25) -> List[Recommendation]:
        """Return the most recent stored surge recommendations."""

        with self.session() as session:
            return list(
                session.query(Recommendation)
                .order_by(Recommendation.run_date.desc(), Recommendation.id.desc())
                .limit(limit)
                .all()
            )


def init_database(settings: Optional[Settings] = None) -> None:
    """Ensure the database schema exists."""

    settings = settings or load_settings()
    DatabaseManager(settings)


def _cli() -> None:
    parser = argparse.ArgumentParser(description="v5 Trader database utility")
    parser.add_argument("--init", action="store_true", help="Initialize the database schema")
    args = parser.parse_args()

    if args.init:
        init_database()
        print("Database initialized.")
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
