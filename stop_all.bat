@echo off
REM IoT System - Stop All Services
REM This script uses port_manager.py to stop all running services

echo ================================================
echo IoT Microservices System - Stopping All Services
echo ================================================
echo.

REM Check if virtual environment exists
if not exist venv (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first to create the virtual environment.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

echo Using port_manager.py to stop all services...
echo.

REM Use port_manager to stop all services
python port_manager.py stop --all

if %errorlevel% neq 0 (
    echo.
    echo WARNING: Some services may not have stopped cleanly.
    echo Trying alternative method using taskkill...
    echo.

    REM Fallback: Kill Python processes running our services
    echo Stopping Python service processes...
    taskkill /F /FI "WINDOWTITLE eq IoT -*" 2>nul

    REM Kill specific Python processes by command line pattern
    for %%s in (catalog message_broker raspberrypi timeSeriesDbConnector analytics account_manager control_center telegram_bot web_dashboard) do (
        echo Checking for %%s...
        wmic process where "commandline like '%%python%%' and commandline like '%%\\%%s\\%%'" delete 2>nul
    )
)

echo.
echo ================================================
echo Services stopped!
echo ================================================
echo.
echo Verifying service status...
python port_manager.py status

echo.
echo All terminal windows should now be closed.
echo If any services are still running, you can:
echo   1. Close their terminal windows manually
echo   2. Use Task Manager to end Python processes
echo   3. Use: python port_manager.py kill --port [PORT_NUMBER]
echo.
pause
