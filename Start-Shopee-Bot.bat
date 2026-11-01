@echo off
chcp 65001 > nul
title Shopee Video Affiliate Bot Pro

echo ===================================================================
echo   🛒 Shopee & TikTok Affiliate Auto-Post Bot Pro (Commercial Edition)
echo ===================================================================
echo.
echo [1/3] กำลังตรวจสอบสภาพแวดล้อมระบบ...

set PYTHON_CMD=C:\Users\non_n\AppData\Local\Programs\Python\Python312\python.exe
if not exist "%PYTHON_CMD%" (
    set PYTHON_CMD=python
)

"%PYTHON_CMD%" --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] ไม่พบ Python ในระบบ กรุณาติดตั้ง Python 3.10+ ก่อนใช้งาน
    pause
    exit /b 1
)

echo [✓] Python พร้อมใช้งาน
echo [2/3] กำลังตรวจสอบ ADB & FFmpeg...

set ADB_EXE=C:\Users\non_n\AppData\Local\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe
if exist "%ADB_EXE%" (
    echo [✓] Android Debug Bridge (ADB) พร้อมใช้งาน
) else (
    echo [i] กำลังใช้ adb จากระบบส่วนกลาง
)

echo [3/3] กำลังเริ่มต้นเซิร์ฟเวอร์ และเปิดหน้าจอ Desktop App...
echo.

:: เริ่มรัน Uvicorn ในหน้าต่างแยกที่ซ่อนได้
start "Shopee Bot Engine" /min "%PYTHON_CMD%" -m uvicorn web.server:app --host 127.0.0.1 --port 8000

:: รอเซิร์ฟเวอร์เริ่มทำงาน 2 วินาที
timeout /t 2 /nobreak > nul

:: เปิดหน้าต่างแบบ Native Desktop App ด้วย Microsoft Edge หรือ Google Chrome
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app=http://localhost:8000 --window-size=1360,900
) else if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app=http://localhost:8000 --window-size=1360,900
) else (
    start "" http://localhost:8000
)

echo ===================================================================
echo   🎉 ระบบเริ่มทำงานเรียบร้อย!
echo   หน้าต่างแอปพลิเคชันจะเปิดขึ้นมาอัตโนมัติ (http://localhost:8000)
echo   ปิดหน้าต่างคอนโซลนี้เมื่อต้องการหยุดการทำงาน
echo ===================================================================
echo.
