#!/bin/bash

set -e

# 自动进入脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Current project: $(pwd)"

# 确认当前目录是 Git 仓库
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    echo "当前目录不是 Git 仓库"
    exit 1
fi

# 检查是否有变更
if [[ -z "$(git status --porcelain)" ]]; then
    echo "No changes detected at $(date '+%Y-%m-%d %H:%M:%S')"
    exit 0
fi

echo "Changes detected at $(date '+%Y-%m-%d %H:%M:%S')"

git add .

COMMIT_MSG="chore: auto sync $(date '+%Y-%m-%d %H:%M:%S')"

git commit -m "$COMMIT_MSG"

# 同步远程，避免 push 被拒绝
git pull --rebase origin main

git push origin main

echo "Changes committed and pushed to GitHub successfully."