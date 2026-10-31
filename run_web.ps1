# run_web.ps1 - PowerShell Launcher for Shopee Clip Maker Web MVP
$pythonPath = "C:\Users\non_n\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $pythonPath)) {
    $pythonPath = "python"
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  🛒 Shopee Clip Maker AI - Web MVP (FastAPI)" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "เปิดเบราว์เซอร์ที่: http://localhost:8000" -ForegroundColor Green

Start-Process "http://localhost:8000"
& $pythonPath -m uvicorn web.server:app --host 127.0.0.1 --port 8000 --reload
