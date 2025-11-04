from __future__ import annotations

import sys
import types
from datetime import date

import pytest
import requests

from adapters.broker_kis import BrokerKIS
from adapters.broker_mock import MockBroker
from adapters.market_mock import MarketMock
from adapters.notifier_windows import NotifierWindows
from adapters.storage_sqlite import SQLiteStorage
from core.entities import Position
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

    result_buy = broker.place_order("AAA", "BUY", 10, price_type="market")
    assert result_buy["ok"] is True
    result_sell = broker.place_order("AAA", "SELL", 5, price_type="limit", limit_price=110.0)
    assert result_sell["ok"] is True

    positions = broker.get_positions()
    assert positions[0].symbol == "AAA"
    assert positions[0].qty == 5
    assert positions[0].last_price != 0

    assert storage.remember_alert("AAA", "stop", date.today()) is True
    assert storage.remember_alert("AAA", "stop", date.today()) is False

    storage.log_event("INFO", "test")


def test_mock_broker_validation(tmp_path):
    storage = SQLiteStorage(tmp_path / "mock.db")
    broker = MockBroker(storage)

    bad_qty = broker.place_order("AAA", "BUY", 0, price_type="market")
    assert bad_qty["ok"] is False

    bad_price = broker.place_order("AAA", "BUY", 1, price_type="limit", limit_price=None)
    assert bad_price["ok"] is False


def test_kis_place_order_retry_and_limits(monkeypatch, tmp_path):
    db_path = tmp_path / "kis.db"
    storage = SQLiteStorage(db_path)
    keys_path = tmp_path / "kis.keys.toml"
    keys_path.write_text(
        """
[auth]
appkey = "dummy"
appsecret = "dummy"

[account]
accno = "12345678-01"
""",
        encoding="utf-8",
    )

    monkeypatch.setattr("adapters.broker_kis.ensure_token", lambda path, is_vts: "Bearer TEST")

    class DummyResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(str(self.status_code))

    class DummySession:
        def __init__(self) -> None:
            self.calls = 0

        def request(self, method, url, headers=None, json=None, timeout=None):
            self.calls += 1
            if self.calls == 1:
                return DummyResponse(401, {})
            return DummyResponse(200, {"rt_cd": "0", "output": {"ODNO": "A1"}})

        def get(self, url, headers=None, params=None, timeout=None):
            return DummyResponse(200, {"output1": []})

    risk = types.SimpleNamespace(daily_loss_limit_r=-3.0, take_profit_pct=0.18)
    broker = BrokerKIS(
        storage=storage,
        keys_path=keys_path,
        paper=False,
        session=DummySession(),
        risk_config=risk,
        mode="live",
    )

    broker.get_positions = lambda: [
        Position(symbol="005930.KS", qty=10, avg_price=70000, last_price=71000)
    ]

    result = broker.place_order("005930.KS", "SELL", 3, price_type="market")
    assert result["ok"] is True
    assert broker._session.calls == 2  # type: ignore[attr-defined]

    storage.log_event("risk", "daily_loss_exceeded")
    blocked = broker.place_order("005930.KS", "SELL", 1, price_type="market")
    assert blocked["ok"] is False

    broker.get_positions = lambda: [
        Position(symbol="005930.KS", qty=1, avg_price=70000, last_price=71000)
    ]
    too_much = broker.place_order("005930.KS", "SELL", 5, price_type="market")
    assert too_much["ok"] is False


def test_symbol_name_resolver(tmp_path):
    assert get_name("005930.KS") == "삼성전자"
    assert get_name("UNKNOWN") == "UNKNOWN"

    csv_path = tmp_path / "krx.csv"
    csv_path.write_text("symbol,name\n123456.KS,테스트기업\n", encoding="utf-8")
    load_krx_cache(csv_path)
    assert get_name("123456.KS") == "테스트기업"
    load_krx_cache(tmp_path / "missing.csv")
