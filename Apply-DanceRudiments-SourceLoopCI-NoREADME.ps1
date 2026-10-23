param(
    [string]$Repository = ".",
    [switch]$VerifyOnly,
    [switch]$RunUnitTests
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $Repository -ErrorAction Stop).Path
$patch = Join-Path $PSScriptRoot 'DanceRudiments-source-loop-ci-fixes-no-readme.patch'
if (-not (Test-Path -LiteralPath $patch -PathType Leaf)) {
    throw "Required patch is missing: $patch"
}

& git -C $repo rev-parse --show-toplevel | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Not a Git repository: $repo" }

Write-Host "Checking README-safe patch for $repo..."
& git -C $repo apply --check --ignore-space-change $patch
if ($LASTEXITCODE -ne 0) {
    & git -C $repo apply --reverse --check --ignore-space-change $patch 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "The patch is already applied; nothing has been changed."
        exit 0
    }
    throw "A source/workflow/test file differs from the expected commit. Nothing was applied. Check 'git status --short' and do not force the patch."
}
if ($VerifyOnly) {
    Write-Host "Patch check succeeded. No files changed. README.md will not be modified."
    exit 0
}

& git -C $repo apply --ignore-space-change $patch
if ($LASTEXITCODE -ne 0) { throw "git apply failed" }
& git -C $repo -c core.whitespace=cr-at-eol diff --check
if ($LASTEXITCODE -ne 0) { throw "Whitespace validation failed after application" }
Write-Host "Applied: workflow, rig-analysis code, regression tests, and source-analysis guide. README.md untouched."

if ($RunUnitTests) {
    Push-Location $repo
    try {
        & python -m unittest discover -s tests/python -p 'test_source_loop_analysis.py' -v
        if ($LASTEXITCODE -ne 0) { throw "Focused source-first tests failed" }
    }
    finally { Pop-Location }
}
Write-Host "Review: git diff --stat"
Write-Host "Commit only the four modified source files; do not commit this installer or patch archive."
