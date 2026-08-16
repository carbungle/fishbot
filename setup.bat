@echo off
echo Installing dependencies for the fishing bot...
python -m pip install -r requirements.txt
echo.
echo Done. If you see errors above, Python is not installed or not on PATH.
echo You need Python 3.9 or newer.
ping -n 4 127.0.0.1 >nul