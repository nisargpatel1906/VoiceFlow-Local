@echo off
REM =============================================================================
REM VoiceFlow Local - Launch Script
REM =============================================================================
REM Starts the voice dictation application using the virtual environment.
REM =============================================================================

echo ============================================
echo   VoiceFlow Local - Starting...
echo ============================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo [ERROR] Virtual environment not found.
    echo Please run install.bat first.
    pause
    exit /b 1
)

REM Launch the main application
set KMP_DUPLICATE_LIB_OK=TRUE
venv\Scripts\python.exe main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Application exited with an error.
    echo Check the error messages above for details.
    pause
)
