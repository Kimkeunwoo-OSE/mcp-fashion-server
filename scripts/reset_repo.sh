#!/usr/bin/env bash
set -euo pipefail

BRANCH="fix/rewrite-windows-toast"

echo "[reset_repo] Checking out orphan branch: ${BRANCH}" >&2
git checkout --orphan "${BRANCH}"

echo "[reset_repo] Removing all tracked files" >&2
git rm -r --cached . || true
echo "[reset_repo] Cleaning working tree" >&2
git clean -fdx

echo "[reset_repo] Removing residual files (except .git)" >&2
find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +

echo "[reset_repo] Repository reset complete. Create new scaffold before committing."
