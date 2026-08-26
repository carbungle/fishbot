@echo off
cd /d "%~dp0"
echo [setup] fishingbot fresh install...
echo.

if not exist "assets" mkdir "assets"
if not exist "config" mkdir "config"
if not exist "data" mkdir "data"
echo [setup] folders ready: assets/ config/ data/

REM install dependencies
echo [setup] installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [setup] trying py -m pip...
  py -m pip install -r requirements.txt
)
if errorlevel 1 (
  echo [setup] trying python3...
  python3 -m pip install -r requirements.txt
)
if errorlevel 1 (
  echo [setup] pip failed - make sure Python 3.9+ is installed and on PATH
  pause
  goto :eof
)
echo [setup] dependencies installed

REM ensure fisher.bat exists
if not exist "fisher.bat" (
  echo @echo off> fisher.bat
  echo cd /d "%%~dp0">> fisher.bat
  echo python fisher_gui.py>> fisher.bat
  echo if errorlevel 1 py fisher_gui.py>> fisher.bat
  echo if errorlevel 1 python3 fisher_gui.py>> fisher.bat
)

REM add to PATH for 'fisher' command
echo %PATH% | find /I "%~dp0" >nul
if errorlevel 1 (
  echo [setup] adding to PATH...
  setx PATH "%PATH%;%~dp0" >nul 2>&1
  echo [setup] PATH updated - reopen cmd to use 'fisher' anywhere
) else (
  echo [setup] PATH already ok
)

echo.
echo [setup] Done. Open cmd and type:  fisher
echo   On first run, log in, then use top-right [calibrate] (press twice) for 9 steps.
echo.
pause
echo [setup] cleaning up setup.bat...
(goto) 2>nul & del "%~f0"
