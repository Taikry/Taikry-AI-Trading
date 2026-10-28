param (
    [string]$symbol = "XAUUSD",
    [string]$timeframe = "M5",
    [string]$action = "analyze",
    [string]$test = "true"
)

$url = "https://hook.us2.make.com/uu21klu4rg3s2l7u2644xi9toeburwhd"

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
