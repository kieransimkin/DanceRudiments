# Source-first animation beat and loop discovery

`tools/analyze_source_motion.py` uses StemLab's rig-motion analyser **before**
converting original animation into DanceRudiments' 64-pip `RigMotion` recordings.
The same job now has **two independent authoring outcomes**: a complete
BPM-grid-matched Action (when the source-wide fit passes the default 70% policy),
and source-time loop candidates that may be retained even if the complete Action
is not sufficiently rhythmic.
The original source Action is preserved unchanged. Complete Actions are
converted only after the whole-action fit gate; StemLab-ranked loop candidates
have their own seam/pose/root-drift gates. Both remain **review-only** recordings. A
candidate is not silently promoted to a built-in pattern, a music-confirmed
beat grid or an approved seamless animation.

## Data flow

1. **Read original source:** Use the pinned BVH importer, retaining its complete
   source frames, exact rational frame interval, source SHA-256, source skeleton,
   numbered physical channels and axes. For FBX, GLB or BLEND, first use
   `tools/blender_motion_import.py extract` to evaluate and capture individual
   animated Actions (including relevant constraints) in a versioned
   `.capture.json`. Do not analyse keyframe indices as though they were seconds.
2. **Exclude source calibration only when known:** `--calibration-frames 1`
   excludes a T-pose lead-in from analysis without rewriting the source. Do not
   remove real frames just to force a stronger rhythm score. For Blender captures,
   perform any known selection during extraction instead.
3. **Ask StemLab:** The unquantised source capture is written to a separate new
   output directory. StemLab validates the complete physical profile and
   timestamps, then estimates motion accents, candidate BPM/phase, recurring
   poses, loop seams, root displacement and joint velocity discontinuity.
4. **Score the entire Action:** Compare StemLab's BPM candidates across movement
   periodicity, weighted motion accents, beat-phase agreement, support from
   independent rig control groups, and coverage throughout the original Action.
   Every Action receives a ranked BPM hypothesis list, a 0–100 heuristic
   **grid-fit confidence**, and rejection reasons. A default `>=70%` fit permits
   full-length conversion. This number is **not a statistically calibrated
   probability** that the dance was performed to a particular musical BPM;
   half/double time, downbeat and metre ambiguity remain explicit. Compiling
   starts at the first valid 64-pip sample within the original source times
   and ends at the last; sub-pip head/tail gaps are recorded, not extended.
5. **Separately identify loopable source motion:** Accept only explicitly unapproved
   `estimated_motion_beat_grid` candidates with supported beat counts, a matching
   **unverified** StemLab beat-map provenance and source-time seam diagnostics
   within StemLab's physical mismatch thresholds. Do not compile corrupted,
   externally approved or missing-grid evidence. Use the
   candidate's exact source start/end seconds for the source beat map. Compile
   into the standard `RigMotion` format at 64 pips per quarter-note beat,
   with half-open loop boundaries, **without** adding a second runtime sampler.
   `pose_recurrence_only` evidence remains in StemLab's report and is **not**
   assigned an arbitrary tempo or converted automatically.
6. **Verify and review:** Optional `--verify-native` compares the new recordings'
   representative native pip samples against the compiler. It does **not** prove
   loop blending, target-rig deformation, foot contact, true musical downbeats,
   or audio sync. Those require explicit inspection and audio timing evidence.

## Setup and usage

Use a compatible StemLab **source checkout or published release containing its
`stemlab.analysis.rig_motion` interface**. Its rig-motion implementation only
needs NumPy for this job; avoid downloading any machine-learning models for
kinematic analysis. The currently pinned StemLab source also imports its
high-level audio analysis package on module initialisation; this transitively
requires **soundfile** even for the otherwise NumPy-only rig analyser. Install
`soundfile>=0.12,<1` when working with that source checkout. The dedicated CI
job installs only this light compatibility requirement, and verifies the actual
pinned analyser file is loaded. Keep StemLab optional rather than forcing its
large audio stack on base DanceRudiments consumers.

