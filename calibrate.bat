@echo off
cd /d "%~dp0"
echo ============================================
echo   CALIBRATION - one-time setup
echo   Have the game open at the fishing spot.
echo ============================================
echo.
echo Step 1/9: Click the 2 corners of the FISHING BAR.
echo   (top-left, then bottom-right)
pause
python main.py --calibrate
if errorlevel 1 goto :error
echo.
echo Step 2/9: Click the 2 corners of the status TEXT area.
echo   (top-left, then bottom-right)
pause
python main.py --set-text
if errorlevel 1 goto :error
echo.
echo Step 3/9: Capture the "hold" text.
echo   When the menu shows HOLD, press Enter to capture it.
python main.py --snap-text hold
if errorlevel 1 goto :error
echo.
echo Step 4/9: Capture the "about to start running" text.
echo   When it shows ABOUT TO START RUNNING, press Enter to capture it.
python main.py --snap-text about
if errorlevel 1 goto :error
echo.
echo Step 5/9: Capture the "running" text.
echo   When it shows RUNNING, press Enter to capture it.
python main.py --snap-text running
if errorlevel 1 goto :error
echo.
echo Step 6/9: Click the 2 corners of the COLOUR-change indicator.
echo   (top-left, then bottom-right)
pause
python main.py --set-color
if errorlevel 1 goto :error
echo.
echo Step 7/9: Click the 4 SEQUENCE locations in order.
echo   1-3 are the spots clicked after pressing F, 4 is after pressing T.
pause
python main.py --set-seq
if errorlevel 1 goto :error
echo.
echo Step 8/9: MODE 2 - click the 7 SEQUENCE locations in order.
echo   (press F1 at runtime to switch into MODE 2)
echo   1-6 are the spots clicked after pressing F, 7 is after pressing T.
pause
python main.py --set-seq2
if errorlevel 1 goto :error
echo.
echo Step 9/9: MODE 2 - click the 4 STORE locations in order.
echo   (this is the trunk store used every 3 catches in MODE 2)
echo   1-3 are the spots clicked after pressing F, 4 is after pressing T.
pause
python main.py --set-seq2-store
if errorlevel 1 goto :error
echo.
echo ============================================
echo   Calibration complete. You can now run: run.bat
echo ============================================
pause
exit /b 0
:error
echo.
echo Something went wrong. Check the message above.
pause