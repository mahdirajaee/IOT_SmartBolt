@echo off
REM IoT System - Start All Services in Separate Windows
REM This is the Windows equivalent of "make run-all" (which uses tmux)

echo ================================================
echo IoT Microservices System - Starting All Services
echo ================================================
echo.

REM Check if virtual environment exists
if not exist venv (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first to create the virtual environment.
    pause
    exit /b 1
)

echo Starting services in the correct order...
echo.
echo Each service will open in its own terminal window.
echo Close the terminal windows to stop individual services,
echo or run stop_all.bat to stop all services at once.
echo.

REM Get the current directory path
set BASE_DIR=%~dp0

REM 1. Start Resource Catalog (must start first - other services depend on it)
echo [1/9] Starting Resource Catalog (Port 8081)...
start "IoT - Resource Catalog (8081)" cmd /k "%BASE_DIR%run_service.bat catalog"
timeout /t 2 /nobreak >nul

REM 2. Start Message Broker (MQTT router)
echo [2/9] Starting Message Broker (MQTT)...
start "IoT - Message Broker (MQTT)" cmd /k "%BASE_DIR%run_service.bat message_broker"
timeout /t 1 /nobreak >nul

REM 3. Start TimeSeries DB Connector
echo [3/9] Starting TimeSeries DB Connector (Port 8082)...
start "IoT - TimeSeries DB (8082)" cmd /k "%BASE_DIR%run_service.bat timeseries"
timeout /t 2 /nobreak >nul

REM 4. Start Account Manager
echo [4/9] Starting Account Manager (Port 8084)...
start "IoT - Account Manager (8084)" cmd /k "%BASE_DIR%run_service.bat account_manager"
timeout /t 2 /nobreak >nul

REM 5. Start Analytics Service (depends on TimeSeries DB)
echo [5/9] Starting Analytics Service (Port 8083)...
start "IoT - Analytics (8083)" cmd /k "%BASE_DIR%run_service.bat analytics"
timeout /t 2 /nobreak >nul

REM 6. Start Control Center (depends on Analytics)
echo [6/9] Starting Control Center (Port 8085)...
start "IoT - Control Center (8085)" cmd /k "%BASE_DIR%run_service.bat control_center"
timeout /t 1 /nobreak >nul

REM 7. Start Raspberry Pi Simulator (depends on Resource Catalog)
echo [7/9] Starting Raspberry Pi Simulator (Port 8086)...
start "IoT - Raspberry Pi (8086)" cmd /k "%BASE_DIR%run_service.bat raspberrypi"
timeout /t 1 /nobreak >nul

REM 8. Start Telegram Bot (depends on Account Manager)
echo [8/9] Starting Telegram Bot (Port 8087)...
start "IoT - Telegram Bot (8087)" cmd /k "%BASE_DIR%run_service.bat telegram_bot"
timeout /t 1 /nobreak >nul

REM 9. Start Web Dashboard (start last - depends on Account Manager)
echo [9/9] Starting Web Dashboard (Port 8090)...
start "IoT - Web Dashboard (8090)" cmd /k "%BASE_DIR%run_service.bat web_dashboard"

echo.
echo ================================================
echo All services started!
echo ================================================
echo.
echo You should now have 9 terminal windows open, one for each service.
echo.
echo Service Status:
echo   1. Resource Catalog     - http://localhost:8081
echo   2. Message Broker       - MQTT on port 1883
echo   3. TimeSeries DB        - http://localhost:8082
echo   4. Account Manager      - http://localhost:8084
echo   5. Analytics Service    - http://localhost:8083
echo   6. Control Center       - http://localhost:8085
echo   7. Raspberry Pi         - http://localhost:8086
echo   8. Telegram Bot         - http://localhost:8087
echo   9. Web Dashboard        - http://localhost:8090
echo.
echo To view service status: python port_manager.py status
echo To stop all services:   stop_all.bat
echo.
echo IMPORTANT: Make sure Mosquitto MQTT Broker is running!
echo   Check with: netstat -an ^| findstr :1883
echo   Start with: net start mosquitto
echo            or: mosquitto -v (in a separate window)
echo.
pause
