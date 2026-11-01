# World-space motion and foot-contact evidence

`dancerudiments_authoring.world_motion` evaluates the actual captured joint
hierarchy **offline**, at the original capture timestamps. It supplies world
positions and motion/contact evidence to StemLab's existing motion analyser and
to the optional loop-finishing tools. The native Recording playback API, its
64-pip clock, profile channel numbers and source files are unchanged.

The evaluator supports `dancerudiments.skeletal-source-v1` profiles from the
original BVH importer and the Blender FBX/GLB/BLEND Action extractor. Those
profiles describe an evaluated, constraint-free carrier with explicit full
inheritance, bone rest matrices, root transform, complete quaternion groups and
explicitly omitted neutral transforms. The saved bone list can be in any order;
the evaluator resolves its hierarchy and rejects cycles, missing parents,
missing transforms and invalid rest matrices.

A **raw Rigify control capture** cannot be evaluated as though its control
locations were the final foot or joint locations. Its constraints, IK/FK choices
and internal deformation bones require Blender evaluation. This module raises
`UnsupportedWorldMotion` for that case; callers can retain control-space beat
analysis while reporting world-space evidence as unavailable. Extract the
evaluated source Action with the existing Blender importer to enable this route.

## Python API

```python
from hashlib import sha256
from pathlib import Path
from dancerudiments_authoring.motion_import import load_capture
from dancerudiments_authoring.recording import _write_json_document
from dancerudiments_authoring.world_motion import (
    analyze_world_motion,
    evaluate_world_motion,
)

source = Path("extracted/dance.capture.json")
capture = load_capture(source)
report = analyze_world_motion(
    capture,
    source_file_sha256=sha256(source.read_bytes()).hexdigest(),
    foot_bones=("LeftFoot", "RightFoot"),  # exact source bone names
)
_write_json_document("analysis/world-motion.json", report)

# Optional in-memory positions for exact source-frame diagnostics/loop finishing:
world = evaluate_world_motion(capture)
left_index = world.bone_names.index("LeftFoot")
left_positions = world.positions[:, left_index]  # read-only NumPy array
```

The source file digest binds a sidecar to the exact capture bytes. The report
also retains the parsed capture fingerprint, complete rig-profile fingerprint,
semantic type and original source-time bounds. Output names must be new when
using the existing JSON writer. `include_positions=True` optionally embeds all
joint trajectories in the report; it obeys an explicit JSON-size budget. Normal
reports contain only root trajectories, aggregate envelopes and foot evidence.
The in-memory evaluator also bounds its total world-matrix allocation.

## Kinematics and rhythm features

The evaluator reconstructs each bone as its parent's evaluated world matrix,
the saved relative rest transform, and its captured local TRS. Object motion
remains on the declared root. Quaternion signs have identical meaning, and small
unit-norm storage error is normalized as in the existing Blender apply bridge.
Nonuniform/reflected animated scales remain part of the source transform;
singular scales cannot supply a stable root-relative analysis and are rejected.

Features retain separate meanings:

| Evidence | Meaning |
| --- | --- |
| World joint speed | Motion of captured joint heads including root travel |
| Root-relative joint speed | Gestures with the root's full translation, rotation and scale removed |
| Root speed | Global movement reported separately from local gestures |
| Body-height proxy | Unweighted mean joint-head height; **not a mass-based centre of mass** |
| Kinetic minima | Source-frame local minima with surrounding movement support |
| Foot-plant/toe-off events | Changes in a low-height, low-speed contact hypothesis |

The world-speed, root-relative and height features are correlated descriptions
of the same capture. `family_lineage` makes that explicit; they must not become
multiple independent model votes. Motion extrema and foot contacts do not, by
themselves, establish musical beat one, meter or the correct half/double tempo.

The coordinate system is the portable carrier's right-handed **Z-up** space.
Positions remain in Blender/source units. The declared scene unit scale and
original coordinate metadata are retained, but a BVH's physical distance units
are never silently certified as metres. Relative thresholds use the saved rest
skeleton's bounding-box diagonal, or the declared bone length for a single-joint
source.

## Contact and slip hypotheses

Supply exact `foot_bones` when known. Otherwise the analyser uses explicitly
labelled foot/ankle-name hypotheses, falling back to toe names. It does not infer
an anatomical identity or ground surface from mesh geometry.

Each foot's low height quantile estimates its stance height. Contact requires
low height, low horizontal speed and low vertical speed for a minimum duration.
`ContactThresholds` exposes the positive tolerances and reports their exact
values. The defaults are 4% of body scale for height, 20% per second for both
speed limits, and 80 ms minimum duration. These are transparent heuristic
thresholds, not validated probabilities or a universal floor-contact model.

Intervals preserve the first and last observed contact samples, an anchor
position, maximum horizontal speed, relative drift and heuristic confidence.
Plant/toe-off events include their two-sample uncertainty interval. A contact
already held at the first frame does not invent a plant at the beginning; a
contact held at the final frame does not invent a toe-off. The separate
low-height stance drift metric exposes sliding even when excessive speed makes
the segment fail the contact gate.

Sampling gaps larger than three times the median source interval split the
evidence into separate `validity_segments_seconds`. Derivatives and contact
intervals never bridge those gaps. Original timestamps are unchanged; no missing
beat, pose or contact is fabricated.

The output marks `requires_review=true`, `contacts_verified=false` and
`musical_timing_verified=false`. Source skeletal geometry is sufficient for
these measurements, but does not prove target skin deformation, collision-free
motion or correct physical foot placement on Kandi Boom.

The song-loop preview builder uses this same evaluator for its bounded offline
source wireframes. It first loads a valid typed `RigMotion`, decodes the selected
normalized rows through the exact profile, and preserves their relative native
pip indices. Alphabetically ordered Blender skeletons retain their original
bone ordering. Invalid portable hierarchies or undeclared transforms fail;
unsupported control-rig semantics produce an explicitly labelled channel graph
and an unavailable-reason field instead of guessed joint positions. This
diagnostic view does not replace the Kandi native-WASM skin review.

## Verification

```sh
python -m pytest tests/python/test_world_motion.py -q
```

Synthetic tests check analytically known hierarchy/rest-basis transforms,
nonuniform and reflected scale, arbitrary skeleton order, root drift,
quaternion-sign invariance, alternating contacts at 30/60/120 fps, missing
semantics, temporal gaps, output identities and allocation bounds. With the
pinned `bpy` runtime available, a further check compares the complete evaluated
matrices against the actual Blender carrier at selected source frames, including
non-axis-aligned rest bases and animated root rotation.

Created by Kieran Simkin — https://kieransimkin.co.uk/my-songs/
