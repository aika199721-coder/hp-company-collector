@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem setupfix11.2.2.1-v1: canonical live validation launcher.
chcp 65001 >nul
cd /d "%~dp0"
set "PAUSE_ARG=-PauseOnExit"
if /i "%~1"=="--no-pause" set "PAUSE_ARG="
if /i "%HPCC_NO_PAUSE%"=="1" set "PAUSE_ARG="
echo live_check を実行しています...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\live_check.ps1" %PAUSE_ARG%
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" (echo live_check は正常に完了しました。) else (echo live_check に失敗しました。終了コード: %EXIT_CODE%)
exit /b %EXIT_CODE%
