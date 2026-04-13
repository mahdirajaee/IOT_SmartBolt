@echo off
REM Helper script to run a single IoT service in the current window
REM Usage: run_service.bat <service_name>

if "%1"=="" (
    echo ERROR: No service specified!
    echo.
    echo Usage: run_service.bat [service_name]
    echo.
    echo Available services:
    echo   catalog   - Resource Catalog ^(Port 8081^)
    echo   message_broker     - Message Broker ^(MQTT only^)
    echo   raspberrypi        - Raspberry Pi Simulator ^(Port 8086^)
    echo   timeseries         - TimeSeries DB Connector ^(Port 8082^)
    echo   analytics          - Analytics Service ^(Port 8083^)
    echo   account_manager    - Account Manager ^(Port 8084^)
    echo   control_center     - Control Center ^(Port 8085^)
    echo   telegram_bot       - Telegram Bot ^(Port 8087^)
    echo   web_dashboard      - Web Dashboard ^(Port 8090^)
    echo.
    pause
    exit /b 1
)

set SERVICE=%1

REM Check if virtual environment exists
if not exist venv (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first to create the virtual environment.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Map service names to directories and scripts
if "%SERVICE%"=="catalog" (
    set SERVICE_DIR=catalog
    set SERVICE_NAME=Resource Catalog
    set SERVICE_PORT=8081
) else if "%SERVICE%"=="message_broker" (
    set SERVICE_DIR=message_broker
    set SERVICE_NAME=Message Broker
    set SERVICE_PORT=MQTT
) else if "%SERVICE%"=="raspberrypi" (
    set SERVICE_DIR=raspberrypi
    set SERVICE_NAME=Raspberry Pi Simulator
    set SERVICE_PORT=8086
) else if "%SERVICE%"=="timeseries" (
    set SERVICE_DIR=timeSeriesDbConnector
    set SERVICE_NAME=TimeSeries DB Connector
    set SERVICE_PORT=8082
) else if "%SERVICE%"=="analytics" (
    set SERVICE_DIR=analytics
    set SERVICE_NAME=Analytics Service
    set SERVICE_PORT=8083
) else if "%SERVICE%"=="account_manager" (
    set SERVICE_DIR=account_manager
    set SERVICE_NAME=Account Manager
    set SERVICE_PORT=8084
) else if "%SERVICE%"=="control_center" (
    set SERVICE_DIR=control_center
    set SERVICE_NAME=Control Center
    set SERVICE_PORT=8085
) else if "%SERVICE%"=="telegram_bot" (
    set SERVICE_DIR=telegram_bot
    set SERVICE_NAME=Telegram Bot
    set SERVICE_PORT=8087
) else if "%SERVICE%"=="web_dashboard" (
    set SERVICE_DIR=web_dashboard
    set SERVICE_NAME=Web Dashboard
    set SERVICE_PORT=8090
) else (
    echo ERROR: Unknown service "%SERVICE%"
    echo Run this script without arguments to see available services.
    pause
    exit /b 1
)

echo ================================================
echo Starting %SERVICE_NAME% ^(Port: %SERVICE_PORT%^)
echo ================================================
echo.
echo Press Ctrl+C to stop the service
echo.

REM Change to service directory and run
cd %SERVICE_DIR%
python main.py

REM Keep window open if there's an error
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Service exited with error code %errorlevel%
    pause
)
