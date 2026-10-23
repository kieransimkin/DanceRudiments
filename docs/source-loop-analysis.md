# Source-first animation beat and loop discovery

`tools/analyze_source_motion.py` uses StemLab's rig-motion analyser **before**
converting original animation into DanceRudiments' 64-pip `RigMotion` recordings.
The original source Action is preserved unchanged. Only StemLab-ranked, estimated
beat-grid candidates are compiled into **review-only** preview rudiments. A
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
4. **Select and compile previews:** Accept only explicitly unapproved
   `estimated_motion_beat_grid` candidates with supported beat counts, a matching
   **unverified** StemLab beat-map provenance and source-time seam diagnostics
   within StemLab's physical mismatch thresholds. Do not compile corrupted,
   externally approved or missing-grid evidence. Use the
   candidate's exact source start/end seconds for the source beat map. Compile
   into the standard `RigMotion` format at 64 pips per quarter-note beat,
   with half-open loop boundaries, **without** adding a second runtime sampler.
   `pose_recurrence_only` evidence remains in StemLab's report and is **not**
   assigned an arbitrary tempo or converted automatically.
5. **Verify and review:** Optional `--verify-native` compares the new recordings'
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
  --target-bpm 124 --max-previews 6 --verify-native

# Blender FBX/GLB/BLEND: first extract evaluated animation Actions into captures.
blender --background --factory-startup --python tools/blender_motion_import.py -- \
  extract my-dancer.glb --source-id my_dancer \
  --output-dir .cache/extracted/my-dancer --sample-fps 60

# Choose a real file from .cache/extracted/my-dancer/index.json, then:
python tools/analyze_source_motion.py .cache/extracted/my-dancer/actual.capture.json \
  --output-dir .cache/source-loop/my-blender-action --max-previews 4

# Analysis only, preserving unquantised timing and not converting any preview:
python tools/analyze_source_motion.py original.bvh \
  --output-dir .cache/source-loop/report-only --max-previews 0
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
  --max-previews 4 --target-bpm 124 --verify-native
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
previews/*.motion.json        # optional, non-looping, estimated-tempo previews
```

The compiled loop is a half-open integer-pip recording `[0, beats*64)`. It does
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
