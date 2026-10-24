@echo off
setlocal
cd /d "%~dp0.."
set "name=GTNH-Updater"
if "%~1"=="--legacy" set "name=GTNH-Updater-Win7"
python -m PyInstaller --clean --noconfirm --onefile --console --name %name% --add-data "lib\cacert.pem;lib" gtnh_updater.py
exit /b %errorlevel%
