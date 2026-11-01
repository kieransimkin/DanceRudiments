# Bounded offline finishing of source-motion loops

`dancerudiments_authoring.loop_repair` creates a **separate corrected capture**
from an explicitly selected interval of an original `RigCapture`. It closes the
pose and first/last sample tangents, measures the amount of correction, and can
validate or stabilize supplied foot-contact intervals. The original frames,
source timing, saved rig profile and numbered channels remain unchanged.

This is an authoring step before the existing native **64-pip** compiler. It
does not replace the runtime sampler or enable wrapping globally. A numerical
success remains a review candidate: musical phase, ground contact, target mesh
deformation and a final published loop still require their own evidence.

## Use with source analysis

```python
from dancerudiments_authoring.loop_repair import (
    LoopRepairOptions, contacts_from_world_report, propose_loop_repairs,
)
from dancerudiments_authoring.motion_import import load_capture, write_capture
from dancerudiments_authoring.world_motion import analyze_world_motion

capture = load_capture("source.capture.json")
world = analyze_world_motion(capture)  # exact saved portable source skeleton
contacts = contacts_from_world_report(capture, world, min_confidence=0.5)

options = LoopRepairOptions(
    root_policy="preserve",
    contact_policy="root_stabilize",  # explicit bounded root-only foot correction
    require_contacts=True,
)
candidates = propose_loop_repairs(
    capture, bpm=120, beat_zero_seconds=0.15,  # supplied hypothesis, not approval
    beat_counts=(4, 8, 16), max_candidates=4,
    options=options, contacts=contacts,
)
for index, candidate in enumerate(candidates):
    if candidate.accepted:
        write_capture(f"corrected-{index}.capture.json", candidate.capture)
    else:
        print(candidate.report["rejection_reasons"])
```

This helper ranks at most **128** beat-aligned windows spread across the source
and attempts at most `max_candidates` repairs, with an absolute maximum of 24.
It does not weaken the existing unmodified-loop seam filters. Its results belong
in a separate repaired-candidate catalogue. BPM and beat-zero remain explicit,
unverified inputs; they do not acquire stronger confidence through repair.

Each proposal uses exactly `beats * 64 + 1` inclusive endpoint samples. The
closing endpoint represents the start of the following cycle. Downstream native
compilation therefore uses **`beats * 64` samples**, leaving out that duplicate
endpoint. The reported tangent is measured on that same pip grid rather than
on a different low-resolution preview. Compiling under another sample/grid
interpretation requires rechecking its seam.

## Repair an explicitly selected interval

```python
from dancerudiments_authoring.loop_repair import FootContact, repair_loop

result = repair_loop(
    capture,
    start_seconds=2.0,
    end_seconds=4.0,
    options=LoopRepairOptions(sample_count=257),
    contacts=(FootContact("LeftFoot", 2.2, 2.6),),
)
```

`start_seconds`, `end_seconds` and contact intervals use the **original capture's
seconds origin**. The corrected capture uses local seconds `[0, end-start]`.
Its report and provenance retain the original bounds and original capture hash.
Source bounds and continuous coverage are enforced before resampling; no end
frames or missing sections are extrapolated. The shared
`world_motion.source_valid_segments(capture)` helper splits coverage whenever
an adjacent timestamp interval is strictly greater than three times the source's
median sample interval. This is the same rule used by world-space evidence and
requires neither a world sidecar nor NumPy. A direct `repair_loop` call whose
bounds cross a gap, or lie inside one, raises `ScoreError` before any pose is
interpolated. Proposals spend their bounded ranking budget only on windows
contained in a continuous segment; obtaining the skeleton scale also uses an
actual observed frame.

Nonuniform timestamps within that continuity threshold use the existing bounded
capture interpolation: linear scalar values, shortest-path quaternion SLERP and
held discrete controls. A single frame is a point `(time, time)` and cannot
support a positive-duration repair. Two frames alone provide no independent
sample interval from which to diagnose a gap. World evidence retains short
coverage segments but labels their zero velocity placeholders and infers no
accents or contacts when fewer than three frames support derivatives.

Invalid inputs raise `ScoreError`. A structurally valid interval that cannot be
finished within the declared limits returns `LoopRepairResult(capture=None,
report=...)` with explicit rejection reasons. No partial corrected capture is
returned for a failed candidate.

