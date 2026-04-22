@echo off
setlocal

REM =============================================================================
REM VoiceFlow Local - Launch Script
REM =============================================================================
REM Starts the voice dictation application using the virtual environment.
REM =============================================================================

REM Check if virtual environment exists
if not exist "venv" (
    > voiceflow_start.log echo [ERROR] Virtual environment not found. Please run install.bat first.
    exit /b 1
)

REM Launch the main application
set KMP_DUPLICATE_LIB_OK=TRUE
if exist "venv\Scripts\pythonw.exe" (
    powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command ^
        "$env:KMP_DUPLICATE_LIB_OK='TRUE';" ^
        "Start-Process -FilePath '%CD%\venv\Scripts\pythonw.exe' -ArgumentList 'main.py' -WorkingDirectory '%CD%' -WindowStyle Hidden"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command ^
        "$env:KMP_DUPLICATE_LIB_OK='TRUE';" ^
        "Start-Process -FilePath '%CD%\venv\Scripts\python.exe' -ArgumentList 'main.py' -WorkingDirectory '%CD%' -WindowStyle Hidden"
)

exit /b 0
