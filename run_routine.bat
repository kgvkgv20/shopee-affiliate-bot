@echo off
setlocal
echo ========================================================
echo   Shopee Affiliate Bot - Automated Routine Runner
echo   Date/Time: %DATE% %TIME%
echo ========================================================

cd /d "C:\Users\non_n\.gemini\antigravity\scratch\shopee-affiliate-bot"

set PYTHON_BIN=C:\Users\non_n\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYTHON_BIN%" (
    set PYTHON_BIN=python
)

echo [1/2] Running Shopee Routine...
"%PYTHON_BIN%" main.py --routine --products 1 --no-telegram

if %ERRORLEVEL% EQU 0 (
    echo [2/2] SUCCESS: Video generated in output/ folder!
) else (
    echo [2/2] FAILED: Check logs at output/run.log
)

echo ========================================================
endlocal
