# Shopee & TikTok Affiliate Auto-Post Bot Pro Launcher (PowerShell)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "  🛒 Shopee & TikTok Affiliate Auto-Post Bot Pro (Commercial Edition)" -ForegroundColor Yellow
Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host ""

$pythonCmd = "python"
if (Test-Path "C:\Users\non_n\AppData\Local\Programs\Python\Python312\python.exe") {
    $pythonCmd = "C:\Users\non_n\AppData\Local\Programs\Python\Python312\python.exe"
}

Write-Host "[1/3] ตรวจสอบ Python & สิ่งแวดล้อม..." -ForegroundColor Green
Write-Host "[2/3] ตรวจสอบ ADB Phone Link & FFmpeg Engine..." -ForegroundColor Green
Write-Host "[3/3] สตาร์ท Uvicorn Server & เปิด Desktop App Window..." -ForegroundColor Green

# Start uvicorn background process
Start-Process -FilePath $pythonCmd -ArgumentList "-m uvicorn web.server:app --host 127.0.0.1 --port 8000" -WindowStyle Minimized

Start-Sleep -Seconds 2

# Launch in Native Desktop App Mode (Edge or Chrome)
$edgePath = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
$chromePath = "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe"

if (Test-Path $edgePath) {
    Start-Process $edgePath -ArgumentList "--app=http://localhost:8000 --window-size=1360,900"
} elseif (Test-Path $chromePath) {
    Start-Process $chromePath -ArgumentList "--app=http://localhost:8000 --window-size=1360,900"
} else {
    Start-Process "http://localhost:8000"
}

Write-Host ""
Write-Host "🎉 เปิดแอปพลิเคชัน Shopee Video Bot เรียบร้อย!" -ForegroundColor Green