## What changes

For scalar controls, the shared seam value is the average of the two endpoints
and the shared tangent is the average of their inward/outward sample tangents.
For rotations, the endpoint midpoint and corrections use quaternion geometry;
`q` and `-q` always represent the same rotation. A full turn can therefore retain
opposite quaternion signs at physically equal endpoints without losing its
interior turn.

Compact cubic corrections act only within `blend_fraction` of each end. They
match the requested first two/last two samples exactly and have zero correction
and slope at the edge of their support. The middle of the original interval is
unchanged by seam finishing. This local construction minimizes the two endpoint
displacements and tangent discrepancies; it is not a global animation or
anatomical optimizer.

Discrete parent selectors, booleans and enums are never blended or repaired.
A mismatched selector at the repeat seam rejects the candidate. Euler winding
is preserved as supplied; a large scalar rotation correction that would erase a
turn is rejected by the rotation budget. Quaternion captures are appropriate
when a repeated full turn needs physically equivalent endpoint representations.

`root_policy="preserve"` performs no global drift removal. Bounded local seam
changes can still move the root near the boundaries. `root_policy="in_place"`
explicitly subtracts linear start-to-end travel from the selected root location
axes before seam finishing. Root travel is measured and included in the total
correction budget. The root comes from the saved portable hierarchy or an exact
`root_bone`; it is never guessed from a name. `root_axes` names profile-local
location components, not presumed world-horizontal axes.

## Correction and motion budgets

| Option | Default | Meaning |
| --- | ---: | --- |
| `blend_fraction` | 0.20 | Fraction at each end changed by local seam finishing |
| `max_rotation_correction_radians` | 0.45 | Largest quaternion geodesic/Euler-component correction |
| `max_translation_correction_fraction` | 0.15 | Largest translated control displacement divided by translation scale |
| `max_scalar_correction_fraction` | 0.08 | Largest other scalar change divided by its fixed profile range |
| `max_correction_rms_fraction` | 0.12 | RMS normalized correction across frames/control groups |
| `min_activity_retention` | 0.65 | Minimum retained motion activity compared with the same source interval |
| `max_activity_increase` | 1.60 | Upper bound preventing repair from injecting excessive movement |
| `min_activity` | 0.01 | Reject static/negligibly moving candidates |
| `max_contact_slip_fraction` | 0.02 | Maximum world-distance drift from a supplied stance anchor |
| `max_contact_speed_fraction_per_second` | 0.20 | Maximum foot speed while the supplied stance applies |
| `max_contact_root_correction_fraction` | 0.10 | Additional root-only stabilization budget |

The default distance scale is the validated portable skeleton's rest-joint
bounding-box diagonal, with the evaluator's declared single-bone fallback. Units
remain source units; no centimetre/metre assumption is introduced. An explicit
positive `translation_scale` overrides that scale. Captures whose skeleton
cannot be evaluated must supply a scale when translations change.

Activity sums per-control quaternion angular variation per second and normalized
scalar variation per second. It uses the same controls before and after repair.
For an explicitly in-place result its reference is measured after detrending
root travel; eliminating intended linear travel is not mistaken for removing
the dance. The numeric activity limits complement the correction limits; they
do not judge choreography, anatomy or visual appeal.

All corrected frames pass the original `RigProfile` physical range, unit
quaternion and discrete-control validation. Values are not clamped to make a
candidate pass. Endpoint pose and first-difference velocity must also meet their
declared tolerances after any contact correction.

## Foot contacts and world coordinates

`FootContact` records an exact bone name, an interval in original seconds, and
an optional world-space anchor. Without an explicit anchor, the first observed
point within that interval supplies one. Constraints are clipped to the chosen
window; zero-length or sub-sample overlaps are not treated as stance evidence.

`contacts_from_world_report(capture, report)` requires matching **capture and
profile SHA-256 identities**, a supported world-evidence schema, valid source
bounds and finite confidence. Its entries retain
`evidence="world_kinematic_hypothesis"`. Detected low-height/slow-motion stance
is not promoted to a verified foot plant.