```sh
# Source-time BVH, no previous rudiment conversion:
python tools/analyze_source_motion.py .cache/motion-sources/my-dance.bvh \
  --source-id my_dance --output-dir .cache/source-loop/my-dance \
  --calibration-frames 1 --min-bpm 70 --max-bpm 180 \
  --target-bpm 124 --min-full-confidence 0.70 --max-previews 6 --verify-native

# Blender FBX/GLB/BLEND: first extract evaluated animation Actions into captures.
blender --background --factory-startup --python tools/blender_motion_import.py -- \
  extract my-dancer.glb --source-id my_dancer \
  --output-dir .cache/extracted/my-dancer --sample-fps 60

# Choose a real file from .cache/extracted/my-dancer/index.json, then:
python tools/analyze_source_motion.py .cache/extracted/my-dancer/actual.capture.json \
  --output-dir .cache/source-loop/my-blender-action --max-previews 4

# Analysis only, preserving unquantised timing and not converting any preview:
python tools/analyze_source_motion.py original.bvh \
  --output-dir .cache/source-loop/report-only --max-previews 0 --no-full-motion
```

For **entire reviewed imported collections**, the batch job reads the source
archives directly from the local cache, validates them according to the original
source plan, applies any evidenced frame-time corrections and detects duplicates
by original member SHA-256. It never downloads a source or converts the full
Action into a time-only rudiment as a prerequisite:

```sh
python tools/analyze_motion_collection.py --sources cmu_dance \
  --cache-root .cache/motion-sources \
  --output-root .cache/loop-analysis/cmu --max-actions 100 \
  --max-previews 4 --min-full-confidence 0.70 --target-bpm 124 --verify-native
```

Each action gets its own independent evidence and optional preview folder;
`index.json` records original member paths, licence, SHA-256, action failures
and any explicit analysis limit. The source ZIP must already be present. Source
plans can establish different levels of upstream checksum assurance; the tool
records the actual bytes' SHA-256 even where the upstream metadata supplied
only a size. Source-specific axis, root-offset and translation conventions
must match the reviewed plan. Reuse any independently evidenced frame-time
corrections *before* analysing: merely reading an original BVH header does not
establish its musical tempo or prove that a third-party converter preserved the
actual capture rate. For individual BVH inputs, use `--frame-time-override` with
a reviewed JSON document containing `frame_time_seconds` (for example,
`"1/60"`) and an `evidence` object documenting the source of the correction.
This applies the existing original-frame timing correction API before analysis;
never infer the correction from the rhythm being sought.

Each output is a new directory containing:

```text
job.json                      # source identity, ranking, preview links, review flags
source.capture.json           # original physical source-time samples (analysis view)
stemlab-analysis.json         # StemLab motion evidence and all candidate loops
estimated-source-beats.json   # only when a movement-grid hypothesis exists
full-length/source_full_action.motion.json # only if confidence >= threshold
loopable-clips.json          # independent candidate catalogue
previews/*.motion.json        # optional, non-looping, estimated-tempo previews
```

The full-length motion uses the saved numbered rig profile, original capture
fingerprint and SHA-256, original provenance and explicit estimated source BPM,
confidence, alternative tempo hypotheses and unrepresented sub-pip endpoints.
It is **non-looping** and has `bpm_status=estimated`. `--target-bpm` changes its
presentation clock; it does not raise the confidence score. Set
`--min-full-confidence` (default `0.70`) to adjust the conservative authoring
policy, or `--no-full-motion` to produce evidence without compiling the complete
Action. `--max-previews 0` independently disables loop conversion.

The compiled loop is a half-open integer-pip recording `[0, beats*64)`.
The separate `loopable-clips.json` references the original `previews/` recordings
without duplicating compressed/large motion payloads. Each recording carries a
`suggested_loop_period_pips` and `suggested_loop_playback` marker; wrapping is
**not automatically enabled** in the native sampler. A loop remains a suggestion
until seam/contact/retarget checks pass. It does
**not** contain an explicit duplicate end pose, interpolate between repeats,
remove root travel, apply foot-planting corrections or auto-loop in the native
engine. For audition, the host must explicitly seek to the first pip at each
period boundary. For publishing, verify the exact target model with the normal
skinned-mesh browser tests and any required StemLab audio beat maps. The
`target_bpm` option only sets a preview's nominal musical transport clock; it
does not change the source rhythm evidence, and changes playback speed rather
than certifying fit to a song.

