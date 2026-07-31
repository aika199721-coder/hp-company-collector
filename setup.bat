@echo off
setlocal
rem setupfix8-v1: default to a visible completion prompt; automation may opt out.
chcp 65001 >nul
cd /d "%~dp0"
echo setup を実行しています...
set "PAUSE_ARG=-PauseOnExit"
if /i "%~1"=="--no-pause" set "PAUSE_ARG="
if /i "%HPCC_NO_PAUSE%"=="1" set "PAUSE_ARG="
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\setup.ps1" %PAUSE_ARG%
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" (echo 正常に完了しました。) else (echo 失敗しました。終了コード: %EXIT_CODE%)
exit /b %EXIT_CODE%
