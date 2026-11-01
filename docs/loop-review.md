# Review, finish and export an imported motion loop

The review backend joins an explicit source window, bounded loop correction,
StemLab's accepted audio mapping and a separate target-mesh review. It creates a
normal optional motion package whose native samples are unchanged by packaging.
The exact audio mapping stays with that clip so it can replay the accepted timing.

This is development source until matching stable packages are published. It
requires the optional `motion-import` dependencies, compatible StemLab timing
review APIs and a built native DanceRudiments extension for native verification.
There are no downloads, model inference, global catalogue registrations or
automatic artistic approvals in this workflow.

## Open the local Kandi review workspace

From a source checkout, install the authoring extra, the compatible StemLab
source revision used by source CI, and the checked-in Node dependencies:

```sh
python -m pip install -e '.[motion-import]'
npm ci
python tools/review_motion_loop.py --help
```

Start with an original Action capture, a StemLab alignment report that hashes
those exact capture bytes and your exact audio master, an explicit source
calibration pose, and the source's actual licence. The audio stays at its
selected local path. A re-encoded copy does not satisfy an existing report.
Save the source licence as JSON with `id`, `url` and `attribution`; include any
additional source terms in that object. The command records your declaration
and does not grant redistribution rights.

```sh
python tools/review_motion_loop.py prepare \
  --capture analysis/source.capture.json \
  --audio music/exact-master.mp3 \
  --alignment-report analysis/alignment.json \
  --output .cache/my-loop-review \
  --start-seconds 2 --end-seconds 4 --beats 4 \
  --original-source-sha256 ORIGINAL_MODEL_SHA256 \
  --calibration-capture extracted/calibration.capture.json \
  --calibration-seconds 0 \
  --license-json source-license.json
python tools/review_motion_loop.py serve .cache/my-loop-review
```

Use the printed loopback URL. The page is the existing Kandi renderer with a
local review panel. It does not publish a site or require an account. In
PowerShell, enter the `prepare` invocation on one line or use PowerShell's
backtick continuation instead of the shell backslashes shown above.

The initial interval must pass the bounded correction and native checks. Use an
accepted analysis candidate as the starting point when the desired boundaries
are not yet known. `--repair-options settings.json` accepts the same bounded
options as source analysis; it never relaxes the numerical gate implicitly.
The command writes a new directory and preserves previous workspaces.

1. **Load the review clip.** The exact source profile, corrected recording,
   source rig, Kandi assets and calibration are verified before playback.
2. **Choose timing.** Select an alignment candidate, adjust phase, or enter
   strictly ordered manual source/audio anchor pairs. Beat one and meter are
   optional separate declarations. Audio drives the existing native pip sampler.
3. **Finish a new selection.** Change source start/end or beat count and press
   the finishing button. The server re-runs canonical bounded repair, compiled
   seam checks and native parity. A failed correction leaves the previous
   selection intact; a successful change clears its visual approval.
4. **Inspect Kandi.** Compare original and corrected motion, deliberately enable
   repeat, and assess the seam, feet and skin. Unsupported or poor mappings do
   not become approved through numerical success.
5. **Save draft or review.** Drafts preserve controls without approving export.
   Save the timing and individual visual decisions when ready. Reopening the
   same workspace restores the exact mapping and decisions; a stale second tab
   must reload before writing.
6. **Export the reviewed package.** All required visual verdicts must be
   accepted. Export verifies the current source, master, target and review,
   builds the standard optional package, reloads it and checks native parity.
   The downloaded ZIP contains the motion, source profile, timing/review
   metadata and notices; audio and Kandi assets remain local.

Changing the timing controls marks the current review dirty. Saving a draft or
finishing different boundaries prevents export until another review is saved.
The original evidence's approval flags remain unchanged; reviewer decisions
live in separate revisioned records.

### Supported source rigs and calibration

The local workbench supports the evaluated portable skeletal carrier produced
by the existing BVH and Blender importers. It validates the saved hierarchy,
rest matrices and explicit transform groups through the canonical offline world
evaluator. The existing Kandi evaluator then uses `parent * rest-local * TRS`,
with the original numbered channels and Blender Z-up convention. Arbitrary
unevaluated constrained Rigify controls need the existing Blender evaluation
route first.

The default bone map is the exact CMU-to-Kandi map already used by the gallery.
For another humanoid naming convention, supply `--retarget-map map.json`: a
complete object mapping those Kandi target bone names to exact, unique source
bone names. Missing or guessed matches are rejected. This is explicit retarget
configuration, not an assertion of anatomical suitability for every rig.

`--calibration-capture` must have the exact same profile. Its selected seconds
must identify one actual captured frame, which can come from a separate saved
calibration capture. The builder never interpolates a guessed T-pose. The
calibration identity includes that pose, source rest rig and bone map, exact
Kandi rig, and the retarget implementation. Updating it requires a new review.

The preview contains the continuous source segment enclosing the initial
selection. Missing source spans are never compiled into a continuous preview.
Choose a new workspace for another disconnected segment. The optional full
Action conversion threshold remains 70%; explicit review does not lower it.

