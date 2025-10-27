# Changelog

All notable changes to **v5 Trader** will be documented in this file.

## [0.1.1] - 2024-05-14
### Added
- `rebuild_env_and_run.bat` helper to recreate a Python 3.10+ virtual environment and launch Streamlit in mock mode.
- SQLAlchemy core, utilities, and Alembic dependencies to the installation requirements.

### Changed
- Batch launchers now enforce Python 3.10+ by printing the interpreter version and exiting on lower versions.
- Streamlit is always executed through the project virtual environment with entry file auto-detection across layouts.
- Documentation now clarifies prerequisites, quick-start flow, and troubleshooting for missing dependencies or incorrect Python usage.

### Fixed
- Database module imports and session factory creation so SQLAlchemy initializes reliably under the enforced environment.
- Telegram alert dispatch to await python-telegram-bot v20+ send operations without coroutine warnings.
- Logistic regression training to align feature and label indices prior to fitting, avoiding sample-length mismatches.

## [0.1.0] - 2024-05-13
- Initial project scaffolding with Streamlit UI, FastAPI backend, and mock data pipeline.
- Implemented v5 Next-Day Surge Probability strategy prototype.
- Added alert manager with Telegram and desktop notification support.
- Included plugins for AI sell advisor, news analyzer, and statistics dashboard.
- Added updater script to check GitHub releases for updates.
