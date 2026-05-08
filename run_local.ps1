param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

if (-not $SkipInstall) {
    Write-Host "[1/3] Installing dependencies..."
    python -m pip install -r requirements.txt
}

Write-Host "[2/3] Checking environment variables..."
if (-not $env:LINE_CHANNEL_ACCESS_TOKEN) {
    $token = Read-Host "Enter LINE_CHANNEL_ACCESS_TOKEN"
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw "LINE_CHANNEL_ACCESS_TOKEN is required."
    }
    $env:LINE_CHANNEL_ACCESS_TOKEN = $token
}

if (-not $env:LINE_TO) {
    $lineTo = Read-Host "Enter LINE_TO (userId/groupId/roomId)"
    if ([string]::IsNullOrWhiteSpace($lineTo)) {
        throw "LINE_TO is required."
    }
    $env:LINE_TO = $lineTo
}

Write-Host "[3/3] Running notifier..."
python src/main.py
