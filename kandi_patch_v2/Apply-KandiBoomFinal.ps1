$ErrorActionPreference = 'Stop'

$RepoRoot = (Get-Location).Path
if (-not (Test-Path (Join-Path $RepoRoot 'tools\mesh_demo_assets\app.js'))) {
    throw 'Run this script from the DanceRudiments repository root.'
}

# Validate the bundle before touching Git state. This deliberately happens
# before branch creation so a damaged/incomplete ZIP cannot leave a stray branch.
$requiredPayload = @(
    'payload\tools\mesh_demo_assets\kandi-boom.js',
    'payload\docs\mesh-demos.md',
    'payload\docs\kandi-boom-integration.md',
    'payload\tests\typescript\kandi-boom.test.js'
)
foreach ($relative in $requiredPayload) {
    $candidate = Join-Path $PSScriptRoot $relative
    if (-not (Test-Path $candidate -PathType Leaf)) {
        throw "Integration bundle is incomplete: missing $relative"
    }
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw 'Python 3 is required to apply this integration bundle.' }

$branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Unable to read the current Git branch.' }
if ($branch -eq 'main') {
    $target = 'kandi-boom-final-integration'
    git show-ref --verify --quiet "refs/heads/$target"
    if ($LASTEXITCODE -eq 0) {
        git switch $target
        if ($LASTEXITCODE -ne 0) { throw "Unable to switch to existing $target." }
        Write-Host "Switched to existing branch $target"
    } else {
        git switch -c $target
        if ($LASTEXITCODE -ne 0) { throw "Unable to create $target." }
        Write-Host "Created branch $target"
    }
} elseif ($branch -ne 'kandi-boom-final-integration') {
    Write-Host "Applying on current branch '$branch' (not creating another branch)."
}

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
