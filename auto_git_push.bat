@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM 自动进入脚本所在目录
cd /d "%~dp0"

echo Current project: %cd%

REM 确认当前目录是 Git 仓库
git rev-parse --is-inside-work-tree > nul 2>&1
if errorlevel 1 (
    echo 当前目录不是 Git 仓库
    exit /b 1
)

REM 检查是否有变更
set HAS_CHANGES=

for /f "delims=" %%i in ('git status --porcelain') do (
    set HAS_CHANGES=1
)

if not defined HAS_CHANGES (
    echo No changes detected at %date% %time%
    exit /b 0
)

echo Changes detected at %date% %time%

REM 添加所有变更
git add .

REM 使用 PowerShell 获取稳定格式的时间
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"`) do (
    set NOW=%%i
)

set COMMIT_MSG=chore: auto sync !NOW!

git commit -m "!COMMIT_MSG!"
if errorlevel 1 (
    echo Commit failed
    exit /b 1
)

REM 先同步远程，避免 push 被拒绝
git pull --rebase origin main
if errorlevel 1 (
    echo Pull rebase failed. Please resolve conflicts manually.
    exit /b 1
)

git push origin main
if errorlevel 1 (
    echo Push failed
    exit /b 1
)

echo Changes committed and pushed to GitHub successfully.