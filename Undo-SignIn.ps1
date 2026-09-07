# =====================================================================
# Undo-SignIn.ps1
#
# THE PANIC BUTTON. Double-click this if the terminal ever refuses to let
# you in after Google sign-in was switched on.
#
# It puts the site back exactly as it was before: no sign-in, open to
# anyone with the address. That is less safe, but it is better than you
# being locked out of your own terminal at 1pm with a position open.
#
# You can always run this. Identity-Aware Proxy protects the APP, not your
# Google Cloud account, so you keep full admin on the project whatever
# happens. There is no state this script cannot recover from.
#
# Takes about 30 seconds.
# =====================================================================

$ErrorActionPreference = 'Stop'

$Service = 'swayam-dashboard'
$Region  = 'asia-southeast1'
$Project = 'swayam-capital'

Write-Host ''
Write-Host '  Swayam Capital - turning Google sign-in OFF' -ForegroundColor Yellow
Write-Host '  ------------------------------------------' -ForegroundColor Yellow
Write-Host ''
Write-Host '  This makes the site public again: anyone with the address'
Write-Host '  will be able to open it. Use it to get back in, then tell'
Write-Host '  Claude so sign-in can be fixed properly.'
Write-Host ''

$answer = Read-Host '  Type YES to continue'
if ($answer -ne 'YES') {
    Write-Host ''
    Write-Host '  Cancelled. Nothing was changed.' -ForegroundColor Green
    Write-Host ''
    exit 0
}

Write-Host ''
Write-Host '  Turning sign-in off...' -ForegroundColor Cyan

# TWO separate commands, deliberately. Run together in one call on
# 2026-09-08, gcloud restored public access but left sign-in switched ON, so
# Abhishek was still locked out by a script whose whole job was to let him in.
# Turning sign-in off is the step that matters, so it goes first and alone.
gcloud run services update $Service `
    --region=$Region `
    --project=$Project `
    --no-iap `
    --quiet

$iapOff = $LASTEXITCODE

gcloud run services add-iam-policy-binding $Service `
    --region=$Region `
    --project=$Project `
    --member=allUsers `
    --role=roles/run.invoker `
    --quiet | Out-Null

if ($iapOff -ne 0) {
    Write-Host ''
    Write-Host '  That did not work. Run this by hand in a terminal:' -ForegroundColor Red
    Write-Host ''
    Write-Host "    gcloud run services update $Service --region=$Region --project=$Project --no-iap" -ForegroundColor White
    Write-Host ''
    exit 1
}

Write-Host ''
Write-Host '  Checking sign-in is really off...' -ForegroundColor Cyan

$ann = gcloud run services describe $Service --region=$Region --project=$Project --format='value(metadata.annotations)' 2>$null
if ($ann -match 'iap-enabled=true') {
    Write-Host ''
    Write-Host '  WARNING: sign-in is STILL on. Run this by hand:' -ForegroundColor Red
    Write-Host ''
    Write-Host "    gcloud run services update $Service --region=$Region --project=$Project --no-iap" -ForegroundColor White
    Write-Host ''
    exit 1
}

Write-Host '  Confirmed off. Checking the site answers...' -ForegroundColor Cyan

try {
    $r = Invoke-WebRequest -Uri 'https://swayam.abhisheksikka.com/api/positions?status=open' `
                           -TimeoutSec 30 -UseBasicParsing
    Write-Host ''
    Write-Host "  The site is answering again (HTTP $($r.StatusCode))." -ForegroundColor Green
} catch {
    Write-Host ''
    Write-Host '  Sign-in is off, but the site did not answer on the first try.' -ForegroundColor Yellow
    Write-Host '  Wait about a minute for the new version to start, then open'
    Write-Host '  https://swayam.abhisheksikka.com in your browser.'
}

Write-Host ''
Write-Host '  Your site is public again. Nothing else was changed.'
Write-Host ''
