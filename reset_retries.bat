@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo 再試行待ちの案件を未処理へ戻します。
set /p "ANSWER=実行しますか？ [Y/N]: "
if /i not "%ANSWER%"=="Y" (
  echo 変更せず終了しました。
  exit /b 0
)
echo reset-retries を実行しています...
set "PAUSE_ARG="
echo %cmdcmdline% | findstr /i /c:"%~f0" >nul && set "PAUSE_ARG=-PauseOnExit"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\reset_retries.ps1" %PAUSE_ARG%
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" (echo 正常に完了しました。) else (echo 失敗しました。終了コード: %EXIT_CODE%)
exit /b %EXIT_CODE%
