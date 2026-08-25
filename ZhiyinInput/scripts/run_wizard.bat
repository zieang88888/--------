@echo off
chcp 65001 >nul
REM 启动知音新手引导 (Python MVP)
setlocal
set SCRIPT=%~dp0..\tools\ZhiyinWizard\zhiyin_wizard.py

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 Python，请安装 Python 3.10+ 并加入 PATH
  pause
  exit /b 1
)

python "%SCRIPT%" --force
exit /b 0
