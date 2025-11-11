⚠️ **기존 작업물 전부 삭제됨** — 이 저장소는 `fix/rewrite-windows-toast` 브랜치에서 v5 Trader 프로젝트를 완전히 재구성했습니다. 초기화 절차는 [`docs/GIT_RESET.md`](docs/GIT_RESET.md)를 참고하세요.

# v5 Trader — FastAPI + Tauri Rewrite

한국 주식 초단기 v5 전략을 위한 로컬 전용 데스크톱 애플리케이션입니다. 핵심 전략/리스크 엔진은 Python으로 유지하되, UI는 **Tauri + React**(데스크톱)로 전환했고, 백엔드는 **FastAPI**로 분리했습니다. 자동매매는 지원하지 않으며 모든 주문은 사용자의 명시적 승인을 거칩니다.

- **운영체제**: Windows 10/11 (권장)
- **백엔드**: Python 3.11, FastAPI, uvicorn
- **프론트엔드**: React + Vite + Tauri 2 (Rust toolchain 필요)
- **아키텍처**: Ports & Adapters (core/ports/adapters 재사용)
- **배포**: `npm run tauri build`로 exe/msi 생성 (아이콘은 Base64 → 빌드시 복원)

---

## 폴더 구성
```
v5_rewrite/
├─ api/                # FastAPI 진입점 및 Pydantic 스키마
├─ app_desktop/        # Tauri + React 프론트엔드 (Vite 기반)
│  ├─ src/             # React 컴포넌트 및 페이지
│  └─ src-tauri/       # Tauri 설정, Rust 엔트리
├─ core/, ports/, adapters/, config/, tests/  # 기존 전략/어댑터 계층
├─ scripts/            # dev/bundle 유틸(아이콘 복원 등)
└─ .vscode/            # VS Code 설정/태스크/런치 구성
```

---

## 필수 요구 사항
- Python 3.11
- Node.js 18 이상 + npm
- Rust stable toolchain (Tauri 빌드용)
- Windows 환경에서 알림을 사용하려면 `pywin32`, `winotify`, Windows 알림 센터 활성화

---

## 빠른 시작
```powershell
# 1) 가상환경 + 백엔드 의존성
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# 2) 프론트엔드 의존성
cd app_desktop
npm install
cd ..

# 3) 개발 모드 실행 (FastAPI + Tauri 동시)
# PowerShell: 백엔드 uvicorn + Tauri dev 프로세스를 병렬로 기동
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

# 혹은 VS Code: Ctrl+Shift+B → dev:desktop(all)
# 혹은 F5 → “Dev: Desktop (API + Tauri)” 복합 디버그 실행
```
실행 후 `http://127.0.0.1:5173`에서 FastAPI가 동작하며, Tauri dev 창(또는 웹뷰)이 자동으로 뜹니다.

---

## 주요 기능
### 백엔드 (FastAPI)
- `GET /api/health` – 헬스체크
- `GET /api/settings` – watch/trade/chart/risk 기본값 노출
- `GET /api/holdings` – 보유 종목 + 손익% + exit 신호 요약 (이름 캐시는 `hts_kor_isnm` + SQLite)
- `GET /api/reco?top=N` – v5 전략 Top N 추천 (심볼/이름/점수/사유)
- `GET /api/candles` – 시세 캔들 (mock/KIS 선택)
- `GET /api/name` – 종목명 조회 (캐시 사용)
- `POST /api/order` – 승인 플래그가 설정된 주문만 브로커 어댑터로 위임

### 프론트엔드 (Tauri + React)
- **거래 탭**: 종목 검색, 매수/매도 토글, 수량/금액 전환, 지정가 ±tick, 퀵 % 버튼, 승인 체크, 결과 토스트
- **차트 탭**: 캔들+거래량, SMA20/60, RSI14 토글, 기간 선택 (설정 기반)
- **추천 탭**: Top N 카드 (이름/코드/점수/미니 스파크라인) + “거래로 이동” 버튼
- **보유/알림 탭**: 테이블 선택 → 슬라이딩 상세 패널(캔들, 권고 매도, 매도 폼). 자동매매 금지 정책을 다시 확인
- **알림**: Tauri Notification 플러그인을 사용해 리스크 신호/주문 결과를 데스크톱 노티로 안내 (Windows Toast 병행 가능)