### Local persistence and automation

The workspace contains immutable source/selection/review snapshots, a rendered
site, and an atomically updated `state.json`. Only declared assets are served.
Concurrent writers use an operating-system lock that is released if the server
exits, including during a failed save. The persistent lock file is not an
active-owner marker; restarting the server can safely reopen the last committed
state without deleting it. Stale tabs still need to reload their revision.
The server binds `127.0.0.1`, issues a fresh per-run capability in the URL
fragment, rejects foreign origins/hosts, and uses port-specific same-site
cookies for source/target assets. API operations require the capability header;
there is no general file browser, arbitrary command endpoint or remote bind.

Use `python tools/review_motion_loop.py inspect .cache/my-loop-review` for a
validated session summary. Stop and restart `serve` to reopen the same saved
work. The token changes; source identities and review revisions persist.

`prepare --automated-test` creates a permanently labelled test workspace.
Automated browser checks use that mode, and any resulting package remains an
unapproved test fixture. This switch is not a shortcut to a human-reviewed pack.

## Finish an explicit window

Use the original `source.capture.json` from an existing source-analysis job or
the validated capture from an imported FBX, GLB/glTF or BLEND Action. Analyse
before choosing a window; preserve the import's exact original file hash and
source-clock conventions. A `.motion.json` is compiled output and cannot replace
the original capture.

```python
from dancerudiments_authoring.loop_review import finish_review_selection

selection = finish_review_selection(
    "analysis/source.capture.json",
    "motion-packs/review-work/selection-001",  # a new directory
    start_seconds=0.90431,
    end_seconds=2.00776,
    beats=4,
    original_source_sha256="<exact original BVH/model SHA-256>",
    repair_options={"contact_policy": "root_stabilize"},
    verify_native=True,
)
```

Boundaries use original capture seconds. They must lie inside one continuously
observed source segment; gaps and out-of-range endpoints are rejected before
interpolation. The explicit beat count is an interpretation, with 1–32 beats and
a resulting 30–300 BPM source coordinate. Changing 4 beats to 8 changes the
native representation to 512 pips and invalidates the old review. It does not
change physical playback speed by itself.

This calls the same `repair_loop` and `compile_repaired_loop` route used by
automatic proposals. It uses `beats * 64 + 1` corrected capture samples and
compiles `beats * 64` half-open native samples. Bounded pose/tangent/contact and
activity gates remain mandatory. Unsupported world layouts are labelled by the
existing evaluator; control captures need an explicit translation scale when
required. A rejected window raises with its rejection reasons and leaves no
published selection. A native parity failure aborts the transaction.

The new selection directory contains:

| File | Purpose |
| --- | --- |
| `source.capture.json` | Exact original capture bytes, copied without reserialization |
| `corrected.capture.json` | Separately identified corrected endpoint-inclusive capture |
| `finished.motion.json` | Native half-open recording and unchanged source profile |
| `repair.json` | Bounded correction, contact and final compiled verification evidence |
| `selection.json` | Source identities, chosen boundaries/beats, exact asset hashes and selection ID |

Every output is new. Existing selections and source files are never overwritten.
The selection manifest is published last. `load_selection(directory)` verifies
all file hashes, profile/capture identities, bounds, correction binding and the
actual final compiled payload; `verify_native=True` additionally checks C++
playback. Its `requires_review` state remains true because generated numerical
evidence is not a reviewer's decision.

## Bind timing to the source and visual decisions to the target

Use an existing `stemlab.motion-alignment.v1` report and
`stemlab.motion-alignment-review.v1` revision against the **original capture byte
hash**. The revision can select an inferred candidate, apply a phase correction
or supply manual source-clock anchors through StemLab. Its accepted mapping must
cover the whole chosen interval inside one continuous segment. Missing source
coverage is never joined.

The finished capture starts at local time zero. Playback translates that to the
original selected start before applying the accepted source-to-audio mapping.
Audio is verified against the actual local master bytes whenever a review is
created or a package is exported. Supplying a similar song or re-encoded copy
does not satisfy that identity.

```python
from dancerudiments_authoring.loop_review import create_loop_review, write_review

target = {
    "id": "kandi_boom",
    "asset_sha256": "<actual target mesh bytes hash>",
    "rig_sha256": "<actual saved target rig bytes hash>",
    "calibration_sha256": "<actual source-to-target calibration bytes hash>",
}
review = create_loop_review(
    "motion-packs/review-work/selection-001",
    alignment_report_path="analysis/alignment.json",
    timing_revision_path="analysis/timing-decision.json",
    audio_source_path="music/exact-master.wav",
    target=target,
    reviewer="Reviewer name",
    verdicts={"seam": "accept", "feet": "accept", "skin": "accept"},
    notes="Inspected the repeating phrase against this exact master and target.",
)
write_review("motion-packs/review-work/review-001.json", review)
```

Enter `accept` only after that inspection. `reject` and `unreviewed` are valid
saved visual verdicts and prevent promotion. The three dimensions deliberately
separate the repeat seam, feet and skin deformation. Confirming an audio mapping
does not confirm any of them, and it does not implicitly establish beat one or
meter. Those optional StemLab confirmations are preserved as supplied.

