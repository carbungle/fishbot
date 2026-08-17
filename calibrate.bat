@echo off
cd /d "%~dp0"
echo ============================================
echo   CALIBRATION - set it up once
echo ============================================
echo.
echo Step 1: Fishing bar region (click 2 corners)
echo.
python main.py --calibrate
if errorlevel 1 goto :error
echo.
echo Step 2 (optional): status TEXT region (click 2 corners)
echo   Press Enter to do it, or type "skip" to skip.
set /p ans="Run text calibration [Enter/skip]: "
if /i "%ans%"=="skip" goto :color
python main.py --set-text
if errorlevel 1 goto :error
:color
echo.
echo Step 3 (optional): COLOUR region that turns a different colour
echo   This adds the 5-second release. Press Enter to do it,
echo   or type "skip" to skip.
set /p ans2="Run colour calibration [Enter/skip]: "
if /i "%ans2%"=="skip" goto :done
python main.py --set-color
if errorlevel 1 goto :error
:done
echo.
echo Calibration done. You can now run: run.bat
pause
exit /b 0
:error
echo.
echo Something went wrong. Check the message above.
pause