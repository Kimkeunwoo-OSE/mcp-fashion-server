# Git 전체 리셋 & 오프한 브랜치 초기화 가이드

이 문서는 기존 작업물을 완전히 삭제하고 `fix/rewrite-windows-toast` 브랜치에서 새 프로젝트를 시작하는 절차를 문서화합니다. Windows PowerShell과 POSIX 셸(Bash)을 기준으로 설명합니다.

## 1. 현재 변경사항 확인
```bash
git status -sb
```
필요하다면 변경사항을 백업하거나 원격에 푸시하세요.

## 2. 오프한(Orphan) 브랜치 생성
```bash
git checkout --orphan fix/rewrite-windows-toast
```
- 기존 커밋 히스토리를 참조하지 않는 완전히 새로운 브랜치가 생성됩니다.
- 워킹트리는 이전 파일을 그대로 보유하므로 다음 단계에서 정리합니다.

## 3. `.git`을 제외한 모든 파일 삭제
### 공통 추천 절차 (크로스 플랫폼)
```bash
git rm -r --cached .
git clean -fdx
```
- 인덱스를 초기화하고 추적 중인 파일을 모두 제거합니다.
- 워킹트리에서 추적/비추적 파일을 포함하여 삭제합니다.

### Windows PowerShell에서 수동 삭제 (필요 시)
```powershell
Get-ChildItem -Force | Where-Object { $_.Name -ne ".git" } | Remove-Item -Recurse -Force
```

## 4. 새 프로젝트 스캐폴드 생성
- 폴더/파일 구조를 새로 작성합니다.
- 필요한 의존성과 설정 파일을 준비합니다.

## 5. 최초 커밋 생성
```bash
git add .
git commit -m "feat: bootstrap v5 Trader rewrite (Windows Toast, sync I/O, local-only)"
```

## 6. 원격 브랜치 초기화 (선택)
```bash
git push -u origin fix/rewrite-windows-toast --force
```
원격에 동일 브랜치를 강제 푸시하여 초기화합니다. 협업 중이라면 팀과 사전 조율이 필요합니다.

## 7. 자동화 스크립트
- `scripts/reset_repo.sh`: Bash 환경에서 위 절차를 자동화합니다.
- `scripts/reset_repo.ps1`: Windows PowerShell에서 동일한 작업을 수행합니다.

스크립트를 실행하기 전에 반드시 백업 여부를 확인하세요. 실행 후에는 `.git` 디렉터리를 제외한 모든 작업물이 삭제됩니다.
