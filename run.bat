@echo off
cd /d "%~dp0"
echo [migrate] fishingbot reorganization for old users...
echo.

if not exist "assets" mkdir "assets"
if not exist "config" mkdir "config"
if not exist "data" mkdir "data"

REM move pngs to assets
if exist "text_hold.png" move /Y "text_hold.png" "assets\text_hold.png" >nul
if exist "text_about.png" move /Y "text_about.png" "assets\text_about.png" >nul
if exist "text_running.png" move /Y "text_running.png" "assets\text_running.png" >nul
if exist "shutdown.png" move /Y "shutdown.png" "assets\shutdown.png" >nul
if exist "..\shutdown.png" if not exist "assets\shutdown.png" copy /Y "..\shutdown.png" "assets\shutdown.png" >nul

REM move configs to config
if exist "cfg.json" if not exist "config\cfg.json" move /Y "cfg.json" "config\cfg.json" >nul
if exist "cfg.txt" if not exist "config\cfg.txt" move /Y "cfg.txt" "config\cfg.txt" >nul

REM move data files to data
if exist "users.dat" if not exist "data\users.dat" move /Y "users.dat" "data\users.dat" >nul
if exist "session.dat" if not exist "data\session.dat" move /Y "session.dat" "data\session.dat" >nul
if exist "fish_counter.txt" if not exist "data\fish_counter.txt" move /Y "fish_counter.txt" "data\fish_counter.txt" >nul
if exist "owner.dat" if not exist "data\owner.dat" move /Y "owner.dat" "data\owner.dat" >nul

REM clean old clutter (but keep fisher.bat, setup.bat, run.bat)
if exist "calibrate.bat" del /f /q "calibrate.bat" >nul 2>&1
if exist "preview.bat" del /f /q "preview.bat" >nul 2>&1
if exist "__pycache__" rmdir /s /q "__pycache__" >nul 2>&1
if exist "main.pyc" del /f /q "main.pyc" >nul 2>&1
echo [migrate] folders reorganized to assets/config/data

REM ensure fisher.bat exists
if not exist "fisher.bat" (
  echo @echo off> fisher.bat
  echo cd /d "%%~dp0">> fisher.bat
  echo python fisher_gui.py>> fisher.bat
  echo if errorlevel 1 py fisher_gui.py>> fisher.bat
  echo [migrate] created fisher.bat
)

REM add to PATH for 'fisher' command
echo %PATH% | find /I "%~dp0" >nul
if errorlevel 1 (
  echo [migrate] adding to PATH...
  setx PATH "%PATH%;%~dp0" >nul 2>&1
  echo [migrate] PATH updated - reopen cmd to use 'fisher' anywhere
) else (
  echo [migrate] PATH already ok
)

echo.
echo [migrate] Done. Your folder now looks like the new clean layout.
echo   Just open cmd and type:  fisher
echo   Calibrate via top-right [calibrate] button (press twice).
echo.
pause
echo [migrate] cleaning up run.bat...
(goto) 2>nul & del "%~f0"
