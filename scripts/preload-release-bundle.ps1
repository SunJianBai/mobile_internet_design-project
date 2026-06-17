param(
  [string]$Tag = "",
  [string]$HostAlias = "TX4H4G",
  [string]$DeployPath = "/home/ubuntu/CampusHub",
  [string]$TarPath = ""
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

if (-not $TarPath) {
  $TarPath = Join-Path "artifacts" "campushub-images-$Tag.tar"
}

if (-not (Test-Path $TarPath)) {
  throw "Image bundle not found: $TarPath. Run scripts/build-images.ps1 and scripts/save-images.ps1 first."
}

$remoteReleaseDir = "$DeployPath/releases"
$remoteTar = "$remoteReleaseDir/$(Split-Path $TarPath -Leaf)"

Write-Host "Preparing remote deploy directories..."
ssh $HostAlias "mkdir -p '$DeployPath/releases' '$DeployPath/scripts/server'"

Write-Host "Uploading preloaded release bundle..."
scp $TarPath "${HostAlias}:$remoteTar"

Write-Host "Uploading deployment files..."
scp docker-compose.prod.yml "${HostAlias}:$DeployPath/docker-compose.prod.yml"
scp scripts/server/deploy-release.sh "${HostAlias}:$DeployPath/scripts/server/deploy-release.sh"
scp scripts/server/rollback-release.sh "${HostAlias}:$DeployPath/scripts/server/rollback-release.sh"
scp scripts/server/smoke-test.sh "${HostAlias}:$DeployPath/scripts/server/smoke-test.sh"

Write-Host "Normalizing remote server script line endings..."
ssh $HostAlias "cd '$DeployPath' && sed -i 's/\r$//' scripts/server/*.sh && chmod +x scripts/server/*.sh"

Write-Host ""
Write-Host "Preloaded bundle ready:"
Write-Host "  tag    : $Tag"
Write-Host "  bundle : $remoteTar"
Write-Host ""
Write-Host "Trigger GitHub Actions deploy with:"
Write-Host "  .\scripts\run-deploy-workflow.ps1 -ReleaseTag $Tag -UseExistingBundle"
