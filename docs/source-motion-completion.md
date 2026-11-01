# Source-motion analysis and bounded loop finishing

DanceRudiments can analyse original BVH frames or extracted Blender Actions,
export source-bound motion events, and create separately identified, numerically
closed loop derivatives. StemLab supplies the tempo and recurrence evidence;
DanceRudiments supplies the saved rig identity, world evaluation, bounded offline
correction and native **64-pip-per-beat** compilation.

The complete source Action, unchanged loop candidates and corrected derivatives
have separate catalogues. Analysis runs in original source seconds before any
resampling. A repaired loop does not raise the source tempo confidence or approve
its musical phase, target mesh or actual foot contact.

The next authoring step is the [local loop-review workspace](loop-review.md):
choose explicit boundaries and beat count, audition a source-bound audio
mapping on Kandi, save timing and separate visual decisions, then export a
standard optional package. Explicit finishing uses the same bounded repair and
native verification as automatic candidates; it does not promote an ambiguous
full Action or lower the 70% conversion threshold.

Timestamp gaps greater than three times the capture's median sample interval
split observed coverage, including when world-space analysis is disabled.
Complete-Action export cannot fill those gaps. Raw and corrected loop windows
must fit one covered interval; exported timing events never invent observations
inside missing spans. Isolated source frames remain in the capture and coverage
metadata but cannot establish a positive-duration alignment segment.

## Run one extracted Action

Use a compatible StemLab installation with source-world evidence and motion-event
support, the DanceRudiments authoring dependencies, and a built native Python
extension when passing `--verify-native`. These are offline analysis commands;
the single-Action, archive and Blender-index routes do not download assets or
models. Output directories must be new and separate from source files.

Save explicit optional correction settings as `repair-options.json`:

```json
{
  "root_policy": "preserve",
  "contact_policy": "root_stabilize",
  "require_contacts": false
}
```

Then run:

```sh
python tools/analyze_source_motion.py path/to/action.capture.json \
  --output-dir .cache/motion-review/action-01 \
  --tempo-strategy consensus \
  --repair-loops --max-repairs 6 --repair-options repair-options.json \
  --verify-native
```

An original `.bvh` is also accepted. Supply its reviewed `--source-id`, axis,
unit and root-offset conventions. Exclude a calibration pose only when known,
using `--calibration-frames`; an FPS correction requires
`--frame-time-override` JSON containing `frame_time_seconds` and recorded
`evidence`. The original bytes and original source hash are preserved. A compiled
`.motion.json` is not an original analysis input.

`root_policy="preserve"` allows bounded local seam correction without removing
the source's overall travel. `"in_place"` explicitly removes linear root travel
and includes that change in the correction budget. `contact_policy="validate"`
is the default: it measures supplied stance constraints and rejects excessive
slip. `"root_stabilize"` may apply bounded root translation to satisfy them.
Conflicting feet and excessive corrections reject the candidate.

Set `require_contacts=true` when an accepted derivative must have usable stance
constraints. With the illustrated `false` value, a candidate without inferred
contacts can pass the pose/tangent checks; its report explicitly records contact
evidence as unavailable. Numerical contact checks remain hypotheses about the
source skeleton rather than ground-truth foot plants. See
[loop-repair.md](loop-repair.md) for correction limits and report fields.

## Evidence selection and output

World evaluation is enabled by default for a validated portable source skeleton
with complete saved rest transforms. Arbitrary Rigify controls with unevaluated
constraints are reported as unsupported. They do not silently receive an
approximate world skeleton.

`--tempo-strategy consensus` compares control, world and contact evidence and can
abstain when the families disagree. `control`, `world` and `contact` select an
explicit family for diagnosis. `--no-world-space` disables world evaluation and
cannot be combined with `world` or `contact`. Evidence derived from one capture
is not counted as independent audio-model corroboration.

| Output | Meaning |
| --- | --- |
| `source.capture.json` | Unchanged physical source samples, timestamps, profile and provenance |
| `world-motion-evidence.json` | Exact source binding, world envelopes, joint/contact hypotheses, or explicit unsupported status |
| `stemlab-analysis.json` | Tempo alternatives, family selection/abstention and unchanged-source loop evidence |
| `motion-events.json` | Observed motion accents/contact events for source-bound audio alignment; no fabricated regular beat points |
| `full-length/` | Complete non-looping Action, exported only if the declared whole-Action confidence gate passes |
| `loopable-clips.json`, `previews/` | Unmodified source-loop candidates under the existing seam filters |
| `loop-repairs.json`, `repaired-loops/` | Separate accepted derivatives and all attempted corrections with rejection reasons |
| `job.json` | Source/profile identities, exact file hashes, selected settings and independent output counts |

`--repair-loops` is explicit and disabled by default. It ranks at most 128
beat-length windows and attempts at most `--max-repairs` corrections per Action
(1–12 in the CLI). It can propose a corrected window even when the unchanged
source has no strict loop candidate. A missing or abstained source tempo prevents
automatic beat-length repair proposals.

Every accepted derivative has a `.capture.json`, `.motion.json` and
`.repair.json`. The corrected capture retains the original source provenance and
interval; its identity differs from the original. Compilation uses exactly
`beats * 64` samples, excluding the duplicate closing endpoint. Before export,
the compiled verifier compares every decoded sample with the corrected capture,
checks the actual wrap pose/tangent and rechecks supplied foot constraints. A bad
compiled candidate is recorded as rejected and produces no derivative files;
later candidates can still succeed. `--verify-native` additionally compares the
compiled samples with native playback. A native parity failure aborts the
transaction rather than publishing a partial result.

