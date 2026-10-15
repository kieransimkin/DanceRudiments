# Coordinated released-viewer workflow

## Checkout layout and command

Use three sibling Git checkouts, with these exact project names:

```text
Projects/
  DanceRudiments/
  react-timeline-sequence/
  stemlab/
```

Run the canonical coordinator from the **Projects** directory:

```powershell
.\stemlab\scripts\Release-DanceFlow.ps1 -ProjectsRoot .
.\stemlab\scripts\Release-DanceFlow.ps1 -ProjectsRoot . -Execute
```

The first command is a preview. It performs read-only prerequisite, repository,
release and tag checks, and creates no commit, release, tag or state file. The
second explicitly authorizes the displayed release sequence: scoped commits,
normal pushes to main, and new version tags. For the initial migration kit use
`.\release-kit\Release-DanceFlow.ps1` instead; keep its Python coordinator and
three `patches/` files beside it. That kit applies the matching repository patches
before preparing each release. Do not manually apply the same patches first.

Requirements: PowerShell 5.1 or later, **Node.js 24** with npm, **Python 3.11 or
later** available as `python`, Git and GitHub CLI (`gh auth login`). All checkouts
must have the expected official origin, be clean, and be on main. Use normal Git
credentials with permission to push the intended commits/tags; workflow-file
changes may require additional token permission. The script refuses unrelated
local work and does not stash, discard, reset, force-push or bypass branch rules.
With protected main, merge the changes through the repository's required review
process rather than disabling protection to make this command succeed.

## Release order and version selection

The order is **react-timeline-sequence → DanceRudiments → StemLab**. Each companion
is published and verified before StemLab tries to consume it. By default the
script proposes the next minor version after the higher of that repository's
source version and latest stable GitHub release. Review the preview; explicit
`-TimelineVersion`, `-DanceRudimentsVersion` and `-StemLabVersion` overrides accept
fresh MAJOR.MINOR.PATCH versions. Prereleases, existing local/remote tags and
attempts to reuse published versions are rejected.

For each repository the coordinator prepares a version commit, pushes main,
waits for the required workflows for **that exact commit**, and only then pushes
a new annotated `vX.Y.Z` tag. It polls at 15-second intervals, with a configurable
`-TimeoutMinutes` (default 420) for each workflow wait. Cancelled, skipped-required,
missing and failed workflows are not success. It reports failed workflow URLs
and stops before releasing downstream code.

The tag push is the release trigger. The repository's existing GitHub Actions
workflows build and publish packages using its configured credentials or trusted
publishing; the terminal does not run `npm publish`, upload wheels, or create a
second GitHub release. A tag or GitHub release alone does not establish registry
availability. Package/index propagation is checked before proceeding.

## Latest stable releases, with an auditable build snapshot

**StemLab always targets the latest stable official viewer releases.** Neither a
sibling checkout, an unreleased main commit, a local `file:`/vendor tarball nor an
arbitrary Actions-variable override is an acceptable production dependency.

`python scripts/configure_viewer_build.py` in StemLab resolves both official
GitHub `releases/latest` records, resolves each tag to its immutable commit and
requires corresponding public npm/PyPI versions to agree. It installs the
published `react-timeline-sequence` version from npm, rebuilds the real Vite web
bundle, runs the channel-grouping tests, and records the versions, commits and
registry integrity values in `.github/viewer-releases.json`. The matching build
receipt is `.github/viewer-build.json`. The existing
`.github/dancerudiments-recording-ref` is now derived from the selected **release**
commit; it is not a development-revision selector.

Concrete versions and registry integrity stay in `package-lock.json`. This is a
snapshot of **the latest release at synchronization**, not permission to remain
on an older release. A mutable `latest` alias on every dependency install would
let different jobs in one build use different bytes. Instead, CI checks latest
release freshness before expensive processing, fails clearly on a stale or
incomplete release, and then uses the same immutable snapshot throughout that
build. An old tag rerun after a newer companion release can therefore fail the
freshness gate; prepare a fresh StemLab release instead of moving an old tag.

The native recording package is installed from a published binary wheel for the
selected release and SHA-256 checked against its recorded PyPI metadata. There
is no source-build fallback when a wheel is unavailable. Source checkout of that
same release commit is retained only for companion regression scripts and
licensing. Base StemLab installation still does not require DanceRudiments; its
optional `rudiments` extra has the synchronized release as its minimum, and fresh
pip resolution can select newer stable versions. Existing installed environments
do not silently self-upgrade during application startup.

The daily/manual **Update released viewer dependencies** workflow in StemLab
proposes new registry versions, lockfile, metadata and rebuilt frontend together
in a pull request. It does not auto-merge, publish packages or deploy Pages.
GitHub must permit Actions-created PRs; required review/Actions approval is
retained. A candidate missing the display APIs fails rather than silently falling
back to an older release. Merge a green update and release StemLab through this
same workflow. Until that update is merged, freshness CI deliberately reports
that main is stale rather than falsely claiming it uses the newest release.

## What must be committed together in StemLab

The helper's outputs are `package.json`, `package-lock.json`, `pyproject.toml`,
`.github/viewer-releases.json`, `.github/viewer-build.json`,
`.github/dancerudiments-recording-ref`, `src/stemlab/web/app.js`, and
`src/stemlab/web/timeline.css`. Do not commit only React source changes. The
coordinator stages these explicit files plus the reviewed kit/version/doc changes,
never arbitrary files from the working tree. The old local archive is removed
only when it is named by the old helper's metadata and its checksum still matches.

