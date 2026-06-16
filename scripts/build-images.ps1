param(
  [string]$Tag = "",
  [switch]$AlsoLatest
)

$ErrorActionPreference = "Stop"

function Get-DefaultTag {
  $tag = (git rev-parse --short HEAD).Trim()
  if (-not $tag) {
    throw "Cannot determine Git commit tag."
  }
  return $tag
}

if (-not $Tag) {
  $Tag = Get-DefaultTag
}

$images = @(
  @{ Name = "campushub-agent"; Context = "CampusHubAgent" },
  @{ Name = "campushub-backend"; Context = "CampusHubBackend" },
  @{ Name = "campushub-web"; Context = "CampusHubWeb" }
)

Write-Host "Building CampusHub images with tag: $Tag"

foreach ($image in $images) {
  $args = @("build", "-t", "$($image.Name):$Tag")
  if ($AlsoLatest) {
    $args += @("-t", "$($image.Name):latest")
  }
  $args += $image.Context

  Write-Host ""
  Write-Host "docker $($args -join ' ')"
  docker @args
}

Write-Host ""
Write-Host "Built images:"
foreach ($repo in @("campushub-agent", "campushub-backend", "campushub-web")) {
  docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" $repo
}
