@echo off
chcp 65001 >nul
REM ============================================================
REM 知音输入法 · 开发版一键部署到小狼毫
REM 自动识别注册表中配置的小狼毫用户目录，并保留已有设置。
REM ============================================================
setlocal

echo.
echo ==============================================
echo  知音输入法 v0.1  ·  开发版部署
echo ==============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 Python，请安装 Python 3.10+ 并加入 PATH
  pause
  exit /b 1
)

python "%~dp0install_dev.py"
if errorlevel 1 (
  echo.
  echo [错误] 部署失败
  pause
  exit /b 1
)

echo.
echo 部署完成。重新部署结束后可在方案选单中选择「知音九键」。
pause