The `dancerudiments.loop-review.v1` record contains exact timing-report and
revision text plus hashes, the selection's exact file hash, the compiled motion
fingerprint, the target/calibration identities, a timezone-qualified timestamp,
reviewer, verdicts and notes. It preserves the original numerical report instead
of changing its approval flags. These are explicit reviewer declarations, not
cryptographic proof of a person's identity or an automatic quality judgement.

Pass `previous_review=old_record_or_path` for another revision of the same
selection. The canonical previous-document hash and incremented revision number
are retained. `validate_loop_review(..., previous_review=...)` verifies that
chain. A different boundary, beat count or compiled output requires a fresh
review. Supply `expected_target` when validating against the current target;
changed geometry, rig or calibration invalidates the old decision.

`review_kind="automated_test"` is reserved for test fixtures. Such records retain
`human_approved=false`; they cannot export without the explicit test-only
`allow_test_review=True` argument and remain labelled as fixtures in the package.
Automated browser clicks must never be presented as musical or visual listening
approval.

## Export and reproduce the accepted result

```python
from dancerudiments_authoring.loop_review import export_reviewed_loop
from dancerudiments_authoring.motion_packages import export_motion_package

export_reviewed_loop(
    "motion-packs/review-work/selection-001",
    "motion-packs/review-work/review-001.json",
    "motion-packs/my_dance_loop/1.0.0",
    audio_source_path="music/exact-master.wav",
    expected_target=target,
    package_id="my_dance_loop", version="1.0.0", title="Reviewed dance phrase",
    license={"id": "<actual source licence>", "url": "<source licence URL>",
             "attribution": "<required attribution>"},
    provenance={"source_url": "<original source URL>"},
)
export_motion_package("motion-packs/my_dance_loop/1.0.0", "my-dance-loop.zip")
```

This uses `MotionPackageBuilder` and the existing package/ZIP schema. The clip's
`metadata.reviewed_loop` contains the saved decisions and a bounded
`dancerudiments.reviewed-loop-playback.v1` descriptor. The package includes the
canonical source profile, compressed Recording, source hash/provenance and
notices. Original capture samples, audio and target geometry are excluded.

Absolute local filesystem paths in source provenance, timing or review data are
refused before packaging. They are not silently removed from an already reviewed
motion. Prepare portable provenance, create a new selection and review it again
if an importer recorded a private local path.

The native samples retain their estimated source-coordinate clock. Use the
saved playback descriptor to reproduce the reviewed audio mapping; treating its
nominal BPM as a new confirmed constant audio tempo would discard a variable
mapping. The helper maps audio seconds to original source seconds, then to an
integer pip in the existing recording. It performs no motion interpolation.

```python
from dancerudiments_authoring.loop_review import load_reviewed_loop

player = load_reviewed_loop("motion-packs/my_dance_loop/1.0.0", "reviewed_loop")
physical_channels = player.sample_audio(audio_current_seconds)
# None outside the selected audio interval. Explicit audition repeat:
repeated_channels = player.sample_audio(audio_current_seconds, repeat=True)
```

`audio_seconds_to_pip(review_or_playback, seconds, repeat=False)` exposes the same
clock mapping for hosts that already own a native player. The audio interval is
half-open. Its exact closing time returns `None`; explicit repeat maps that time
back to the first pip. Times before the loop return `None` even with repeat.
The final valid interior time maps to the last stored pip, never a duplicated
closing pose. Manual variable-rate anchors remain strictly monotone, and
piecewise timing is preserved in the optional package.

## Verification

`tests/python/test_loop_review.py` exercises actual source correction, StemLab
alignment/review, package ZIP installation, decoded native playback, variable
mapping, half-open repeat, byte/source/target identity changes, revision chains,
gap rejection, private-path refusal and transaction rollback. All fixtures are
synthetic and labelled as automated tests. The source completion regressions
also cover the shared compiler after extraction of its reusable helper.

```sh
PYTHONPATH=../stemlab/src python -m pytest \
  tests/python/test_loop_review.py tests/python/test_source_motion_completion.py \
  tests/python/test_loop_repair.py tests/python/test_loop_review_workspace.py -q
npm test
python tools/build_loop_review_test_fixture.py \
  --output-dir .cache/loop-review-fixture
python tools/test_loop_review_browser.py \
  --workspace .cache/loop-review-fixture/workspace \
  --output-dir .cache/loop-review-browser-qa
```

The browser gate requires the project's Playwright/Chromium test environment.
The fixture generator uses synthetic motion, WAV audio and timing observations
with the checked-in Kandi assets; it downloads no media or models. Its decisions
and exported package remain explicitly labelled automated test data. Workspace
regressions also exercise HTTP authentication, stale writes, interrupted-writer
recovery and publication without replacing an existing directory on Windows.

The local workbench and actual Kandi/browser gates test the integration surface;
they are separate from subjective timing and target-mesh decisions. Source CI,
optional package creation, official package publication and website deployment
remain distinct states.
