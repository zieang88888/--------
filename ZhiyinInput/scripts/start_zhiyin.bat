@echo off
chcp 65001 >nul
setlocal
title 知音输入法

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 Python，请安装 Python 3.10+ 并加入 PATH
  pause
  exit /b 1
)

python "%~dp0start_zhiyin.py" %*
if errorlevel 1 (
  echo.
  echo [错误] 知音输入法启动失败
  pause
  exit /b 1
)

exit /b 0
