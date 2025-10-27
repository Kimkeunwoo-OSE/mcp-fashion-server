from __future__ import annotations

import sys
import types

from adapters.broker_mock import MockBroker
from adapters.market_mock import MockMarketData
from adapters.notifier_windows import WindowsToastNotifier
from adapters.storage_sqlite import SQLiteStorage


def test_notifier_windows_non_windows(monkeypatch):
    monkeypatch.setattr("adapters.notifier_windows.sys.platform", "linux", raising=False)
    notifier = WindowsToastNotifier()
    assert notifier.send("test message") is False


def test_notifier_windows_on_windows(monkeypatch):
    dummy = types.SimpleNamespace(calls=0)

    class DummyToast:
        def show_toast(self, *args, **kwargs):
            dummy.calls += 1
            return True

    monkeypatch.setitem(sys.modules, "win10toast", types.SimpleNamespace(ToastNotifier=DummyToast))
    monkeypatch.setattr("adapters.notifier_windows.sys.platform", "win32", raising=False)

    notifier = WindowsToastNotifier()
    assert notifier.send("hello") is True
    assert dummy.calls == 1


def test_market_mock_deterministic():
    market = MockMarketData(seed=123)
    candles_a = list(market.get_candles("AAA", limit=5))
    candles_b = list(market.get_candles("AAA", limit=5))
    assert candles_a[0].close == candles_b[0].close
    assert len(market.get_themes()) >= 3


def test_broker_and_storage(tmp_path):
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path)
    broker = MockBroker(storage)

    assert broker.place_order("AAA", "buy", 10, price=100.0) is True
    assert broker.place_order("AAA", "sell", 5, price=110.0) is True

    positions = broker.get_positions()
    assert positions[0].symbol == "AAA"
    assert positions[0].qty == 5

    order_id = next(iter(broker.orders))
    assert broker.amend(order_id, price=120.0) is True
    assert broker.cancel(order_id) is True

    storage.log_event("INFO", "test")
