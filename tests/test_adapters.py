from __future__ import annotations

import sys
import types

import pytest

from adapters.broker_kis import BrokerKIS
from adapters.broker_mock import MockBroker
from adapters.market_kis import MarketKIS
from adapters.market_mock import MarketMock
from adapters.notifier_windows import NotifierWindows
from adapters.storage_sqlite import SQLiteStorage
from config.schema import AppSettings
from core.symbols import get_name, load_krx_cache


@pytest.fixture(autouse=True)
def cleanup_toast_modules():
    try:
        yield
    finally:
        for name in ("win10toast", "winotify"):
            sys.modules.pop(name, None)


def test_notifier_windows_success_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    class DummyToast:
        called: dict[str, object] = {}

        def show_toast(self, **kwargs):
            DummyToast.called = kwargs
            return True

    module = types.ModuleType("win10toast")
    module.ToastNotifier = lambda: DummyToast()
    sys.modules["win10toast"] = module
    sys.modules["winotify"] = types.ModuleType("winotify")

    notifier = NotifierWindows(enable_ps_fallback=False)
    assert notifier.send("hello") is True
    assert DummyToast.called.get("threaded") is False
    assert isinstance(DummyToast.called.get("msg"), str)


def test_notifier_windows_false_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux", raising=False)
    notifier = NotifierWindows(enable_ps_fallback=False)
    assert notifier.send("hello") is False


def test_notifier_windows_fallback_without_crash(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    class DummyToast:
        def show_toast(self, **kwargs):
            raise RuntimeError("boom")

    module_toast = types.ModuleType("win10toast")
    module_toast.ToastNotifier = lambda: DummyToast()
    sys.modules["win10toast"] = module_toast

    class DummyNotification:
        def __init__(self, app_id: str, title: str, msg: str) -> None:
            self.app_id = app_id
            self.title = title
            self.msg = msg

        def show(self) -> None:
            raise RuntimeError("fail")

    module_notify = types.ModuleType("winotify")
    module_notify.Notification = DummyNotification  # type: ignore[attr-defined]
    sys.modules["winotify"] = module_notify

    notifier = NotifierWindows(enable_ps_fallback=False)
    result = notifier.send("fallback test")
    assert result is False


def test_notifier_windows_long_message(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    class DummyToast:
        def show_toast(self, **kwargs):
            return True

    module = types.ModuleType("win10toast")
    module.ToastNotifier = lambda: DummyToast()
    sys.modules["win10toast"] = module

    notifier = NotifierWindows(enable_ps_fallback=False)
    result = notifier.send("x" * 500)
    assert isinstance(result, bool)


def test_market_mock_deterministic():
    market = MarketMock(seed=123)
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


def test_symbol_name_resolver(tmp_path):
    assert get_name("005930.KS") == "삼성전자"
    assert get_name("UNKNOWN") == "UNKNOWN"

    csv_path = tmp_path / "krx.csv"
    csv_path.write_text("symbol,name\n123456.KS,테스트기업\n", encoding="utf-8")
    load_krx_cache(csv_path)
    assert get_name("123456.KS") == "테스트기업"
    # reset cache to default (missing file clears overrides)
    load_krx_cache(tmp_path / "missing.csv")


def test_market_kis_without_keys(tmp_path):
    settings = AppSettings.model_validate(
        {
            "market": {"provider": "kis"},
            "kis": {"keys_path": str(tmp_path / "kis.keys.toml")},
        }
    )
    market = MarketKIS(settings)
    candles = list(market.get_candles("005930.KS"))
    assert candles == []


def test_broker_kis_requires_confirmation(tmp_path):
    storage = SQLiteStorage(tmp_path / "kis.db")
    broker = BrokerKIS(storage=storage, keys_path=tmp_path / "kis.keys.toml")
    assert broker.place_order("005930.KS", "buy", 1, price=100.0) is False
