from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, Iterable

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS: tuple[str, ...] = (
    "005930.KS",  # Samsung Electronics
    "000660.KS",  # SK hynix
    "035420.KS",  # NAVER
    "051910.KS",  # LG Chem
    "068270.KS",  # Celltrion
    "207940.KS",  # Samsung Biologics
    "035720.KS",  # Kakao
    "105560.KS",  # KB Financial Group
    "096770.KQ",  # SK Innovation (KOSDAQ placeholder)
    "066570.KS",  # LG Electronics
    "005380.KS",  # Hyundai Motor
    "000270.KS",  # Kia
    "302440.KS",  # SK Biopharm
    "259960.KS",  # 크래프톤
    "326030.KS",  # SK바이오팜
)

_DEFAULT_SYMBOL_NAMES: Dict[str, str] = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "035420.KS": "네이버",
    "051910.KS": "LG화학",
    "068270.KS": "셀트리온",
    "207940.KS": "삼성바이오로직스",
    "035720.KS": "카카오",
    "105560.KS": "KB금융",
    "096770.KQ": "SK이노베이션",
    "066570.KS": "LG전자",
    "005380.KS": "현대차",
    "000270.KS": "기아",
    "302440.KS": "SK바이오사이언스",
    "259960.KS": "크래프톤",
    "326030.KS": "SK바이오팜",
}

_EXTRA_SYMBOL_NAMES: Dict[str, str] = {}
_CSV_LOADED = False


def load_krx_cache(path: Path | None = None) -> Dict[str, str]:
    """Load optional KRX symbol cache from CSV.

    The CSV is expected to contain at least two columns: symbol, name. Additional
    columns are ignored. Missing files are silently ignored.
    """

    global _EXTRA_SYMBOL_NAMES, _CSV_LOADED
    csv_path = path or Path("data/krx_list.csv")
    _EXTRA_SYMBOL_NAMES = {}
    if csv_path.exists():
        try:
            with csv_path.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                if "symbol" in reader.fieldnames or "code" in reader.fieldnames:
                    symbol_key = "symbol" if "symbol" in reader.fieldnames else "code"
                    name_key = "name" if "name" in reader.fieldnames else reader.fieldnames[1]
                    for row in reader:
                        symbol = (row.get(symbol_key) or "").strip()
                        name = (row.get(name_key) or "").strip()
                        if symbol and name:
                            _EXTRA_SYMBOL_NAMES[symbol] = name
                else:
                    fh.seek(0)
                    reader_plain = csv.reader(fh)
                    for row in reader_plain:
                        if len(row) < 2:
                            continue
                        symbol = row[0].strip()
                        name = row[1].strip()
                        if symbol and name:
                            _EXTRA_SYMBOL_NAMES[symbol] = name
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("KRX 심볼 캐시 로드 실패: %s", exc)
    _CSV_LOADED = True
    return dict(_EXTRA_SYMBOL_NAMES)


def _ensure_cache() -> None:
    if not _CSV_LOADED:
        load_krx_cache()


def get_name(symbol: str) -> str:
    """Return a Korean company name for the given symbol if known."""

    _ensure_cache()
    clean_symbol = symbol.strip()
    return _EXTRA_SYMBOL_NAMES.get(clean_symbol) or _DEFAULT_SYMBOL_NAMES.get(clean_symbol) or clean_symbol


def iter_default_symbols() -> Iterable[str]:
    return DEFAULT_SYMBOLS
