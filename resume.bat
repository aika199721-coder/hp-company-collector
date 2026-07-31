@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo resume を実行しています...
set "PAUSE_ARG="
echo %cmdcmdline% | findstr /i /c:"%~f0" >nul && set "PAUSE_ARG=-PauseOnExit"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\resume.ps1" %PAUSE_ARG%
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" (echo 正常に完了しました。) else (echo 失敗しました。終了コード: %EXIT_CODE%)
exit /b %EXIT_CODE%
