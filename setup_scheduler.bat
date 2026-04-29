@echo off
echo ============================================
echo   JobScraper - Windows Task Scheduler Setup
echo ============================================
echo.

:: Get the current directory (project root)
set PROJECT_DIR=%~dp0
set PROJECT_DIR=%PROJECT_DIR:~0,-1%

:: Try to find Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH.
    echo Please install Python or add it to your PATH.
    pause
    exit /b 1
)

:: Get Python path
for /f "tokens=*" %%i in ('where python') do (
    set PYTHON_PATH=%%i
    goto :found_python
)

:found_python
echo Found Python at: %PYTHON_PATH%
echo Project directory: %PROJECT_DIR%
echo.

:: Read schedule from config (default 10:00)
set HOUR=10
set MINUTE=00
echo Schedule: Daily at %HOUR%:%MINUTE%
echo.

:: Create the scheduled task
echo Creating scheduled task "JobScraper_Daily"...
schtasks /create /tn "JobScraper_Daily" /tr "\"%PROJECT_DIR%\run_scraper.bat\"" /sc daily /st %HOUR%:%MINUTE% /f /rl highest

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo   Task created successfully!
    echo ============================================
    echo.
    echo Task Name:  JobScraper_Daily
    echo Schedule:   Daily at %HOUR%:%MINUTE%
    echo Command:    python main.py --run-now
    echo.
    echo To modify: Open Task Scheduler ^> Task Scheduler Library ^> JobScraper_Daily
    echo To delete: schtasks /delete /tn "JobScraper_Daily" /f
    echo To run now: schtasks /run /tn "JobScraper_Daily"
) else (
    echo.
    echo ERROR: Failed to create scheduled task.
    echo Try running this script as Administrator.
)

echo.
pause
