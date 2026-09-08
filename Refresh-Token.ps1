# =====================================================================
#  Swayam Capital - refresh the FYERS token
#
#  Run this ONCE each trading day, AFTER 08:00 IST and before you trade.
#  A token generated before dawn has been rejected by FYERS by lunchtime.
#
#  HOW TO RUN IT
#    Right-click this file and choose "Run with PowerShell".
#    Or, from a PowerShell window in this folder:  .\Refresh-Token.ps1
#
#  WHAT IT DOES
#    1. Opens your browser at the FYERS login page.
#    2. You log in with your PIN and OTP.
#    3. FYERS sends you to a page whose ADDRESS contains the code.
#       Copy the WHOLE address bar and paste it back here.
#    4. It writes the new token into .env for the app on this PC,
#       and uploads it to Google Secret Manager for the live website.
#    5. It then proves the token works by asking FYERS for your balance.
#
#  SIGNS YOUR TOKEN HAS DIED
#    "no live price", legs showing no real price, or strikes jumping about
#    a thousand points away from where NIFTY actually is.
# =====================================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Cannot find the Python environment at $Python" -ForegroundColor Red
    Write-Host "Expected it inside the project folder. Nothing was changed." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

$hour = (Get-Date).Hour
if ($hour -lt 8) {
    Write-Host ""
    Write-Host "  It is before 08:00. A token made this early has been rejected" -ForegroundColor Yellow
    Write-Host "  by FYERS later the same day. Come back after 8am." -ForegroundColor Yellow
    Write-Host ""
    $go = Read-Host "  Carry on anyway? (y/N)"
    if ($go -ne "y") { exit 0 }
}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Swayam Capital - FYERS token refresh" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

& $Python (Join-Path $ProjectRoot "scripts\refresh_fyers_token.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  The refresh did not complete. Your old token is unchanged." -ForegroundColor Red
    Read-Host "  Press Enter to close"
    exit 1
}

Write-Host ""
Write-Host "  Checking the new token against your account..." -ForegroundColor Cyan

$check = @'
import sys
sys.path.insert(0, "src")
from dotenv import load_dotenv
load_dotenv(".env", override=True)
from swayam.fyers_client import FyersClient
m = FyersClient().model
status = m.market_status()
if status.get("s") != "ok":
    print("  FAILED: FYERS refused the new token.")
    raise SystemExit(1)
funds = m.funds()
total = next((float(r["equityAmount"]) for r in funds.get("fund_limit", []) if int(r["id"]) == 1), None)
quote = m.quotes({"symbols": "NSE:NIFTY50-INDEX"})
spot = quote["d"][0]["v"]["lp"]
print(f"  Token works.")
print(f"  Your total balance : Rs {total:,.2f}")
print(f"  NIFTY              : {spot:,.2f}")
'@
$check | & $Python -
if ($LASTEXITCODE -ne 0) {
    Write-Host "  The new token did not work. Try again." -ForegroundColor Red
    Read-Host "  Press Enter to close"
    exit 1
}

Write-Host ""
Write-Host "  Done. The app on this PC will use the new token immediately." -ForegroundColor Green
Write-Host ""
Write-Host "  NOTE ABOUT THE LIVE WEBSITE:" -ForegroundColor Yellow
Write-Host "  swayam.abhisheksikka.com should pick this up within a minute, with" -ForegroundColor Yellow
Write-Host "  no restart and no redeploy. It reads the token while running now." -ForegroundColor Yellow
Write-Host "  That has NEVER been proven in production, so if the live site still" -ForegroundColor Yellow
Write-Host "  shows no prices two minutes from now, a redeploy is the escape" -ForegroundColor Yellow
Write-Host "  hatch. Do not redeploy before waiting those two minutes." -ForegroundColor Yellow
Write-Host ""
Read-Host "  Press Enter to close"
