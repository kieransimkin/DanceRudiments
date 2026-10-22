$ErrorActionPreference = 'Stop'

$RepoRoot = (Get-Location).Path
if (-not (Test-Path (Join-Path $RepoRoot 'tools\mesh_demo_assets\app.js'))) {
    throw 'Run this script from the DanceRudiments repository root.'
}

$branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to read the current Git branch.' }
if ($branch -eq 'main') {
    $target = 'kandi-boom-final-integration'
    git show-ref --verify --quiet "refs/heads/$target"
    if ($LASTEXITCODE -eq 0) {
        throw "Local branch $target already exists. Switch to it or remove/rename it before retrying."
    }
    git switch -c $target
    if ($LASTEXITCODE -ne 0) { throw "Unable to create $target." }
    Write-Host "Created branch $target"
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required to apply this integration bundle.' }

& $python.Source (Join-Path $PSScriptRoot 'apply_kandi_boom_final.py')
if ($LASTEXITCODE -ne 0) { throw 'Kandi Boom integration patch failed.' }

Write-Host ''
Write-Host 'Integration applied. Suggested verification:'
Write-Host '  npm ci'
Write-Host '  npm test'
Write-Host '  python -m unittest discover -s tests/python -p test_kandi_boom_*.py -v'
Write-Host '  python -m unittest discover -s tests/python -p test_mesh_demo_assets.py -v'
Write-Host '  python -m unittest discover -s tests/python -p test_release_pages.py -v'
Write-Host '  git diff --check'
Write-Host '  git status --short'
