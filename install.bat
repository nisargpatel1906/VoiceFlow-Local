@echo off
REM =============================================================================
REM VoiceFlow Local - Installation Script
REM =============================================================================
REM This script sets up the Python environment and installs dependencies.
REM Run this once before using the application.
REM =============================================================================

set "PYTHON_EXE=py -3.10"

echo ============================================
echo   VoiceFlow Local - Installation
echo ============================================
echo.

REM Check if Python 3.10 is installed
%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10 is not installed.
    echo Install Python 3.10 and ensure the Python Launcher py is available.
    pause
    exit /b 1
)

echo [OK] Python 3.10 found
echo.

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    %PYTHON_EXE% -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
    echo.
) else (
    echo [INFO] Virtual environment already exists
    echo.
)

REM Activate virtual environment and install dependencies
echo Installing dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

REM Create models directory
if not exist "models" (
    echo Creating models directory...
    mkdir models
)

REM Download the faster-whisper model
set "MODEL_SIZE=medium"
for /f %%i in ('venv\Scripts\python.exe -c "import config; print(config.MODEL_SIZE)"') do set "MODEL_SIZE=%%i"
echo Downloading faster-whisper '%MODEL_SIZE%' model (this may take a while)...
venv\Scripts\python.exe -c "import config; from faster_whisper import WhisperModel; WhisperModel(config.MODEL_SIZE, download_root='models')"
if errorlevel 1 (
    echo [WARNING] Model download failed. It will download on first run instead.
) else (
    echo [OK] Model downloaded to models/
)
echo.

echo ============================================
echo   Installation complete!
echo   Run start.bat to launch VoiceFlow Local.
echo ============================================
pause
