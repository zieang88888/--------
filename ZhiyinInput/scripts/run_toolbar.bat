@echo off
chcp 65001 >nul
REM 启动知音悬浮工具栏 (Python MVP)
REM 用法：双击本文件
setlocal
set SCRIPT=%~dp0..\tools\ZhiyinToolbar\zhiyin_toolbar.py

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 Python，请安装 Python 3.10+ 并加入 PATH
  pause
  exit /b 1
)

start "知音工具栏" pythonw "%SCRIPT%"
echo 知音悬浮工具栏已在后台启动（Ctrl+Alt+L 显示/隐藏）
exit /b 0
