param(
  [string]$PublicBaseUrl = "http://124.220.81.104",
  [string]$Ref = "main",
  [string]$ReleaseTag = "",
  [switch]$UseExistingBundle,
  [switch]$NoWatch
)

$ErrorActionPreference = "Stop"

function Assert-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Command not found: $Name"
  }
}

Assert-Command gh

$args = @(
  "workflow", "run", "deploy.yml",
  "--ref", $Ref,
  "-f", "public_base_url=$PublicBaseUrl",
  "-f", "use_existing_bundle=$($UseExistingBundle.IsPresent.ToString().ToLower())"
)

if ($ReleaseTag) {
  $args += @("-f", "release_tag=$ReleaseTag")
}

Write-Host "Triggering Deploy workflow..."
Write-Host "  ref             : $Ref"
Write-Host "  public_base_url : $PublicBaseUrl"
if ($ReleaseTag) {
  Write-Host "  release_tag     : $ReleaseTag"
} else {
  Write-Host "  release_tag     : short Git SHA from GitHub Actions"
}
Write-Host "  existing bundle : $($UseExistingBundle.IsPresent)"
Write-Host ""

gh @args
if ($LASTEXITCODE -ne 0) {
  throw "Failed to trigger Deploy workflow."
}

if (-not $NoWatch) {
  & (Join-Path $PSScriptRoot "watch-workflow.ps1") -Workflow "deploy.yml" -Branch $Ref
}