---

## 테스트
```bash
pytest -q
```
모든 핵심 로직(core/strategy_v5, risk, adapters, wiring)이 FastAPI 이전과 동일하게 커버됩니다.

---

## 주문 & KIS 연동 주의
1. `config/kis.keys.toml.example`를 복사해 `config/kis.keys.toml` 작성 (Git에 커밋 금지)
2. `[market]`, `[broker]` 섹션을 `"kis"`로 설정하면 FastAPI가 KIS 어댑터를 로딩합니다
3. `appkey/appsecret`만 입력해도 실행 시 자동으로 OAuth 토큰을 발급(`Bearer ...`, `expires_at` 캐시)
4. `POST /api/order`는 `approve=true`인 경우에만 브로커로 전달하며, 실전 모드에서는 일중 손실 제한/수량/승인 여부를 다시 검사합니다
5. 모든 결과는 SQLite `trades`/`logs` 테이블에 기록되며 중복 알림은 하루 1회로 제한됩니다

---

## 빌드 & 배포
### 데스크톱 번들 (Tauri)
```powershell
# 아이콘(Base64) → ico 복원 후 빌드
powershell -ExecutionPolicy Bypass -File scripts\restore_icon.ps1
npm run tauri build        # (또는 루트에서 build_exe.ps1 실행)
```
- 산출물: `app_desktop/src-tauri/target/release/` 내부의 `.exe` / `.msi`
- `build_exe.ps1`는 `.venv` 확인 → 백엔드 의존성 설치 → 아이콘 복원 → `npm run tauri build`

### GitHub Actions (선택)
`.github/workflows/release.yml` 워크플로가 태그 `v*.*.*` 푸시에 자동으로 EXE를 빌드해 릴리스에 업로드합니다.

---

## 개발 편의 도구
- `scripts/dev.ps1` : FastAPI 서버 + Tauri dev 프로세스를 동시에 기동
- `.vscode/tasks.json` : venv 생성, 의존성 설치, 프론트 빌드/테스트를 한 번에 실행
- `.vscode/launch.json` : FastAPI 디버거와 Tauri dev를 복합 실행
- `run.bat` : Windows에서 PowerShell 스크립트를 호출해 dev 환경 준비

---

## Windows 알림
- 백엔드는 기존 `NotifierWindows` 어댑터( `winotify` → PowerShell BurntToast → `win10toast(threaded=False)` 순 )를 유지합니다.
- Tauri 프론트에서는 `tauri-plugin-notification`을 통해 알림을 발행하며, 권한이 없으면 첫 실행 시 요청합니다.
- `V5_DISABLE_WIN10TOAST=1` 환경변수를 설정하면 백엔드에서 `win10toast`가 비활성화됩니다.

---

## Troubleshooting
| 이슈 | 해결 방법 |
| --- | --- |
| FastAPI가 시작되지 않음 | `pip install -r requirements.txt`로 백엔드 의존성을 설치하고 `.venv` Python 경로를 VS Code 설정에서 확인하세요. |
| 프론트 빌드 실패 | Node 18 이상인지 확인 후 `app_desktop`에서 `npm install` 다시 실행. Rust toolchain이 없다면 `rustup-init` 설치 필요. |
| 알림 미표시 | Windows 알림 센터 ON / 집중 모드 OFF인지 확인. 원격 데스크톱에서는 제한될 수 있습니다. |
| KIS 401/500 오류 | 키 파일 경로/권한 확인 후 FastAPI 로그를 참조하세요. 토큰은 자동 재발급되며 실패 시 경고가 출력됩니다. |

---

## 버전 & 변경 기록
- [`CHANGELOG.md`](CHANGELOG.md)
- [`VERSION`](VERSION)

기여/문의는 PR 또는 이슈로 남겨주세요. v5 Trader의 목표는 “자동매매 금지 + 사용자 승인형 보조” 원칙을 지키면서 데스크톱 경험을 현대화하는 것입니다.