Frontend build inputs are hashed with normalized LF line endings; generated
JavaScript/CSS retain exact LF bytes under `.gitattributes`. Release/source/hash
metadata are evidence, not a substitute for the genuine npm build. Never add a
capability marker to old JavaScript merely to satisfy a test.

## Publication and Pages verification

StemLab's tagged release invokes the existing combined Arcadians workflow. It
keeps all four examples in one deployment:

- `timeline/arcadians/`: complete analysis with master and drum/percussion beat
  hypotheses, overlaid audio lanes and time/height controls;
- `arcadians/`: the original 48 master-derived recordings;
- `arcadians-stems/`: 60 actual different-stem two-dimensional recordings;
- `arcadians-averages/`: 180 peak/average/moving-average comparisons.

The three movement galleries use the released shared X–Y/bar harness. Each bar
corresponds to one stored dimension. Native sampling, complete-analysis checks,
audio-clock seeking, browser controls, HTTP range responses and post-deployment
public checks remain required. BeatNet and BeatThis run **after separation**, on
both the master and labelled drums/percussion; the master pass is not replaced.

The coordinator checks that the Pages deployment job actually ran successfully,
downloads the tested site and browser reports, and runs StemLab's existing
artifact and live URL/audio verifiers again. This final verification downloads
hundreds of megabytes of real-song assets. A package-only green run with skipped
Pages cannot be reported as complete. CI browser synchronization evidence is not
a claim of subjective listening QA in the PowerShell terminal.

Do **not** separately start the manual Arcadians workflow while the tagged
release is already running it. Keep Settings → Pages → Source set to GitHub
Actions and `STEMLAB_PAGES_ENABLED=true`. The script checks these and never
changes permissions, environment approvals, secrets or protection rules.
Approvals for `npm`, `pypi`, `nuget` or `github-pages` may require maintainer action.
The configured registry trusted publishers/credentials must already be valid.
Optional Conan, Docker Hub or MCP Registry destinations retain their existing
opt-in conditions and are not falsely reported as having published when skipped.

## Interrupted runs and failures

The session file defaults to `.danceflow-release-session.json` beside the three
checkouts, outside their Git histories. It stores only versions, source IDs,
phase, workflow IDs and kit hashes—never credentials. Preserve the kit and use:

```powershell
.\release-kit\Release-DanceFlow.ps1 -ProjectsRoot . -Execute -Resume
```

A prepared/tagged release resumes the same source and checks; it does not bump
again, retag, overwrite packages or push a replacement asset. Approve waiting
jobs or resolve a transient infrastructure problem and rerun those **same-commit**
jobs before resuming. The script never automatically reruns failed workflows.

A build failure before its version commit leaves its local edits for inspection.
A code fix, moved checkout, edited kit, unexpected dirty file or changed tag stops
resume: do not edit journal SHAs to bypass this safeguard. Review and commit the
fixes, complete or abandon the partial release deliberately, and start a new
session with a different `-StateFile` and fresh versions for any already-tagged
projects. Existing published tags/assets remain intact. The coordinator is
conservative: it releases all three projects; it does not guess how to adopt a
partially edited release or roll it back.

## Source of truth

Use the actual YAML and release-version scripts in each repository. GitHub
workflow-token event restrictions are documented at
https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication
and event triggers at
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows.
Registry tags/locking: https://docs.npmjs.com/cli/commands/npm-dist-tag and
https://docs.npmjs.com/cli/commands/npm-ci. Never bypass a failed publication gate
because an older artifact or a different commit was green.

## This repository's role

DanceRudiments owns the native sampler and packaged shared catalogue/recording
harness. Publish its `SampledRecording` and `HARNESS_DISPLAY_API_VERSION == 1`
capabilities before updating StemLab. Keep the per-dimension bar renderer and
X–Y renderer on the same native samples and audio clock.

Use `python tools/release_version.py prepare X.Y.Z` to update CMake, Python,
npm/lock and C#/NuGet together; never bump just one binding. The coordinator uses
this tool, waits for all six main workflows, and creates a fresh tag only after
success. Existing tag workflows publish Python wheels/sdist, TypeScript/WASM,
C++ archives, the release visualizer and C#/NuGet, with the optional Conan upload
retained. PyPI, scoped npm and NuGet version visibility are verified before StemLab
is released. Retain matching third-party licences and release assets.

### Windows checksum regression

The two recording WASM source inputs, `tools/recording_wasm.cpp` and
`include/dancerudiments/recording_view.hpp`, are byte-hashed by
`recording.wasm.json`. Windows `core.autocrlf=true` previously changed their bytes;
the exact observed failure was the CRLF form of the unchanged C++ source. The
`.gitattributes` LF rules preserve those inputs (and their manifest/base64
artifacts). Do not weaken SHA checks, rewrite expected hashes for CRLF, skip
Windows tests or rebuild a different native module to hide this defect.

```powershell
python -m unittest discover -s tests/python -p test_recording_source_eol.py -v
$Version = python tools/release_version.py current
python tools/check_release_version.py "v$Version"
```

The new regression makes a real Git index, checks out with autocrlf enabled,
and requires exact original manifest hashes. Full native/binding checks remain
in the existing main CI. The new line-ending policy takes effect on fresh CI
checkouts; do not destructively reset an existing local working tree to apply it.