The repair report binds the final motion by both canonical fingerprint and exact
file SHA-256. It records correction magnitude, activity retention and contact
coverage. `numerical_repeat_seam_verified` can become true while
`loop_seam_approved`, `audio_beat_alignment_verified` and mesh approval remain
false. The retained-motion score is not a probability of artistic quality.

Motion events use the exact `source.capture.json` byte hash and the
`source_capture_seconds` clock. StemLab's optional motion/audio alignment API
requires those original bytes, explicit audio event evidence and a declared
clock mapping; the motion-only tempo estimate is not musical verification. See
StemLab's `docs/motion-alignment.md` for alignment proposals and explicit review
revisions.

## Analyse reviewed archives or extracted models

For already cached archives from the reviewed source plan:

```sh
python tools/analyze_motion_collection.py \
  --plan motion-packages/sources.json --sources cmu_dance \
  --cache-root .cache/motion-sources \
  --output-root .cache/motion-review/collection-01 \
  --max-actions 100 --tempo-strategy consensus \
  --repair-loops --max-repairs 6 --repair-options repair-options.json \
  --verify-native
```

Archive/member hashes, license, source-plan identity and timing corrections
survive in the source capture and corrected derivative provenance. Collection
indexes have separate `full_motion_shortlist`, `loopable_shortlist` and
`repaired_loop_shortlist` fields. Source files are not rewritten.

For the exact `index.json` produced by Blender Action extraction:

```sh
python tools/analyze_blender_capture_batch.py \
  --index .cache/extracted-model/index.json \
  --output-root .cache/motion-review/model-01 \
  --tempo-strategy consensus \
  --repair-loops --max-repairs 6 --repair-options repair-options.json \
  --verify-native
```

This validates every indexed Action's source-file and profile identities. It
reads the extracted capture files; it does not reopen or execute the model file.
The original model hash remains distinct from the extracted source-capture and
corrected-capture hashes.

## Pinned real-source validation

The existing two-source benchmark applies the reviewed CMU source recipes,
including Salsa `60_01`'s explicit 60 FPS correction and calibration exclusion:

```sh
python tools/evaluate_real_rig_motions.py \
  --cache-root .cache/real-motion-sources \
  --output-dir .cache/motion-review/cmu-summary-01 \
  --tempo-strategy consensus \
  --repair-loops --max-repairs 6 --repair-options repair-options.json
```

The default uses existing pinned files. Its explicit `--download` option acquires
only the two approved recipe sources when authorized. The benchmark's output
directory contains diagnostic summaries; source and derivative motion remain
in separate private local directories. Real third-party motion is not a test
fixture or a base-package payload.

Local development validation of the full single-Action CLI, using the two pinned
sources, a 60–240 BPM search, consensus selection, six correction attempts,
`contact_policy="root_stabilize"` and native verification, produced:

| Source | Tempo decision | Full Action at 70% threshold | Unmodified previews | Corrected derivatives |
| --- | --- | --- | ---: | ---: |
| CMU Salsa `60_01` | Control fallback, 217.5 BPM; 51.85% whole-Action fit | Rejected | 4 | 2 |
| CMU Ballet `05_18` | Conflicting evidence families; abstained | Rejected | 0 | 0 |

The salsa decision was `control_fallback_no_contact_tempo`, with zero independent
model votes. Its accepted four-beat windows were approximately
0.90431–2.00776 s and 36.21466–37.31810 s. The first satisfied two inferred stance
constraints after correction; the second had no usable contact constraint in
its interval. Maximum translation corrections were approximately 2.34% and
10.50% of rest-body scale, with activity retention approximately 111.37% and
103.83%. Both passed decoded compiled-sample/wrap checks and native sampling.
Neither has musical, target-mesh or human seam approval.

The ballet result was `contradictory_families_abstained`, so the pipeline did not
manufacture a beat grid or automatically correct a beat-length loop. Explicit
control-only experiments can produce numerical loops under a supplied tempo
hypothesis; that does not override the consensus result. The benchmark command
above uses its existing 55–220 BPM search, so counts can differ from this wider
single-Action experiment. Results are development evidence, not a published
release or deployed viewer verification.

Source identities used in that validation:

- Salsa `60_01`: `39bd3f3b0e32b54437c0e45161a437d5719f09cb9105dfe37fb9310004ab497d`
- Ballet `05_18`: `70d1ed45aa696f2fd6ca5a02ea1ba7517fdd86ccf816e2757d055360de3c3cbf`

## Regression coverage

`tests/python/test_source_motion_completion.py` uses synthetic portable BVH
motion, a reviewed local ZIP and a Blender extraction index. With compatible
StemLab and the native extension available, it exercises actual world/event
binding, catalogue separation, derivative provenance, final-byte/fingerprint
binding, failed-compilation isolation, CLI validation and summary-only benchmark
outputs. It downloads nothing. Lower-level closure, quaternion, discrete-control,
contact-conflict and activity gates are in `test_loop_repair.py`; exact world
evaluation is covered by `test_world_motion.py`.

```sh
python -m pytest tests/python/test_source_motion_completion.py \
  tests/python/test_loop_repair.py tests/python/test_world_motion.py -q
```

Set `DANCERUDIMENTS_REQUIRE_STEMLAB=1` and
`DANCERUDIMENTS_REQUIRE_NATIVE=1` in an integration gate to make missing optional
runtimes fail visibly. Source-development checks and published-release
compatibility/deployment remain separate gates.
