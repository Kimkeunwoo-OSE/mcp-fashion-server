# mcp-fashion-server

로컬에서 실행되는 **v5 Trader** 애플리케이션 코드와 문서를 포함한 저장소입니다. FastAPI 백엔드와 Streamlit 프런트엔드를 이용해 KIS OpenAPI 기반의 "v5 Next-Day Surge Probability Strategy"를 수행하며, README와 실행 스크립트를 통해 바로 동작시킬 수 있습니다.

## Prerequisites

- **Python 3.10 또는 3.11**이 필요합니다. Python 3.12 이상은 아직 권장하지 않으며, 3.9 이하 버전은 지원하지 않습니다.
- Windows에서 설치 시 *Add Python to PATH* 옵션을 반드시 체크해 주세요.

## Quick Start

1. `setup_and_run_mock.bat`을 더블 클릭하여 모의(Mock) 모드로 앱을 실행합니다.
2. `run_paper_mode.bat`으로 페이퍼 모드를 체험합니다.
3. `.env`에 KIS 키를 입력한 뒤 `run_live_mode.bat`으로 실거래 모드(주의 필요)를 실행합니다.
4. `build_exe.bat`을 사용해 단일 실행 파일(EXE)을 생성할 수 있습니다.
5. `git_push.bat`으로 변경 사항을 커밋하고 원격 저장소로 푸시합니다.

## Troubleshooting

- `ModuleNotFoundError: v5_trader` 오류가 발생하면 저장소 루트에서 실행하고 있는지 확인하고, `__init__.py` 파일 존재 여부 및 Python 3.10 이상 가상환경을 사용 중인지 확인하세요.
- `ModuleNotFoundError: sqlalchemy`가 발생하면 가상환경이 활성화된 상태에서 `pip install -r requirements.txt`를 다시 실행하거나 `rebuild_env_and_run.bat`을 이용해 가상환경을 재구성하세요.
- Streamlit 실행 시 Python38 경로가 노출된다면 시스템 파이썬이 사용 중입니다. 배치 파일이 `%~dp0\.venv\Scripts\python.exe -m streamlit`을 호출하도록 최신 버전을 사용하세요.
- PowerShell에서 캐럿(`^`) 관련 파이프 오류가 보인다면, `-NoProfile` 및 파이프 앞 캐럿이 제거된 최신 배치 파일을 사용하고 있는지 확인하세요.
