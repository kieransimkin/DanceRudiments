# Repair the optional-NumPy test gate and documentation at current DanceRudiments main.
# No release, push, tag or force operation is performed.
param(
    [switch]$CheckOnly,
    [switch]$RunTests
)
$ErrorActionPreference = 'Stop'

$root = (& git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $root) {
    throw 'Run this from within the DanceRudiments Git checkout.'
}
$root = ($root | Select-Object -First 1).Trim()
Push-Location $root
try {
    $testPath = Join-Path $root 'tests/python/test_source_loop_analysis.py'
    $readmePath = Join-Path $root 'README.md'
    if (-not (Test-Path -LiteralPath $testPath) -or -not (Test-Path -LiteralPath $readmePath)) {
        throw 'Missing expected DanceRudiments source files.'
    }

    $test = [System.IO.File]::ReadAllText($testPath)
    $oldGate = "@unittest\.skipUnless\(importlib\.util\.find_spec\('numpy'\) is not None or\r?\n[ \t]+os\.environ\.get\('DANCERUDIMENTS_REQUIRE_NATIVE'\) == '1',"
    $newGate = "@unittest.skipUnless(importlib.util.find_spec('numpy') is not None,"
    $gateCount = [regex]::Matches($test, $oldGate).Count
    if ($gateCount -gt 1) { throw 'Multiple optional NumPy test guards matched; refusing to edit.' }
    if ($gateCount -eq 0 -and -not $test.Contains($newGate)) {
        throw 'The NumPy guard does not match the reviewed source; refusing to overwrite it.'
    }
    $correctedTest = if ($gateCount -eq 1) { [regex]::Replace($test, $oldGate, $newGate) } else { $test }

    $readme = [System.IO.File]::ReadAllText($readmePath)
    $sectionHeading = '### Playback-rate interpretations for rigged motion'
    $anchor = 'The gallery also supports **local StemLab rhythm-analysis review**.'
    $eol = if ($readme.Contains("`r`n")) { "`r`n" } else { "`n" }
    if (-not $readme.Contains($sectionHeading)) {
        if (-not $readme.Contains($anchor)) {
            throw 'The README insertion anchor is missing; refusing to change the documentation.'
        }
        $section = @(
            $sectionHeading,
            '',
            'The Kandi Boom gallery offers **half time (0.5×)**, **original time (1×)**',
            'and **double time (2×)** in addition to the 0.75× and 1.5× preview',
            'rates. The TypeScript `motionTimeRate` and `motionSourcePipAtTime`',
            'helpers convert elapsed presentation time to an original source pip.',
            'The motion stays on the native 64-pip source clock, with no implicit',
            'audio synchronisation, source-BPM correction, wrapping or resampling.',
            '',
            ''
        ) -join $eol
        $readme = $readme.Replace($anchor, $section + $anchor)
    }

    $temporaryPatch = 'dancerudiments_half_double_motion_rebased.patch'
    $tracked = @(& git ls-files -- $temporaryPatch)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to check Git tracked files.' }
    if ($tracked.Count -gt 0) {
        & git diff --quiet -- $temporaryPatch
        if ($LASTEXITCODE -ne 0) { throw 'The tracked hand-off patch has local changes; preserving it.' }
    }
    Write-Host "NumPy test guard correction: $(if ($gateCount) { 'needed' } else { 'already present' })"
    Write-Host "Root README update: $(if ($readme -ne [System.IO.File]::ReadAllText($readmePath)) { 'needed' } else { 'already present' })"
    Write-Host "Tracked temporary patch cleanup: $(if ($tracked.Count) { 'needed' } else { 'not needed' })"
    if ($CheckOnly) { Write-Host 'Check-only mode; nothing modified.'; return }

    if ($correctedTest -ne $test) {
        [System.IO.File]::WriteAllText($testPath, $correctedTest, [System.Text.UTF8Encoding]::new($false))
    }
    $currentReadme = [System.IO.File]::ReadAllText($readmePath)
    if ($readme -ne $currentReadme) {
        [System.IO.File]::WriteAllText($readmePath, $readme, [System.Text.UTF8Encoding]::new($false))
    }
    if ($tracked.Count -gt 0) { & git rm -- $temporaryPatch; if ($LASTEXITCODE -ne 0) { throw 'Could not remove tracked temporary patch.' } }

    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'Git diff whitespace validation failed.' }
    Write-Host 'Changes prepared. Review with git diff and git status before committing.'
    if ($RunTests) {
        & python -m unittest discover -s tests/python -p test_source_loop_analysis.py -v
        if ($LASTEXITCODE -ne 0) { throw 'Source-first motion unit tests failed.' }
        & node --test tests/typescript/motion-time.test.js
        if ($LASTEXITCODE -ne 0) { throw 'Playback timing tests failed.' }
    }
} finally {
    Pop-Location
}
