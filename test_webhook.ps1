param (
    [string]$symbol = "XAUUSD",
    [string]$timeframe = "M5",
    [string]$action = "analyze",
    [string]$test = "true"
)

$url = $env:MAKE_WEBHOOK_URL
if (-not $url) {
    Write-Host "[ERROR] MAKE_WEBHOOK_URL environment variable is required." -ForegroundColor Red
    exit 1
}

$payload = @{
    symbol    = $symbol
    timeframe = $timeframe
    action    = $action
    test      = $test
    chat_id   = "-1004341134868"
} | ConvertTo-Json

Write-Host "Sending webhook POST to $url..." -ForegroundColor Cyan
Write-Host "Payload: $payload" -ForegroundColor Gray

try {
    $response = Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Body $payload
    Write-Host "Response ($response)" -ForegroundColor Green
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
}
