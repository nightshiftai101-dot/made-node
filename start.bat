@echo off
echo ============================================================
echo   M.A.D.E. Coin Node  v0.9.1-testnet
echo   Making A Daily Earning
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3 is not installed.
    echo Download it from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet

echo.
echo Starting M.A.D.E. Coin Node...
echo.
python node.py %*
pause
