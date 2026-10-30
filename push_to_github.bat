@echo off
setlocal
echo ========================================================
echo   Shopee Affiliate Bot - Push to GitHub (kgvkgv20)
echo ========================================================

set "PATH=C:\Users\non_n\AppData\Local\Programs\MinGit\cmd;C:\Users\non_n\AppData\Local\Programs\gh;%PATH%"
cd /d "C:\Users\non_n\.gemini\antigravity\scratch\shopee-affiliate-bot"

powershell -ExecutionPolicy Bypass -File push_to_github.ps1

pause
