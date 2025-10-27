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

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from v5_trader.core.utils.config import Settings, load_settings


Base = declarative_base()

# Default engine/session for typical local usage.
engine = create_engine("sqlite:///v5_trader.db", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class PriceCandle(Base):
    """Daily OHLCV candle."""

    __tablename__ = "price_candles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)


class Holding(Base):
    """Represents a daily snapshot of a portfolio holding."""

    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), index=True, nullable=False)
    quantity = Column(Float, nullable=False)
    average_price = Column(Float, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)


class Order(Base):
    """Records manual orders the user executed with optional notes."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), index=True, nullable=False)
    side = Column(String(8), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    note = Column(String(255))


class Recommendation(Base):
    """Stores the v5 surge probability output for transparency."""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), index=True, nullable=False)
    run_date = Column(Date, index=True, nullable=False)
    surge_probability = Column(Float, nullable=False)
    target_price = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)


class DatabaseManager:
    """Simple façade to the SQLAlchemy engine and sessions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        db_path = Path(settings.database.path)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        if db_path == Path("v5_trader.db"):
            self.engine = engine
            self._session_factory = SessionLocal
        else:
            self.engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
            self._session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        """Return a new session bound to the engine."""

        return self._session_factory()

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
