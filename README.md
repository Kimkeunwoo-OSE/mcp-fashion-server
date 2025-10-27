⚠️ **기존 작업물 전부 삭제됨** — 이 저장소는 `fix/rewrite-windows-toast` 브랜치에서 v5 Trader 프로젝트를 완전히 새로 구성했습니다. 이전 작업물은 `docs/GIT_RESET.md`를 참고해 동일 절차로 초기화되었습니다.

# v5 Trader (Rewrite, Windows Toast Edition)

한국 주식 초단기 v5 전략을 위한 로컬 설치형 도우미 애플리케이션입니다. 자동매매는 지원하지 않으며, 추천/모의주문/실거래 보조 및 급등 알림(Windows Toast)을 제공합니다.

## 프로젝트 개요
- **타깃 OS**: Windows 10/11
- **Python 버전**: 3.10 / 3.11
- **패키지 매니저**: `pip` + `venv`
- **아키텍처**: Ports & Adapters (Hexagonal)
- **런 모드**: `mock` → `paper` → `live` 순의 점진적 확장

## 빠른 시작
```powershell
REM 1) 가상환경 생성 및 활성화 (Windows PowerShell)
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1

REM 2) 의존성 설치
pip install -r requirements.txt

REM 3) 테스트 실행
pytest -q

REM 4) CLI 실행(M0)
python -m app

REM 5) Streamlit UI 실행(M1)
python -m app --ui
```

### 설정 파일
`config/settings.example.toml`을 복사하여 `config/settings.toml`을 생성한 뒤 값을 수정하세요. 누락 시 안전한 기본값이 사용되며, 경고 로그가 출력됩니다.

### 주요 기능(M0)
- 동기 I/O 기반의 모의 시세/브로커 어댑터
- Windows Toast(Win10Toast) 알림 어댑터
- SQLite3 기반 로컬 영속화
- 전략 점수화 후 상위 3개 후보 출력

### Streamlit UI(M1)
`python -m app --ui` 명령으로 실행하며 다음 기능을 제공합니다.
- 현재 설정 상태 패널 및 환경 정보
- 상위 3개 추천 카드 및 미니 차트
- “알림 테스트” 버튼으로 Windows Toast 테스트
- 다크 테마 및 설정 기반 새로 고침 주기 반영

## 테스트
프로젝트는 `pytest` 기반의 테스트 스위트를 포함합니다. 전체 테스트는 다음 명령으로 실행합니다.

```bash
pytest -q
```

## 실행 · 검증 시나리오
```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt

python -m app
python -c "from adapters.notifier_windows import NotifierWindows; print(NotifierWindows().send('hello'))"
```

- CLI는 “추천 종목 3개”를 출력하며 예외 없이 종료해야 합니다.
- 토스트 단독 호출은 Windows 환경에서 `True`를 반환하며 실제 알림을 표시합니다. 비Windows 환경에서는 `False`를 반환하지만 예외는 발생하지 않습니다.

## Git 리셋 절차
이 저장소는 기존 작업물을 완전히 삭제한 뒤 오프한 브랜치에서 재구성되었습니다. 동일 절차를 진행하려면 [`docs/GIT_RESET.md`](docs/GIT_RESET.md)를 참고하거나 `scripts/reset_repo.ps1` / `scripts/reset_repo.sh` 스크립트를 사용하세요.

## 변경 로그 & 버전
- [`CHANGELOG.md`](CHANGELOG.md)
- [`VERSION`](VERSION)

## Troubleshooting
- **WNDPROC return value cannot be converted to LRESULT / TypeError: WPARAM … NoneType**
  - 토스트 호출 시 `threaded=False`로 고정되었으며, `pywin32>=306`이 설치되어 있는지 확인하세요.
  - Windows 알림 센터가 켜져 있는지, “집중 지원(방해 금지)” 모드가 꺼져 있는지 확인하세요.
  - 원격 데스크톱/가상화 환경에서는 알림이 제한될 수 있습니다.
- **PowerShell BurntToast 폴백 사용**
  - `Install-Module -Name BurntToast -Force -Scope CurrentUser`
  - 조직 정책/권한에 따라 설치가 제한될 수 있습니다.

## 라이선스
프로젝트는 작성된 코드에 한해 MIT 라이선스를 가정합니다. (필요시 업데이트)
