DanceRudiments: README-safe source-loop CI fix
===============================================

Use this bundle if the earlier patch fails at README.md:95. That README hunk
only added optional CI documentation; it is NOT required for the actual fixes.
This patch deliberately does not modify README.md.

From the DanceRudiments checkout in PowerShell (after extracting this ZIP there):

  .\Apply-DanceRudiments-SourceLoopCI-NoREADME.ps1 -Repository . -VerifyOnly
  .\Apply-DanceRudiments-SourceLoopCI-NoREADME.ps1 -Repository .

Or manually, from the checkout containing the .patch file:

  git apply --check --ignore-space-change .\DanceRudiments-source-loop-ci-fixes-no-readme.patch
  git apply --ignore-space-change .\DanceRudiments-source-loop-ci-fixes-no-readme.patch
  git -c core.whitespace=cr-at-eol diff --check

Avoid 'git add .' if you extracted the patch into the repository, since that
would include patch/installer artifacts. Stage these exact four paths instead:

  git add .github/workflows/source-motion-loops.yml docs/source-loop-analysis.md python/dancerudiments_authoring/source_loop_analysis.py tests/python/test_source_loop_analysis.py
  git commit -m "Fix source-first motion analysis CI"
  git push

Changes (based on the original patch, excluding only README.md):
- Install lightweight soundfile runtime requirement for StemLab's current import graph.
- Require a genuine pinned StemLab rig analyser to load in the dedicated CI job.
- Make that integration test fail instead of silently skip in required jobs.
- Skip NumPy-dependent BVH test only in lightweight suites lacking NumPy.
- Use a richer synthetic BVH with tempo/loop evidence; require actual previews.
- Validate loop beat map provenance and seam diagnostics before compiling previews.
- Upload source-analysis CI evidence on success and failure.
- Update docs/source-loop-analysis.md and workflow file triggers.

This archive intentionally does not overwrite README.md, local assets or any other
unrelated file. It does not modify Git config or reset local changes.
If --check fails on another file, stop and inspect 'git status --short'.
