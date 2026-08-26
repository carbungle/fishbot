@echo off
cd /d "%~dp0"
echo [migrate] fisher reorganization...

if not exist "assets" mkdir "assets"
if exist "text_hold.png" move /Y "text_hold.png" "assets\text_hold.png" >nul
if exist "text_about.png" move /Y "text_about.png" "assets\text_about.png" >nul
if exist "text_running.png" move /Y "text_running.png" "assets\text_running.png" >nul
if exist "shutdown.png" move /Y "shutdown.png" "assets\shutdown.png" >nul

if exist "setup.bat" del /f /q "setup.bat" >nul 2>&1
if exist "calibrate.bat" del /f /q "calibrate.bat" >nul 2>&1
if exist "preview.bat" del /f /q "preview.bat" >nul 2>&1
echo [migrate] removed old bats, moved pngs to assets\

REM add current folder to user PATH for 'fisher' command
echo %PATH% | find /I "%~dp0" >nul
if errorlevel 1 (
  echo [migrate] adding to PATH...
  setx PATH "%PATH%;%~dp0" >nul 2>&1
  echo [migrate] PATH updated - reopen cmd to use 'fisher'
) else (
  echo [migrate] PATH already ok
)

REM ensure fisher.bat exists
if not exist "fisher.bat" (
  echo @echo off> fisher.bat
  echo cd /d "%%~dp0">> fisher.bat
  echo python fisher_gui.py>> fisher.bat
)

echo.
echo [migrate] Done. Use:  fisher   (in cmd, from this folder or anywhere after reopen)
echo Calibrate via top-right [calibrate] button in console (press twice).
echo.
pause
