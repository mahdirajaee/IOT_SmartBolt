@echo off
REM IoT System Setup Script for Windows
REM 

echo ================================================
echo IoT Microservices System - Windows Setup
echo ================================================
echo.

REM 
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.11 or higher from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [1/4] Checking Python version...
python --version

echo.
echo [2/4] Creating virtual environment...
if exist venv (
    echo Virtual environment already exists. Skipping creation.
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
)

echo.
echo [3/4] Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ERROR: Failed to activate virtual environment!
    pause
    exit /b 1
)

echo.
echo [4/4] Installing dependencies...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo ERROR: Failed to upgrade pip!
    pause
    exit /b 1
)

pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo ================================================
echo Setup completed successfully!
echo ================================================
echo.
echo Next steps:
echo 1. Install Mosquitto MQTT Broker:
echo    - Download from: https://mosquitto.org/download/
echo    - Or use: winget install EclipseFoundation.Mosquitto
echo.
echo 2. Start the MQTT broker:
echo    - Run: net start mosquitto
echo    - Or: mosquitto -v (in a separate window)
echo.
echo 3. Run services:
echo    - Individual service: run_service.bat catalog
echo    - All services: run_all.bat
echo.
echo To activate the virtual environment manually:
echo    venv\Scripts\activate
echo.
pause
