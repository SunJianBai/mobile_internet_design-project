param(
  [string]$BaseUrl = "https://sun227454.online/CampusHub",
  [int]$Retries = 10,
  [int]$DelaySeconds = 5
)

$ErrorActionPreference = "Stop"

$base = $BaseUrl.TrimEnd("/")
$apiUrl = "$base/api/v1/orders?page=1&size=1"

function Invoke-WithRetry {
  param(
    [string]$Name,
    [scriptblock]$Action
  )

  for ($attempt = 1; $attempt -le $Retries; $attempt++) {
    try {
      Write-Host "Checking $Name (attempt $attempt/$Retries)"
      return & $Action
    } catch {
      if ($attempt -eq $Retries) {
        throw
      }
      Write-Host "Check failed, retrying in $DelaySeconds seconds..."
      Start-Sleep -Seconds $DelaySeconds
    }
  }
}

Invoke-WithRetry "$base/" {
  $homeResponse = Invoke-WebRequest -Uri "$base/" -UseBasicParsing -TimeoutSec 15
  if ($homeResponse.StatusCode -lt 200 -or $homeResponse.StatusCode -ge 400) {
    throw "Home page returned HTTP $($homeResponse.StatusCode)"
  }
}

Invoke-WithRetry $apiUrl {
  $api = Invoke-RestMethod -Uri $apiUrl -TimeoutSec 15
  if ($api.code -ne 200) {
    throw "API smoke test failed. code=$($api.code), message=$($api.message)"
  }
}

Write-Host "Smoke test passed: $base"
