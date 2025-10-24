#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m v5_trader.core.data_engine.database --init
streamlit cache clear || true

echo "v5 Trader environment ready. Run 'streamlit run v5_trader/main.py' to start the UI."
