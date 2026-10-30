<#
.SYNOPSIS
    ตั้งค่า Windows Task Scheduler เพื่อให้บอทผลิตคลิป Shopee Affiliate อัตโนมัติตามเวลาที่กำหนด
.DESCRIPTION
    สร้าง Scheduled Task ชื่อ "ShopeeAffiliateRoutine" ที่จะรันไฟล์ run_routine.bat
    ตามเวลาประจำวัน เช่น ทุกวันเวลา 09:00 น. และ 18:00 น.
#>

param (
    [string]$Action = "register",  # register หรือ unregister
    [string[]]$Times = @("09:00", "18:00")  # เวลาที่ต้องการให้รันทุกวัน
)

$TaskName = "ShopeeAffiliateRoutine"
$BatchPath = "C:\Users\non_n\.gemini\antigravity\scratch\shopee-affiliate-bot\run_routine.bat"

if ($Action -eq "unregister") {
    Write-Host "🗑️ กำลังลบ Scheduled Task: $TaskName ..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "✅ ลบ Task เรียบร้อยแล้ว!" -ForegroundColor Green
    exit 0
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "🚀 ตั้งค่า Routine อัตโนมัติใน Windows Task Scheduler" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. ตรวจสอบไฟล์ batch
if (-not (Test-Path $BatchPath)) {
    Write-Error "❌ ไม่พบไฟล์: $BatchPath"
    exit 1
}

# 2. สร้าง Trigger สำหรับแต่ละเวลา
$Triggers = @()
foreach ($time in $Times) {
    Write-Host "⏰ กำหนดเวลาทำงาน: ทุกวัน เวลา $time น." -ForegroundColor Yellow
    $Triggers += New-ScheduledTaskTrigger -Daily -At $time
}

# 3. กำหนด Action ที่จะทำ (รัน run_routine.bat แบบย่อหน้าต่าง)
$TaskAction = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatchPath`"" -WorkingDirectory "C:\Users\non_n\.gemini\antigravity\scratch\shopee-affiliate-bot"

# 4. กำหนด Settings (ให้รันแม้แบตเตอรี่ต่ำ ไม่จำกัดเวลา)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# 5. ลงทะเบียน Task ในระบบ Windows
try {
    # ลบตัวเดิมก่อนถ้ามีอยู่
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask -TaskName $TaskName `
        -Trigger $Triggers `
        -Action $TaskAction `
        -Settings $Settings `
        -Description "Shopee Affiliate Video Automated Routine Generator" | Out-Null

    Write-Host "`n✅ ลงทะเบียน Task สำเร็จเรียบร้อยแล้ว!" -ForegroundColor Green
    Write-Host "📌 บอทจะตื่นมารันทำคลิปอัตโนมัติทุกวันเวลา: $($Times -join ', ') น." -ForegroundColor Green
    Write-Host "📁 ผลลัพธ์คลิปจะถูกเก็บไว้ที่: C:\Users\non_n\.gemini\antigravity\scratch\shopee-affiliate-bot\output" -ForegroundColor Cyan
    Write-Host "`n💡 หากต้องการยกเลิก ให้รันคำสั่ง:" -ForegroundColor Gray
    Write-Host "   powershell -File setup_windows_scheduler.ps1 -Action unregister" -ForegroundColor Gray
} catch {
    Write-Error "❌ เกิดข้อผิดพลาดในการลงทะเบียน: $_"
}
