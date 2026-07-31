@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem setupfix11.2.2-v1: canonical Windows setup launcher.
chcp 65001 >nul
cd /d "%~dp0"
set "NO_PAUSE=0"
if /i "%~1"=="--no-pause" set "NO_PAUSE=1"
if /i "%HPCC_NO_PAUSE%"=="1" set "NO_PAUSE=1"
echo [hp-company-collector] セットアップを開始します。
echo ログ保存先: "%~dp0logs"

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Unblock-File -LiteralPath '%~dp0scripts\windows\common.ps1','%~dp0scripts\windows\setup.ps1' -ErrorAction SilentlyContinue; $null = [scriptblock]::Create((Get-Content -Raw -LiteralPath '%~dp0scripts\windows\setup.ps1'))" >nul 2>&1
if errorlevel 1 goto PYTHON_FALLBACK

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\setup.ps1" -NonInteractive
set "EXIT_CODE=%ERRORLEVEL%"
goto COMPLETE

:PYTHON_FALLBACK
echo PowerShellスクリプトを読み取れないため、Python fallbackを実行します。
py -3.13 "%~dp0scripts\windows\setup_fallback.py"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="9009" goto COMPLETE
python "%~dp0scripts\windows\setup_fallback.py"
set "EXIT_CODE=%ERRORLEVEL%"

:COMPLETE
if "%EXIT_CODE%"=="0" (
  echo セットアップ完了。次に validate.bat を実行してください。
) else (
  echo セットアップに失敗しました。終了コード: %EXIT_CODE%
  echo エラー概要とstack traceは画面および "%~dp0logs" のsetupログを確認してください。
)
if "%NO_PAUSE%"=="0" (
  echo Press any key to continue . . .
  pause >nul
)
exit /b %EXIT_CODE%
