@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem setupfix11.2.2.2-v1: canonical validate launcher.
chcp 65001 >nul
cd /d "%~dp0"
set "PAUSE_ARG=-PauseOnExit"
if /i "%~1"=="--no-pause" set "PAUSE_ARG="
if /i "%HPCC_NO_PAUSE%"=="1" set "PAUSE_ARG="
echo validate を実行しています...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\validate.ps1" %PAUSE_ARG%
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" (echo validate は正常に完了しました。) else (echo validate に失敗しました。終了コード: %EXIT_CODE%)
exit /b %EXIT_CODE%
