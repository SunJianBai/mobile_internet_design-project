param(
  [string]$CommitMessage = "Demo CI/CD flow",
  [string[]]$Pathspec = @("CampusHubApp"),
  [string]$Branch = "",
  [switch]$SkipLocalBuild,
  [switch]$SkipCommit,
  [switch]$SkipPush,
  [switch]$CreatePr,
  [string]$PrTitle = "Demo CI/CD branch workflow",
  [string]$PrBody = "Demo PR for CI/CD recording.",
  [switch]$Deploy,
  [string]$PublicBaseUrl = "https://sun227454.online/CampusHub"
)

$ErrorActionPreference = "Stop"

function Assert-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Command not found: $Name"
  }
}

Assert-Command git
Assert-Command gh

if (-not $Branch) {
  $Branch = (git branch --show-current).Trim()
}

if (-not $Branch) {
  throw "Cannot determine current Git branch. Pass -Branch explicitly."
}

Write-Host "CampusHub CI/CD demo"
Write-Host "  branch   : $Branch"
Write-Host "  pathspec : $($Pathspec -join ', ')"
Write-Host ""

if (-not $SkipLocalBuild) {
  Write-Host "Step 1/5: Build CampusHubApp H5 locally"
  Push-Location (Join-Path (Get-Location) "CampusHubApp")
  try {
    $env:UNI_INPUT_DIR = "."
    npm.cmd run build:h5
  } finally {
    Pop-Location
  }
  Write-Host ""
}

if (-not $SkipCommit) {
  Write-Host "Step 2/5: Stage and commit demo changes"
  $gitAddArgs = @("add", "--") + $Pathspec
  git @gitAddArgs

  $stagedFiles = @(git diff --cached --name-only)
  if ($stagedFiles.Count -eq 0) {
    Write-Host "No staged changes. Skipping commit."
  } else {
    Write-Host "Staged files:"
    $stagedFiles | ForEach-Object { Write-Host "  $_" }
    git commit -m $CommitMessage
  }
  Write-Host ""
}

if (-not $SkipPush) {
  Write-Host "Step 3/5: Push branch to GitHub"
  git push -u origin $Branch
  Write-Host ""
}

if ($CreatePr) {
  Write-Host "Step 4/5: Create or reuse pull request"
  $existingPrUrl = gh pr list --head $Branch --base main --json url --jq ".[0].url"
  if ($existingPrUrl) {
    Write-Host "Existing PR: $existingPrUrl"
  } else {
    gh pr create --base main --head $Branch --title $PrTitle --body $PrBody
  }
  Write-Host ""
}

Write-Host "Step 5/5: Watch CI workflow"
& (Join-Path $PSScriptRoot "watch-workflow.ps1") -Workflow "ci.yml" -Branch $Branch

if ($Deploy) {
  if ($Branch -ne "main") {
    throw "Deploy workflow only runs on main. Merge the PR first, then rerun this script on main with -Deploy."
  }

  Write-Host ""
  Write-Host "Triggering production deploy after CI passed..."
  & (Join-Path $PSScriptRoot "run-deploy-workflow.ps1") -PublicBaseUrl $PublicBaseUrl -Ref "main"

  Write-Host ""
  Write-Host "Running smoke test..."
  & (Join-Path $PSScriptRoot "smoke-test.ps1") -BaseUrl $PublicBaseUrl
}