All reports include source/profile SHA-256 and explicit `requires_review` and
`audio_beat_alignment_verified=false` flags. Generated motion candidates are
optional data; they must not be bundled into the base package or registered
site-wide. Output directories are never overwritten; jobs write into a
project-local temporary directory and rename the complete result into place.

## CI

`.github/workflows/source-motion-loops.yml` tests synthetic captures, original
BVH parsing, calibration exclusion, native 64-pip compilation, negative
cases, and a full StemLab rhythm inference smoke test using a pinned test-only
StemLab source snapshot. That snapshot is **not** a runtime or release dependency.
It fails if the StemLab analyser is missing (no silent test skips), and checks
that the synthetic source yields a real tempo hypothesis and at least one
compiled preview, rather than letting `all([])` count as verification. A generic
suite with no NumPy can skip only the NumPy-dependent BVH import fixture; the
motion-analysis workflow treats NumPy and native playback as hard requirements.
No third-party source downloads, model weights, musical tracks or rights-bearing
motion assets are needed for these regression checks. Production and release
workflows must independently use compatible **officially published** packages.


## Test the motion candidates against bundled StemLab songs

The dedicated source-first workflow also runs StemLab exploratory **audio** loop
analysis over the three bundled example masters, checks beat evidence and pairs
possible musical loop windows with native-verified synthetic rig loop previews.
It generates an **audio-free interactive review visualiser** with waveform, beat
markers, ranked candidates, source-rig motion and a local hash-verified audio
file picker. This does not certify audio beat-1, foot planting or seamless
transitions. See [song loop preview](song-loop-preview.md).

## Whole-Action shortlist and source provenance

The batch `index.json` contains independent `full_motion_shortlist` and
`loopable_shortlist` arrays. Each complete Action records its original source
archive, member, bytes' SHA-256, plan SHA-256, licence, rig profile fingerprint,
selected BPM, competing tempo hypotheses, confidence and acceptance gate.
Collection imports supply those provenance fields to the capture **before** any
StemLab evaluation; the compiled `RigMotion.recording.provenance` retains them.
The full motion preserves root travel and does **not** claim a safe repeating
seam. The loop shortlist uses separate pose/velocity/root-drift criteria even
when an Action fails the full-length >=70% confidence gate.

This is a **kinematic** beat fit, not an audio matching probability. A numeric
percentage can be calibrated against labelled motion/audio examples later;
version `dancerudiments.full-motion-grid-fit.v1` is a transparent evidence score
with separate periodicity, whole-action coverage, beat phase and control support.
A performer moving regularly at 60 BPM may also fit a 120 BPM subdivision; both
hypotheses remain available for manual selection, and no downbeat is silently
approved.

## Blender FBX/GLB/BLEND multi-Action batches

Use the original `index.json` created by
`tools/blender_motion_import.py extract` to analyse every explicitly listed
source-time `.capture.json` without resampling or recompiling up front:

```sh
python tools/analyze_blender_capture_batch.py \
  --index .cache/extracted/my-model/index.json \
  --output-root .cache/loop-analysis/my-model \
  --min-full-confidence 0.70 --max-previews 4 --verify-native
```

The job checks the exact indexed profile SHA-256 and the original source FBX/GLB/BLEND
SHA-256 recorded by Blender inside each captured Action. It does not execute the
original Blender file, open referenced external texture files or reinterpret
unverified music tempo as a confirmed beat. The output has independently ranked
`full_motion_shortlist` and `loopable_shortlist` arrays and rejects missing or
inconsistent capture identities rather than silently retargeting to another rig.
