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

REM 5) 스캐너(1회 실행)
python -m app --scan

REM 6) Streamlit UI 실행(M1)
python -m app --ui  # 내부적으로 `python -m streamlit run app/ui_streamlit.py`

REM 7) 네이티브 데스크톱 모드(pywebview)
python -m app --desktop
```

### 설정 파일
`config/settings.example.toml`을 복사하여 `config/settings.toml`을 생성한 뒤 값을 수정하세요. 누락 시 안전한 기본값이 사용되며, 경고 로그가 출력됩니다.

### 감시 / 리스크 / 거래 / 차트 설정
`[watch]` 섹션에서 감시 유니버스(`universe`), Custom 심볼 목록, 추천 개수(`top_n`), 갱신 주기(`refresh_sec`)를 지정할 수 있습니다.
`[risk]` 섹션은 손절/익절/트레일링/최대 보유 종목 수를 제어하며, CLI/Streamlit 모두 동일한 규칙으로 매도 신호를 계산합니다.
`[trade]` 섹션은 주문 폼의 퀵 비율 버튼(`quick_pct`), 지정가 스텝(`tick`), 기본 주문 유형(`default_price_type`), 승인 문구(`confirm_phrase`)를 정의합니다.
`[chart]` 섹션은 캔들 화면에서 사용할 기간 리스트(`periods`)와 보조지표(`indicators`, 예: SMA20/60, RSI14)를 제어합니다.

### 주요 기능(M0)
- 동기 I/O 기반의 모의·KIS 시세/브로커 어댑터
- Windows Toast 알림 어댑터(멀티 폴백, 예외 전파 없음)
- SQLite3 기반 로컬 영속화 + 알림 중복 방지 로그
- KIS `hts_kor_isnm` 기반 종목명 캐시(메모리 + SQLite)로 CLI/UI/토스트에 항상 `이름 (코드)` 형식 표시
- 감시 유니버스(Top200/Top150/Custom)에서 동적 스크리닝 후 상위 `watch.top_n` 후보 출력
- 보유 포지션을 불러와 손절/익절/트레일링 규칙으로 매도 신호 계산 및 토스트 전송

### Streamlit UI(M1)
`python -m app --ui` 명령은 내부적으로 Streamlit CLI(`python -m streamlit run app/ui_streamlit.py`)를 호출하며 다음과 같은 **4개 탭**으로 구성된 데스크톱 스타일 화면을 제공합니다.

1. **거래 탭** – 한국투자증권 앱을 닮은 주문 폼으로 매수/매도 토글, “수량/금액” 전환, 지정가 ±스텝 버튼(`trade.tick`), 퀵 비율 버튼(`trade.quick_pct`), 승인 체크(`trade.confirm_phrase`)를 제공합니다. 승인되지 않은 주문은 전송되지 않으며 모든 결과는 SQLite `logs`/`trades` 테이블과 Windows 토스트로 안내합니다.
2. **차트 탭** – 선택한 심볼을 Plotly 캔들+거래량 2축 그래프로 표시하고, 설정된 기간(`chart.periods`) 슬라이더와 SMA/RSI 토글(`chart.indicators`)로 보조지표를 조합할 수 있습니다.
3. **추천 탭** – v5 스크리너 Top N 카드를 코드·종목명·점수·미니 지표와 함께 보여주며, 각 카드에서 “거래로” / “차트로” 버튼을 통해 해당 탭으로 즉시 이동할 수 있습니다.
4. **보유/알림 탭** – 실보유표(수익률·exit 신호 배지 포함)와 승인형 매도 컨트롤(수량/금액 전환, 지정가 스텝, 퀵 비율 버튼, 3초 쿨다운)을 제공하며, 손절/익절/트레일링 신호는 하루 1회만 토스트로 알립니다.

상단 패널에서는 Mode / Market / Broker / KIS 키 감지 상태, 리스크 임계값, 감시 유니버스 요약을 한눈에 확인할 수 있습니다. 모든 알림은 `NotifierWindows` 어댑터를 통해 전송되며 실패해도 예외가 전파되지 않습니다.

### 데스크톱 모드 (--desktop)

`python -m app --desktop` 또는 `run.bat --desktop`을 실행하면 Streamlit 서버를 백그라운드 서브프로세스로 띄운 뒤 `pywebview`를 이용한 네이티브 창(1200×800, 최소 900×600)이 생성됩니다. 창 상단 메뉴에는 “새로고침”과 “다크 모드 토글” 항목이 포함되어 있으며, 창을 닫으면 Streamlit 프로세스가 자동으로 종료됩니다. `assets/app.ico` 파일이 존재한다면 창 아이콘으로 사용됩니다.
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
3. 키 파일에는 최소한 `appkey`와 `appsecret`만 입력해도 됩니다. 애플리케이션이 최초 실행 시 KIS OAuth API를 호출하여 `access_token`과 `expires_at` 값을 자동으로 발급·저장합니다.
4. 실거래 주문은 **자동매매 금지** 정책에 따라 보유 종목 섹션의 “자동매매 금지에 동의” 체크박스를 활성화해야 전송됩니다. `BrokerKIS.place_order()`는 Live 모드 & 실계좌(`kis.paper=false`)에서만 실행되며, 승인 누락·일중 손실 제한·수량 검증 등에 실패하면 `{"ok": False, "message": ...}` 형태로 거절 사유를 반환합니다.
5. 키 파일이 존재하지 않거나 파싱에 실패하면 KIS 기능이 비활성화되며 Mock 모드와 동일하게 동작하면서 경고만 출력됩니다.
6. 네트워크 오류/권한 문제/토큰 만료 시 주문과 시세가 실패할 수 있습니다. 애플리케이션은 401 응답을 감지하면 토큰을 자동으로 재발급한 뒤 한 번 더 시도합니다. 그래도 실패한다면 로그(`logs` 테이블)와 Streamlit 상태 패널을 확인하세요.
7. 잔고/보유 종목은 KIS 잔고 API를 통해 로드하며, 실패 시 로컬 SQLite 캐시에 저장된 데이터를 사용합니다. 토스트 알림은 하루 한 번만 전송되도록 `logs` 테이블에서 중복을 차단합니다.
8. 종목명은 `inquire-price` 응답의 `hts_kor_isnm` 필드를 SQLite와 메모리에 캐시하여 모든 화면/알림에 `이름 (코드)` 형식으로 표시됩니다.

> `config/kis.keys.toml` 예시 구조
> ```toml
> [auth]
> appkey = ""
> appsecret = ""
> # access_token 은 없어도 됩니다. 실행 시 자동 발급/저장됩니다.
> # 수동으로 입력할 경우 반드시 'Bearer ' 접두어를 포함하세요.
> # access_token = "Bearer your_token"
> # expires_at = 0
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
python -m app --scan
python -m app --ui
python -m app --desktop
python -c "from adapters.notifier_windows import NotifierWindows; print(NotifierWindows().send('hello'))"
```

- CLI는 감시 유니버스 기반으로 추천 N개를 **코드 + 종목명** 형식으로 출력하며 예외 없이 종료해야 합니다.
- `python -m app --scan`은 1회 스캔 후 보유 종목의 매도 신호를 계산해 토스트로 전송합니다. `--loop` 옵션을 함께 사용하면 `watch.refresh_sec` 간격으로 반복 실행합니다.
- `python -m app --ui` 실행 시 Streamlit이 별도 프로세스로 기동되며 브라우저가 자동으로 열리거나 URL이 콘솔에 표시됩니다.
- 토스트 단독 호출은 Windows 환경에서 `True`를 반환하며 실제 알림을 표시합니다. 비Windows 환경에서는 `False`를 반환하지만 예외는 발생하지 않습니다.
- 필요 시 직접 `streamlit run app/ui_streamlit.py` 명령으로도 UI를 실행할 수 있습니다.

## Windows 토스트 알림
- 모든 알림은 `adapters.notifier_windows.NotifierWindows` 단일 어댑터를 통해 전송됩니다.
- 우선 순위는 `winotify` → PowerShell BurntToast → `win10toast(threaded=False)` 입니다. Streamlit 실행 중이거나 `V5_DISABLE_WIN10TOAST=1` 환경 변수가 설정되어 있으면 `win10toast`는 자동 비활성화됩니다.
- `send()`는 어떤 경우에도 예외를 전파하지 않으며 `True` / `False` 반환값으로만 성공 여부를 알립니다.
- 동일한 매도 알림은 `logs` 테이블에 키(`symbol:signal:date`)를 기록해 하루 한 번만 토스트를 전송합니다.
- 알림이 보이지 않을 경우 Windows 알림 센터가 활성화되어 있고 “집중 모드(방해 금지)”가 꺼져 있는지 확인하세요.
- 원격 데스크톱/가상화 환경에서는 알림이 제한될 수 있습니다.

## Git 리셋 절차
이 저장소는 기존 작업물을 완전히 삭제한 뒤 오프한 브랜치에서 재구성되었습니다. 동일 절차를 진행하려면 [`docs/GIT_RESET.md`](docs/GIT_RESET.md)를 참고하거나 `scripts/reset_repo.ps1` / `scripts/reset_repo.sh` 스크립트를 사용하세요.

## 변경 로그 & 버전
- [`CHANGELOG.md`](CHANGELOG.md)
- [`VERSION`](VERSION)

## PyInstaller 단일 실행 파일

Windows에서 단일 실행 파일이 필요하면 PowerShell에서 `build_exe.ps1`을 실행하세요. 스크립트는 `.venv` 환경의 `pyinstaller`를 자동으로 설치하고 `dist/v5_trader.exe`를 생성합니다.

```powershell
./build_exe.ps1
# 또는 특정 파이썬 경로를 지정하려면
./build_exe.ps1 -Python .\.venv\Scripts\python.exe
```

## Troubleshooting
- **WNDPROC return value cannot be converted to LRESULT / TypeError: WPARAM … NoneType**
  - 토스트 호출이 `NotifierWindows` 내부에서 `threaded=False`로 고정되었으며, `pywin32>=306`과 `winotify>=1.1`이 설치되어 있는지 확인하세요.
  - Streamlit 실행 시에는 `win10toast`가 자동 비활성화되며, 필요하면 `V5_DISABLE_WIN10TOAST=1` 환경 변수를 사용해 강제로 끌 수 있습니다.
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
  - 토큰 항목이 비어 있으면 앱이 자동으로 발급·저장합니다. 수동 입력 시에는 반드시 `Bearer ` 접두어와 만료 시간을 포함하세요.
  - 주문 거절/네트워크 오류는 `logs` 테이블과 콘솔 로그에 기록됩니다.

## 라이선스
프로젝트는 작성된 코드에 한해 MIT 라이선스를 가정합니다. (필요시 업데이트)
