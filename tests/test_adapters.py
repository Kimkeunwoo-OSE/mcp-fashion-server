from __future__ import annotations

import sys
import types
from datetime import date

import pytest

from adapters.broker_mock import MockBroker
from adapters.market_mock import MarketMock
from adapters.notifier_windows import NotifierWindows
from adapters.storage_sqlite import SQLiteStorage
from core.symbols import get_name, load_krx_cache


@pytest.fixture(autouse=True)
def cleanup_toast_modules():
    try:
        yield
    finally:
        for name in ("win10toast", "winotify", "streamlit"):
            sys.modules.pop(name, None)


def test_notifier_windows_prefers_winotify(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    class DummyNotification:
        called = False

        def __init__(self, app_id: str, title: str, msg: str) -> None:
            self.app_id = app_id
            self.title = title
            self.msg = msg

        def show(self) -> None:
            DummyNotification.called = True

    module_notify = types.ModuleType("winotify")
    module_notify.Notification = DummyNotification  # type: ignore[attr-defined]
    sys.modules["winotify"] = module_notify

    notifier = NotifierWindows(enable_ps_fallback=False)
    assert notifier.send("hello") is True
    assert DummyNotification.called is True


def test_notifier_windows_disables_win10toast_under_streamlit(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    sys.modules["streamlit"] = types.ModuleType("streamlit")

    class DummyNotification:
        called = False

        def __init__(self, app_id: str, title: str, msg: str) -> None:
            self.msg = msg

        def show(self) -> None:
            DummyNotification.called = True

    module_notify = types.ModuleType("winotify")
    module_notify.Notification = DummyNotification  # type: ignore[attr-defined]
    sys.modules["winotify"] = module_notify

    class DummyToast:
        called = False

        def show_toast(self, **kwargs):
            DummyToast.called = True
            return True

    module_toast = types.ModuleType("win10toast")
    module_toast.ToastNotifier = lambda: DummyToast()
    sys.modules["win10toast"] = module_toast

    notifier = NotifierWindows(enable_ps_fallback=False)
    assert getattr(notifier, "_use_win10toast", False) is False
    result = notifier.send("hello")
    assert result in (True, False)
    assert DummyToast.called is False


def test_notifier_windows_false_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux", raising=False)
    notifier = NotifierWindows(enable_ps_fallback=False)
    assert notifier.send("hello") is False


def test_notifier_windows_long_message(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    class DummyNotification:
        called = False

        def __init__(self, app_id: str, title: str, msg: str) -> None:
            self.msg = msg

        def show(self) -> None:
            DummyNotification.called = True

    module_notify = types.ModuleType("winotify")
    module_notify.Notification = DummyNotification  # type: ignore[attr-defined]
    sys.modules["winotify"] = module_notify

    notifier = NotifierWindows(enable_ps_fallback=False)
    result = notifier.send("x" * 500)
    assert isinstance(result, bool)
    assert DummyNotification.called is True


def test_market_mock_universe():
    market = MarketMock(seed=123)
    universe = market.get_universe("KOSPI_TOP200")
    assert len(universe) >= 5
    custom = market.get_universe("CUSTOM", custom=["AAA", "BBB"])
    assert custom == ["AAA", "BBB"]


def test_broker_and_storage(tmp_path):
    db_path = tmp_path / "test.db"
    storage = SQLiteStorage(db_path)
    broker = MockBroker(storage)

    assert broker.place_order("AAA", "buy", 10, price=100.0) is True
    assert broker.place_order("AAA", "sell", 5, price=110.0) is True

    positions = broker.get_positions()
    assert positions[0].symbol == "AAA"
    assert positions[0].qty == 5
    assert positions[0].last_price != 0

    order_id = next(iter(broker.orders))
    assert broker.amend(order_id, price=120.0) is True
    assert broker.cancel(order_id) is True

    assert storage.remember_alert("AAA", "stop", date.today()) is True
    assert storage.remember_alert("AAA", "stop", date.today()) is False

    storage.log_event("INFO", "test")


def test_symbol_name_resolver(tmp_path):
    assert get_name("005930.KS") == "삼성전자"
    assert get_name("UNKNOWN") == "UNKNOWN"

    csv_path = tmp_path / "krx.csv"
    csv_path.write_text("symbol,name\n123456.KS,테스트기업\n", encoding="utf-8")
    load_krx_cache(csv_path)
    assert get_name("123456.KS") == "테스트기업"
    load_krx_cache(tmp_path / "missing.csv")
