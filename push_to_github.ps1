# push_to_github.ps1
# สคริปต์นำโปรเจกต์ขึ้น GitHub (kgvkgv20/shopee-affiliate-bot) อัตโนมัติ

$env:Path = "C:\Users\non_n\AppData\Local\Programs\MinGit\cmd;C:\Users\non_n\AppData\Local\Programs\gh;$env:Path"
Set-Location -Path "C:\Users\non_n\.gemini\antigravity\scratch\shopee-affiliate-bot"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "🚀 Shopee Affiliate Bot — นำโปรเจกต์ขึ้น GitHub (kgvkgv20)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. ตรวจสอบการล็อกอิน GitHub
$auth = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n🔑 กรุณาเข้าสู่ระบบ GitHub ด้วยคำสั่งด้านล่าง (ระบบจะเปิดเบราว์เซอร์ให้กดยืนยัน 1 คลิก):" -ForegroundColor Yellow
    Write-Host "   gh auth login -w -p https" -ForegroundColor Green
    Write-Host "`nกำลังเปิดหน้าต่างยืนยันสิทธิ์ GitHub..." -ForegroundColor Yellow
    gh auth login -w -p https
}

# 2. สร้างและเชื่อมต่อ Remote Repository
Write-Host "`n📦 กำลังสร้าง Repository บน GitHub และอัปโหลดโค้ด..." -ForegroundColor Yellow
gh repo create kgvkgv20/shopee-affiliate-bot --private --source=. --remote=origin --push

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ อัปโหลดขึ้น GitHub สำเร็จแล้วที่: https://github.com/kgvkgv20/shopee-affiliate-bot" -ForegroundColor Green
    
    # 3. ส่ง Secret GEMINI_API_KEY ไปยัง GitHub Secrets อัตโนมัติ
    if (Test-Path .env) {
        $envContent = Get-Content .env
        $geminiKey = ($envContent | Where-Object { $_ -match "^GEMINI_API_KEY=(.+)$" }) -replace "^GEMINI_API_KEY=", ""
        if ($geminiKey) {
            Write-Host "🔐 กำลังตั้งค่า GEMINI_API_KEY ใน GitHub Secrets อัตโนมัติ..." -ForegroundColor Cyan
            $geminiKey | gh secret set GEMINI_API_KEY --repo kgvkgv20/shopee-affiliate-bot
            Write-Host "✅ ตั้งค่า Secret สำเร็จ! GitHub Actions พร้อมรันบนคลาวด์ได้ทันที" -ForegroundColor Green
        }
    }
} else {
    Write-Host "`n⚠️ หากมี Repository อยู่แล้วบน GitHub ให้ใช้คำสั่ง:" -ForegroundColor Yellow
    Write-Host "   git remote add origin https://github.com/kgvkgv20/shopee-affiliate-bot.git" -ForegroundColor Gray
    Write-Host "   git push -u origin main" -ForegroundColor Gray
}
