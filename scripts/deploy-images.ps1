param(
  [string]$Tag = "",
  [string]$HostAlias = "TX4H4G",
  [string]$DeployPath = "/home/ubuntu/CampusHub",
  [string]$TarPath = "",
  [string]$PublicBaseUrl = "http://124.220.81.104"
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
ssh $HostAlias "mkdir -p '$DeployPath/releases' '$DeployPath/backups' '$DeployPath/scripts/server'"

Write-Host "Uploading release bundle..."
scp $TarPath "${HostAlias}:$remoteTar"

Write-Host "Uploading deployment files..."
scp docker-compose.prod.yml "${HostAlias}:$DeployPath/docker-compose.prod.yml"
scp scripts/server/deploy-release.sh "${HostAlias}:$DeployPath/scripts/server/deploy-release.sh"
scp scripts/server/rollback-release.sh "${HostAlias}:$DeployPath/scripts/server/rollback-release.sh"
scp scripts/server/smoke-test.sh "${HostAlias}:$DeployPath/scripts/server/smoke-test.sh"

Write-Host "Deploying release $Tag..."
ssh $HostAlias "cd '$DeployPath' && sed -i 's/\r$//' scripts/server/*.sh && chmod +x scripts/server/*.sh && scripts/server/deploy-release.sh '$Tag' '$remoteTar' '$PublicBaseUrl'"

Write-Host "Running local smoke test..."
& (Join-Path "scripts" "smoke-test.ps1") -BaseUrl $PublicBaseUrl
