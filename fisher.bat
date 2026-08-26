@echo off
cd /d "%~dp0"
REM fisher launcher - use: fisher  (from cmd in this folder, or anywhere if PATH added)
python fisher_gui.py
if errorlevel 1 py fisher_gui.py
if errorlevel 1 python3 fisher_gui.py
if errorlevel 1 (
  echo [fisher] Python not found or deps missing. Run setup.bat as admin, or: pip install -r requirements.txt
  pause
)
