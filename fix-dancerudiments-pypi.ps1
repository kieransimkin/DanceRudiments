# Run in DanceRudiments repository root. Safe to rerun; does not change the existing tag.
$ErrorActionPreference = 'Stop'
if (-not (Test-Path './pyproject.toml') -or -not (Test-Path './CMakeLists.txt')) {
    throw 'Run this script from the DanceRudiments repository root.'
}
function Replace-Once([string]$content, [string]$old, [string]$new, [string]$description) {
    if ($content.Contains($new)) { Write-Host "Already applied: $description"; return $content }
    if (-not $content.Contains($old)) { throw "Expected text not found ($description). No files have been written." }
    return $content.Replace($old, $new)
}
$py = [IO.File]::ReadAllText((Resolve-Path './pyproject.toml'))
$cm = [IO.File]::ReadAllText((Resolve-Path './CMakeLists.txt'))
$pyNew = Replace-Once $py '"-DDANCERUDIMENTS_BUILD_TESTS=OFF"]' '"-DDANCERUDIMENTS_BUILD_TESTS=OFF", "-DDANCERUDIMENTS_INSTALL_RIG_MOTION_EXAMPLES=OFF"]' 'disable bulky CMake examples in Python builds'
$pyNew = Replace-Once $pyNew '"examples/rig-motion/**", ' '' 'exclude rig examples from sdist include'
$pyNew = Replace-Once $pyNew 'sdist.exclude = [' 'sdist.exclude = ["examples/rig-motion/**", ' 'explicitly exclude rig examples from sdist'
$cmNew = Replace-Once $cm 'option(DANCERUDIMENTS_BUILD_DEMO_TOOLS' 'option(DANCERUDIMENTS_INSTALL_RIG_MOTION_EXAMPLES "Install large optional rig-motion demo assets" ON)`noption(DANCERUDIMENTS_BUILD_DEMO_TOOLS' 'define optional CMake examples flag'
# Correct escaped PS literal newline only for newly added flag
$cmNew = $cmNew.Replace('ON)`noption(DANCERUDIMENTS_BUILD_DEMO_TOOLS', "ON)" + "`n" + 'option(DANCERUDIMENTS_BUILD_DEMO_TOOLS')
$pattern='(?m)^install\(DIRECTORY examples/rig-motion/ DESTINATION "\$\{DANCERUDIMENTS_DOC_DIR\}/examples/rig-motion"\r?\n  PATTERN "__pycache__" EXCLUDE\)'
if ($cmNew -notmatch 'if\(DANCERUDIMENTS_INSTALL_RIG_MOTION_EXAMPLES\)') {
    if (-not [regex]::IsMatch($cmNew,$pattern)) { throw 'Expected CMake rig-motion install block missing. No files have been written.' }
    $cmNew=[regex]::Replace($cmNew,$pattern, 'if(DANCERUDIMENTS_INSTALL_RIG_MOTION_EXAMPLES)' + "`n" + '  install(DIRECTORY examples/rig-motion/ DESTINATION "${DANCERUDIMENTS_DOC_DIR}/examples/rig-motion"' + "`n" + '    PATTERN "__pycache__" EXCLUDE)' + "`n" + 'endif()',1)
}
[IO.File]::WriteAllText((Resolve-Path './pyproject.toml'), $pyNew, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText((Resolve-Path './CMakeLists.txt'), $cmNew, [Text.UTF8Encoding]::new($false))
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }
git diff --stat
Write-Host 'Changes applied. Review git diff before committing.'
