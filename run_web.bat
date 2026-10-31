@echo off
chcp 65001 > nul
echo ========================================================
echo   🛒 Shopee Clip Maker AI - Web MVP Launcher
echo ========================================================
echo.
echo กำลังเริ่มต้น Web Application บน http://localhost:8000 ...
echo กรุณารอสักครู่ ระบบจะเปิดเบราว์เซอร์ให้อัตโนมัติ...
echo.

set PYTHON_CMD=C:\Users\non_n\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYTHON_CMD%" (
    set PYTHON_CMD=python
)

start "" http://localhost:8000
"%PYTHON_CMD%" -m uvicorn web.server:app --host 127.0.0.1 --port 8000 --reload
pause
