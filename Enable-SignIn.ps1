# =====================================================================
# Enable-SignIn.ps1
#
# Turns on Google sign-in for swayam.abhisheksikka.com.
#
# WHY THIS SCRIPT EXISTS
# Sign-in failed on 2026-09-08 with IAP error 11, an incorrectly configured
# OAuth client. This project has no Google Workspace organisation, so Google's
# own built-in client does not apply and a custom one has to be created by
# hand. The API that used to create it was shut down in March 2026, so the
# console is the only way.
#
# You create the client in the browser. This script does the rest.
#
# YOUR CLIENT SECRET NEVER LEAVES YOUR MACHINE. It is typed here, written to
# a temporary file, sent straight to Google, and the file is deleted. It is
# never printed, never logged, and never sent to Claude.
#
# COST: nothing. Identity-Aware Proxy is free for a Cloud Run app, and the
# load-balancer charge people mention does not apply because this uses the
# direct Cloud Run method with no load balancer. The roughly 2 rupees a day
# you saw was Gemini usage for the AI, which is unrelated.
#
# IF ANYTHING GOES WRONG: double-click Undo-SignIn.ps1. It puts the site back.
# =====================================================================

$ErrorActionPreference = 'Stop'

$Project = 'swayam-capital'
$Region  = 'asia-southeast1'
$Service = 'swayam-dashboard'
$Account = 'abhisheksikka99.99@gmail.com'

Write-Host ''
Write-Host '  Swayam Capital - turning Google sign-in ON' -ForegroundColor Cyan
Write-Host '  -----------------------------------------' -ForegroundColor Cyan
Write-Host ''
Write-Host '  BEFORE you run this, do these three things in the browser:' -ForegroundColor Yellow
Write-Host ''
Write-Host '   1. Open  https://console.cloud.google.com/apis/credentials?project=swayam-capital'
Write-Host '   2. Create Credentials  ->  OAuth client ID  ->  Application type: Web application'
Write-Host '      Name it anything, for example "Swayam sign-in". Click Create.'
Write-Host '   3. Copy the Client ID. Then click the client to edit it, and under'
Write-Host '      "Authorized redirect URIs" click ADD URI and paste EXACTLY this,'
Write-Host '      with your own client ID in the middle:'
Write-Host ''
Write-Host '      https://iap.googleapis.com/v1/oauth/clientIds/YOUR_CLIENT_ID:handleRedirect' -ForegroundColor White
Write-Host ''
Write-Host '      Click Save. Keep the Client ID and Client secret on screen.'
Write-Host ''
Write-Host '  If it asks you to configure the OAuth consent screen first, choose'
Write-Host '  External, put your own email in every box, and add your own email'
Write-Host '  as a test user.'
Write-Host ''

$go = Read-Host '  Done all three? Type YES to continue'
if ($go -ne 'YES') {
    Write-Host ''
    Write-Host '  Cancelled. Nothing was changed.' -ForegroundColor Green
    Write-Host ''
    exit 0
}

Write-Host ''
$clientId = Read-Host '  Paste the Client ID'
if ([string]::IsNullOrWhiteSpace($clientId)) {
    Write-Host '  No client ID given. Nothing was changed.' -ForegroundColor Red
    exit 1
}
$clientId = $clientId.Trim()

$secure = Read-Host '  Paste the Client secret (hidden)' -AsSecureString
$bstr   = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$secret = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr).Trim()
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

if ([string]::IsNullOrWhiteSpace($secret)) {
    Write-Host '  No secret given. Nothing was changed.' -ForegroundColor Red
    exit 1
}

# Sanity check: the redirect URI must contain THIS client id, or sign-in
# fails with error 11 again and you will not know why.
Write-Host ''
Write-Host '  Check the redirect URI you saved reads exactly:' -ForegroundColor Yellow
Write-Host "    https://iap.googleapis.com/v1/oauth/clientIds/$clientId`:handleRedirect" -ForegroundColor White
Write-Host ''
$ok = Read-Host '  Does it match? Type YES'
if ($ok -ne 'YES') {
    Write-Host ''
    Write-Host '  Fix the redirect URI first, then run this again.' -ForegroundColor Red
    Write-Host '  Nothing was changed.' -ForegroundColor Green
    exit 1
}

$tmp = Join-Path $env:TEMP ("iap-oauth-{0}.yaml" -f ([guid]::NewGuid().ToString('N')))
try {
    @"
accessSettings:
  oauthSettings:
    clientId: $clientId
    clientSecret: $secret
"@ | Out-File -FilePath $tmp -Encoding utf8 -NoNewline

    Write-Host ''
    Write-Host '  Telling Google to use your client...' -ForegroundColor Cyan

    gcloud iap settings set $tmp `
        --project=$Project `
        --resource-type=cloud-run `
        --region=$Region `
        --service=$Service `
        --quiet

    if ($LASTEXITCODE -ne 0) {
        Write-Host ''
        Write-Host '  That failed. Nothing about your site changed.' -ForegroundColor Red
        Write-Host '  The most common cause is a redirect URI that does not match.' -ForegroundColor Yellow
        exit 1
    }
}
finally {
    # The secret was on disk for a few seconds. Remove it either way.
    if (Test-Path $tmp) { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
    $secret = $null
}

Write-Host '  Making sure your account is allowed in...' -ForegroundColor Cyan
gcloud projects add-iam-policy-binding $Project `
    --member="user:$Account" `
    --role='roles/iap.httpsResourceAccessor' `
    --condition=None --quiet | Out-Null

Write-Host '  Turning sign-in on...' -ForegroundColor Cyan
gcloud run services update $Service --region=$Region --project=$Project --iap --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host '  Could not turn sign-in on. Run Undo-SignIn.ps1 to be safe.' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host '  Now OPEN https://swayam.abhisheksikka.com IN A NEW WINDOW' -ForegroundColor Yellow
Write-Host '  and sign in with your Google account.' -ForegroundColor Yellow
Write-Host ''
Write-Host '  DO NOT close this window until you are inside.' -ForegroundColor Yellow
Write-Host ''
$inside = Read-Host '  Did you get in? Type YES, or NO to undo everything'

if ($inside -ne 'YES') {
    Write-Host ''
    Write-Host '  Undoing. Your site will be public again in a moment.' -ForegroundColor Yellow
    gcloud run services update $Service --region=$Region --project=$Project --no-iap --quiet
    gcloud run services add-iam-policy-binding $Service --region=$Region --project=$Project `
        --member=allUsers --role=roles/run.invoker --quiet | Out-Null
    Write-Host '  Done. Tell Claude the error you saw on screen.' -ForegroundColor Green
    exit 0
}

# Only now, once he is provably inside, do we close the door behind him.
Write-Host ''
Write-Host '  Good. Closing the door to everyone else...' -ForegroundColor Cyan
gcloud run services remove-iam-policy-binding $Service --region=$Region --project=$Project `
    --member=allUsers --role=roles/run.invoker --quiet 2>$null | Out-Null

Write-Host ''
Write-Host '  Sign-in is on. Your terminal is now private to your Google account.' -ForegroundColor Green
Write-Host '  Undo-SignIn.ps1 turns it off again at any time.' -ForegroundColor Green
Write-Host ''
Write-Host '  One leftover: the AI compaction job is paused, because under sign-in'
Write-Host '  it needs different credentials. Tell Claude to fix it when convenient.'
Write-Host ''
