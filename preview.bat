@echo off
cd /d "%~dp0"
echo ============================================
echo   PREVIEW - check the detector (ESC in window to close)
echo ============================================
python main.py --preview
pause