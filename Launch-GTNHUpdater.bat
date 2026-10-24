@echo off
setlocal
if exist "%~dp0GTNH-Updater.exe" (
  "%~dp0GTNH-Updater.exe" %*
  goto finish
)
if exist "%~dp0GTNH-Updater-Win7.exe" (
  "%~dp0GTNH-Updater-Win7.exe" %*
  goto finish
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0gtnh_updater.py" %*
) else (
  python "%~dp0gtnh_updater.py" %*
)
:finish
set "result=%errorlevel%"
if "%~1"=="" pause
exit /b %result%
