param(
  [Parameter(Mandatory = $true)]
  [string]$Workflow,
  [string]$Branch = "",
  [int]$DelaySeconds = 8
)

$ErrorActionPreference = "Stop"

function Assert-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Command not found: $Name"
  }
}

Assert-Command gh
Assert-Command git

if (-not $Branch) {
  $Branch = (git branch --show-current).Trim()
}

if (-not $Branch) {
  throw "Cannot determine current Git branch. Pass -Branch explicitly."
}

Write-Host "Waiting $DelaySeconds seconds for GitHub Actions to create the run..."
Start-Sleep -Seconds $DelaySeconds

$runsJson = gh run list `
  --workflow $Workflow `
  --branch $Branch `
  --limit 1 `
  --json databaseId,status,conclusion,displayTitle,headBranch,createdAt,url

$runs = @($runsJson | ConvertFrom-Json)
if ($runs.Count -eq 0) {
  throw "No workflow run found. workflow=$Workflow branch=$Branch"
}

$run = $runs[0]

Write-Host ""
Write-Host "Watching workflow run:"
Write-Host "  workflow : $Workflow"
Write-Host "  branch   : $($run.headBranch)"
Write-Host "  title    : $($run.displayTitle)"
Write-Host "  status   : $($run.status)"
Write-Host "  url      : $($run.url)"
Write-Host ""

gh run watch $run.databaseId --exit-status
if ($LASTEXITCODE -ne 0) {
  throw "Workflow failed. workflow=$Workflow run=$($run.databaseId)"
}
