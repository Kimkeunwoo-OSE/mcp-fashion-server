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
python -m app --ui  # 내부적으로 `python -m streamlit run app/ui_streamlit.py`
```

### 설정 파일
`config/settings.example.toml`을 복사하여 `config/settings.toml`을 생성한 뒤 값을 수정하세요. 누락 시 안전한 기본값이 사용되며, 경고 로그가 출력됩니다.

### 주요 기능(M0)
- 동기 I/O 기반의 모의 시세/브로커 어댑터
- Windows Toast(Win10Toast) 알림 어댑터
- SQLite3 기반 로컬 영속화
- 전략 점수화 후 상위 3개 후보 출력

### Streamlit UI(M1)
`python -m app --ui` 명령은 내부적으로 Streamlit CLI(`python -m streamlit run app/ui_streamlit.py`)를 호출하며 다음 기능을 제공합니다.
- Mode / Market / Broker 프로바이더 및 KIS 키 파일 감지 상태 표시
- 상위 3개 추천 카드: 코드 + 종목명 + 점수 + 핵심 지표 + 미니 차트
- “모의 주문(Paper)” 버튼 — KIS 선택 시 “주문 전 사용자 승인” 체크박스를 반드시 활성화해야 주문 요청을 전송합니다.
- “알림 테스트” 버튼은 추천 종목 정보를 포함한 `[v5] 추천: ...` 토스트 포맷으로 전송합니다.
- 포지션 테이블(코드/종목명/수량/평단가) 및 리스크 요약, 새로 고침 주기 안내

### KIS 연결(Paper/Live)
1. `config/kis.keys.toml.example`를 참고하여 **사용자가 직접** `config/kis.keys.toml`을 작성합니다. (Git에 커밋되지 않으며 `.gitignore`로 보호됩니다.)
2. `config/settings.toml`에서 다음 항목을 조정합니다.
   ```toml
   [market]
   provider = "kis"

   [broker]
   provider = "kis"

   [kis]
   keys_path = "config/kis.keys.toml"  # 변경 가능
   paper = true  # 실거래 시 false (주의)
   ```
3. 모의/실거래 주문은 **자동매매 금지** 정책에 따라 UI의 “주문 전 사용자 승인” 체크박스를 활성화해야 `BrokerKIS`가 동작합니다. `require_user_confirm=False` 상태에서는 항상 차단됩니다.
4. 키 파일이 존재하지 않거나 파싱에 실패하면 KIS 기능이 비활성화되며 Mock 모드와 동일하게 동작하면서 경고만 출력됩니다.
5. 네트워크 오류/권한 문제/토큰 만료 시 주문과 시세가 실패할 수 있습니다. 로그(`logs` 테이블)와 Streamlit 상태 패널을 확인하세요.

> `config/kis.keys.toml` 예시 구조
> ```toml
> [auth]
> appkey = ""
> appsecret = ""
> vt = "" # (선택) 모의투자 토큰
>
> [account]
> accno = "" # 계좌번호 (가상/실전)
> ```

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
python -m app --ui
python -c "from adapters.notifier_windows import NotifierWindows; print(NotifierWindows().send('hello'))"
```

- CLI는 “추천 종목 3개”를 **코드 + 종목명** 형식으로 출력하며 예외 없이 종료해야 합니다.
- `python -m app --ui` 실행 시 Streamlit이 별도 프로세스로 기동되며 브라우저가 자동으로 열리거나 URL이 콘솔에 표시됩니다.
- 토스트 단독 호출은 Windows 환경에서 `True`를 반환하며 실제 알림을 표시합니다. 비Windows 환경에서는 `False`를 반환하지만 예외는 발생하지 않습니다.
- 필요 시 직접 `streamlit run app/ui_streamlit.py` 명령으로도 UI를 실행할 수 있습니다.

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
- **Streamlit ScriptRunContext 경고**
  - 이제 UI는 Streamlit CLI 서브프로세스로 실행되므로 해당 경고가 나타나지 않아야 합니다.
  - 여전히 발생한다면 `streamlit run app/ui_streamlit.py`를 직접 실행해 동작을 확인하세요.
- **PowerShell BurntToast 폴백 사용**
  - `Install-Module -Name BurntToast -Force -Scope CurrentUser`
  - 조직 정책/권한에 따라 설치가 제한될 수 있습니다.
- **KIS 연동 실패**
  - `config/kis.keys.toml` 경로/권한을 확인하고, `appkey`, `appsecret`, `accno`가 올바른지 검증하세요.
  - 토큰 만료 시 새로운 토큰을 발급받아 `auth.vt`를 업데이트하십시오.
  - 주문 거절/네트워크 오류는 `logs` 테이블과 콘솔 로그에 기록됩니다.

## 라이선스
프로젝트는 작성된 코드에 한해 MIT 라이선스를 가정합니다. (필요시 업데이트)
