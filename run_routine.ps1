# run_routine.ps1 - Automated Routine Runner for PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BotDir = "C:\Users\non_n\.gemini\antigravity\scratch\shopee-affiliate-bot"
Set-Location -Path $BotDir

$PythonBin = "C:\Users\non_n\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $PythonBin)) {
    $PythonBin = "python"
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "🛒 Shopee Affiliate Bot — รันระบบ Routine อัตโนมัติ" -ForegroundColor Cyan
Write-Host "📅 เวลา: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

& $PythonBin main.py --routine --products 1 --no-telegram

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ ผลิตคลิปเสร็จสมบูรณ์! ตรวจสอบไฟล์ในโฟลเดอร์ output/" -ForegroundColor Green
} else {
    Write-Host "`n⚠️ พบข้อผิดพลาด ดูรายละเอียดใน output/run.log" -ForegroundColor Red
}
