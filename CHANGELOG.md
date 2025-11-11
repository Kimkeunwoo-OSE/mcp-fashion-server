# Changelog

## [0.2.0] - 2024-06-01
### Changed
- Streamlit 기반 UI를 Tauri + React 데스크톱 앱으로 전환
- FastAPI 백엔드(`api/`)를 도입해 core/ports/adapters를 재사용
- `api/deps.py`로 의존성 배선 모듈화 (tests는 여기에서 import)
- VS Code 태스크/런치, dev/build PowerShell 스크립트를 추가
- requirements에서 Streamlit/pywebview 제거, FastAPI/uvicorn 추가
### Added
- Tauri 프론트엔드 컴포넌트 (거래/차트/추천/보유 탭)
- `/api/settings`, `/api/name`, `/api/order` 등 REST 엔드포인트 확장
- GitHub Actions 릴리스 워크플로 (태그 푸시 시 Tauri 빌드)

## [0.1.0] - 2024-06-01
### Added
- 초기 v5 Trader 리라이트(M0) 구성
  - Ports & Adapters 구조의 코어/어댑터/포트 모듈
  - Mock 마켓/브로커/SQLite/Windows Toast 어댑터
  - 설정 스키마 및 기본 TOML 예제
  - CLI 엔트리포인트 및 Streamlit UI 스텁
  - Git 전체 리셋 절차 문서 및 자동화 스크립트
- 테스트 스위트(pytest) 작성

### Planned
- Streamlit UI 고도화(M1)
- Paper/Live 모드 확장