With `contact_policy="validate"`, repaired foot trajectories are measured
against those anchors. Excessive drift or speed rejects the result. With
`contact_policy="root_stabilize"`, a bounded least-squares root translation
tries to satisfy active anchors without modifying bone lengths or adding a new
IK solver. World corrections are transformed through the saved root rest basis;
rotated roots are supported. Unconstrained intervals interpolate the required
root offset, and the offset is closed before applying it. Final residual slip,
speed, total correction and seam continuity are measured again.

Two simultaneous feet that demand inconsistent root corrections are rejected
as `conflicting_foot_contacts`. Corrections beyond the root budget or residual
sliding after closure also reject the result. This deliberately does not claim
to solve every planted-foot configuration; some need explicit target-rig IK or
a different source interval.

World-space constraints require an evaluated, reconstructible portable source
carrier. Raw constrained Rigify animator controls do not establish resulting
foot positions and are rejected for this operation. A successful numeric
constraint check sets `contacts.constraints_satisfied=true` while
`contacts.verified` and `contacts.foot_plant_verified` remain **false**. With no
usable intervals the report says contact evidence is unavailable; use
`require_contacts=True` to prohibit that case.

## Reports and provenance

`LoopRepairResult.report` uses `format="dancerudiments.loop-repair"`, schema 1.
The principal fields are:

| Fields | Meaning |
| --- | --- |
| `accepted`, `status`, `rejection_reasons` | Numerical result and explicit failed gates |
| `source_capture_sha256`, `source_profile_sha256` | Immutable original source/profile identities |
| `source_start_seconds`, `source_end_seconds`, `period_seconds` | Original interval and local output duration |
| `before`, `after` | Maximum angular, translational and normalized-scalar seam errors plus first-difference velocity jumps |
| `corrections` | Maximum angle, translation, normalized scalar and RMS changes |
| `activity_before`, `activity_after`, `activity_retention` | Measured motion preservation |
| `contacts` | Supplied evidence type, anchors, before/after slip and speed, numerical constraints satisfied |
| `root_travel_removed`, `root_bone`, `translation_scale` | Explicit root policy and physical scale |
| `repair_id`, `corrected_capture_sha256` | Deterministic repair settings identity and actual resulting capture hash |
| `proposal` | Optional beat count, supplied BPM/phase, ranking and bounded attempt metadata |

Successful reports set `status="numerically_closed_review_candidate"` and
`requires_review=true`. `loop_seam_approved`, `audio_beat_alignment_verified`
and `target_mesh_verified` stay false. The new capture's provenance nests the
original provenance and repair settings/results. Its own fingerprint appears
only in the external report to avoid a self-referential hash.

When packaging a compiled review clip, bind the external report to the exact
compiled motion bytes as well. The compiler's top-level `source_capture_sha256`
then identifies the **corrected** capture; the original capture identity remains
inside its nested source provenance. Keeping those two identities distinct
prevents a repaired clip from being represented as unchanged source motion.

Use `verify_compiled_loop_seam(motion, corrected_capture, repair_report)` before
export. It checks all final decoded Recording rows against the corrected capture,
their exact source/profile/repair identities and half-open extent. It appends the
first **compiled** row to measure the actual repeat tangent, then reevaluates
constrained foot trajectories after normalized encoding. Its
`dancerudiments.compiled-loop-check` report returns `passed`, rejection reasons,
maximum per-sample errors, wrap diagnostics and measured contacts. A changed
compile rate or phase therefore cannot keep a successful repair label merely by
retaining a provenance hash. The existing native execution check remains
separate; this helper verifies the final payload without inventing a playback
engine.

## Verification

`tests/python/test_loop_repair.py` covers source immutability, signed quaternion
equivalence and full turns, closure and tangent continuity, explicit root travel,
correction limits, held selectors, exact native pip compilation, sliding-foot
rejection, root stabilization, conflicting contacts, rotated rest bases and stale
evidence. Coverage tests reject timestamp holes before interpolation, retain
legitimate irregular sampling, bound proposal search to observed spans and
preserve isolated frames without inventing contact evidence. NumPy-dependent
world/contact checks use synthetic BVH fixtures.

```sh
python -m pytest tests/python/test_loop_repair.py tests/python/test_world_motion.py \
  tests/python/test_motion_import.py -q
```

The new authoring module is useful independently of source-motion inference;
neither StemLab nor a model download is needed to finish an explicitly supplied
window. StemLab remains the canonical owner of tempo/loop hypotheses, and
DanceRudiments retains its existing native playback contract.
