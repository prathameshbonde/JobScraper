@echo off
REM Wrapper script for scheduled task execution
setlocal enabledelayedexpansion

:: Set project directory
set PROJECT_DIR=%~dp0
set PROJECT_DIR=!PROJECT_DIR:~0,-1!

:: Run Python with absolute path logging
cd /d "%PROJECT_DIR%"
python main.py --run-now >> "%PROJECT_DIR%\logs\scheduler.log" 2>&1
