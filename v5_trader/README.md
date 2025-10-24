# v5 Trader

**v5 Trader** is a fully local, cost-free AI-assisted stock trading companion implementing the **"v5 Next-Day Surge Probability Strategy"**. The project combines a Streamlit front-end, a FastAPI backend, and modular core services to deliver actionable trading recommendations that respect privacy and regulatory requirements.

## Features

- 🔒 100% local execution with optional mock mode for demonstration without KIS credentials.
- 📈 Implements the proprietary v5 Next-Day Surge Probability Strategy for daily entry suggestions.
- 📊 Plotly and TradingView-powered visualizations with a dark, glassmorphic interface.
- 🤖 AI-assisted sell advisor, news sentiment insights, and statistics dashboard plugins.
- 🛰️ Real-time alerting via Telegram bots and desktop notifications.
- 💾 SQLite-backed storage for quotes, orders, and analytical results.
- 🔄 Updater service checks GitHub releases for new versions (no auto-download).

## Project Structure

```
v5_trader/
├── core/
│   ├── alert_manager/
│   ├── broker_api/
│   ├── data_engine/
│   ├── strategy_v5/
│   └── updater/
├── plugins/
│   ├── ai_sell_advisor/
│   ├── news_analyzer/
│   └── statistics_dashboard/
├── ui/
│   ├── assets/
│   ├── chart_panel/
│   ├── main_window/
│   ├── order_panel/
│   └── theme/
├── config/
│   ├── settings.json
│   ├── theme.json
│   └── user.env
├── CHANGELOG.md
├── ROADMAP.md
├── main.py
├── requirements.txt
└── updater.py
```

## Getting Started

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment**

   - Copy `config/user.env` to `.env.local` and populate with your KIS OpenAPI credentials and Telegram bot configuration.
   - Adjust `config/settings.json` and `config/theme.json` to suit your preferences.

3. **Initialize the database**

   ```bash
   python -m v5_trader.core.data_engine.database --init
   ```

4. **Run the backend**

   ```bash
   uvicorn v5_trader.core.data_engine.api:app --reload
   ```

5. **Launch the Streamlit UI**

   ```bash
   streamlit run v5_trader/main.py
   ```

## REST API Overview

The FastAPI backend exposes endpoints that enable automation or integration with other tools:

- `GET /health` — basic liveness probe.
- `GET /strategy/recommendations` — execute the v5 strategy and return fresh surge predictions.
- `GET /holdings` — list the latest holdings snapshots stored in SQLite.
- `GET /orders` — retrieve the manual order log.
- `POST /orders` — record a new order entry for auditing purposes.
- `GET /recommendations` — fetch the most recent persisted strategy outputs.

## Mock Mode

Set `V5_TRADER_MOCK_MODE=true` in your environment (or via the Settings tab) to run without real KIS connectivity. Mock mode ships with sample historical and live data contained in the `v5_trader/ui/assets/mock_data` directory.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is released under the MIT License.
