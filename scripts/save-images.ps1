param(
  [string]$Tag = "",
  [string]$OutputDir = "artifacts"
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
  "campushub-agent:$Tag",
  "campushub-backend:$Tag",
  "campushub-web:$Tag"
)

foreach ($image in $images) {
  docker image inspect $image | Out-Null
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$tarPath = Join-Path $OutputDir "campushub-images-$Tag.tar"

Write-Host "Saving images to $tarPath"
docker save -o $tarPath @images

$item = Get-Item $tarPath
Write-Host "Saved $($item.FullName) ($([math]::Round($item.Length / 1MB, 2)) MB)"
