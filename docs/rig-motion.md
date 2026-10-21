# Rigify character motion on the DanceRudiments clock

This extension binds the existing native **N-dimensional Recording** to a
versioned Blender Rigify control profile. Each model has a semantic type URL;
each physical parameter has a fixed, one-based channel number. A compiled motion
retains the profile, source timing, provenance and normalized samples together.

The core authoring code is standard-library Python. Live playback still uses
C++ `SampledRecording` at **64 integer pips per quarter-note beat**. Blender is
the optional environment for importing, evaluating and driving a rigged mesh.
Existing XYZ patterns, the 1,731-pattern catalogue and their looping semantics
are unchanged. Rig motions are **non-looping** and reject out-of-range pips.

## Models and types

The checked-in inventory was generated using the actual **Blender 5.2.2 LTS**
Rigify implementation. It covers eight metarigs and 28 component types. The
[Rigify catalogue guide](rigify-catalogue.md) records the exact build, source
hashes, channel counts, component contexts and regeneration command.

| Rigify preset | Motion type |
| --- | --- |
| Human | `syn://type/danceflow/motion/rigify/metarig/human` |
| Basic human | `syn://type/danceflow/motion/rigify/metarig/basic/basic_human` |
| Basic quadruped | `syn://type/danceflow/motion/rigify/metarig/basic/basic_quadruped` |
| Bird | `syn://type/danceflow/motion/rigify/metarig/animals/bird` |
| Cat | `syn://type/danceflow/motion/rigify/metarig/animals/cat` |
| Horse | `syn://type/danceflow/motion/rigify/metarig/animals/horse` |
| Shark | `syn://type/danceflow/motion/rigify/metarig/animals/shark` |
| Wolf | `syn://type/danceflow/motion/rigify/metarig/animals/wolf` |

Component types have a parallel hierarchy, for example
`syn://type/danceflow/motion/rigify/component/limbs/arm` and
`syn://type/danceflow/motion/rigify/component/spines/super_spine`.
`synny://` URLs resolve to the **same identity** as their `syn://` equivalents.
The tree is an interchange convention; it does not add a Potbot dependency or
modify another repository's type registry.

Rigify's presets are configurable. A rig with edited proportions, extra bones,
different generation settings or another Blender build needs its **own exported
profile**. The model type can remain the same while its profile fingerprint
changes. Neither bone count nor matching names establishes rig compatibility.

## Numbered channel contract

A `dancerudiments.rig-profile` document declares:

| Field | Meaning |
| --- | --- |
| `type_uri`, `model`, `version` | Semantic model identity and explicit profile version |
| `channels[].number` | Persistent one-based parameter number; column index is `number - 1` |
| `name` | Unique Recording dimension name |
| `bone`, `data_path`, `array_index` | Exact Blender control and component to drive |
| `unit` | Blender units, radians, unitless values or other explicitly declared units |
| `minimum`, `maximum`, `neutral` | Physical range and neutral value |
| `value_type`, `interpolation` | Float, integer or Boolean; linear, quaternion or step behavior |
| `enum_items` | Valid numeric choices and labels for discrete enum controls, when present |
| `rotation_mode` | The actual generated control's Euler order, quaternion or axis-angle mode |
| `source` | Blender/Rigify identity, rest matrices, parents, locks and scene-unit metadata |

The initial export enumerates actual controls deterministically. When extending
an exported profile, `--previous` preserves the old channel numbers and appends
new parameters. Removed or changed parameter definitions fail rather than
silently reusing an old number. The explicit version and SHA-256 fingerprint
accompany every capture and motion. A fingerprint detects mismatched data; it is
not a digital signature or a guarantee that a source is trustworthy.

The generated manifests cover writable **animator control transforms and numeric
custom properties**, including IK/FK blends and parent selectors where present.
Rigify's internal `ORG-`, `DEF-`, `MCH-` and `VIS-` bones are excluded from direct
control. The existing rig evaluates its constraints and drives the bound mesh.
Static metarig-generation parameters are inventoried separately: segment counts,
widget choices and similar settings are not time-varying motion channels.

Local transforms remain in Blender's coordinate convention. Exported presets use
explicit bounds: location ±10 Blender units, Euler angles ±4π radians, scale
0..4, quaternion components −1..1, and custom properties' declared ranges.
These are encoding limits, not anatomical joint limits. Set suitable bounds when
exporting a real character, especially one with large root translation. Values
outside the chosen range fail; they are never silently clamped or independently
renormalized per clip.

Physical values encode into the existing bipolar Recording contract:

```text
normalized = 2 * (physical - minimum) / (maximum - minimum) - 1
physical = minimum + (normalized + 1) * (maximum - minimum) / 2
```

Every stored scalar remains finite float64 within `[-1,1]`, rounded to twelve
decimals. Quaternions are complete `w,x,y,z` groups and must have unit magnitude.
Boolean/integer selectors use held values, never fractional intermediate choices.
Quaternion interpolation uses shortest-path SLERP during compilation. Existing
Euler controls keep their actual rotation order and sampled winding; unwrap
source discontinuities before capture. The profile does not force Euler-based
Rigify controls into quaternion mode.

## Inspect or export the mappings

From a source checkout, the CLI works without installing a native extension for
inspection and authoring:

```sh
python tools/rig_motion.py catalogue
python tools/rig_motion.py profile human --output generated/human.profile.json
python tools/rig_motion.py channels generated/human.profile.json --output generated/human.channels.csv
python tools/rig_motion.py profile limbs.arm --kind component --output generated/arm.profile.json
python tools/rig_motion.py sources
```

After installing this source revision, `dancerudiments-rig` is the same command.
The catalogue JSON and all profile JSON files are shipped inside the Python
package. The CSV includes every numbered parameter; no XYZ truncation occurs.
Existing outputs are preserved unless `--overwrite` is explicit. Conversion
commands refuse output paths that are also their inputs.

## Import and capture real animation

The Blender bridge is available as the packaged
`dancerudiments_authoring.blender_bridge` module and through
`tools/blender_rigify_bridge.py`. The latter wrapper is useful with Blender's
`--python` command. Playback requires the native DanceRudiments extension for
the **Python ABI used by that Blender**. Authoring-only import/profile/capture
operations do not require the native extension.

First import a local file using Blender's supported interchange importers:

```sh
blender --background --python tools/blender_rigify_bridge.py -- import-source dance.bvh --save imported-source.blend
```

FBX and glTF/GLB are also accepted. This imports the recording's skeleton and
animation. Use an explicit retargeting workflow in Blender to map it onto the
chosen generated Rigify rig, correct the rest-pose/bone bases and root scale,
choose the appropriate FK/IK controls, and **bake the control animation**. Save
that result as, for example, `dancer-retargeted.blend`.

Export the exact character profile and capture its controls:

```sh
blender --background dancer-retargeted.blend --python tools/blender_rigify_bridge.py -- export-profile --armature rig --model my_dancer --output generated/dancer.profile.json
blender --background dancer-retargeted.blend --python tools/blender_rigify_bridge.py -- capture-action --armature rig --profile generated/dancer.profile.json --frame-start 1 --frame-end 121 --output generated/dance.capture.json
```

`--model` is your rig instance's stable descriptive identifier. `--kind metarig`
with the original model identifier is appropriate when preserving a preset's
model type. `--location-range`, `--rotation-range` and `--scale-max` choose the
export contract; modifying these later requires a new capture/profile identity.

Capture times are in seconds relative to the first selected Blender frame. The
source musical beat-zero offset must use **that same origin**. FPS and captured
frame range are retained in provenance. The bridge restores the previous scene
frame after capture. BVH import preserves its source FPS. Fractional frame bounds
allow precise imported endpoints; see `capture-action --help` for frame-step and
sample-rate controls.

The bridge reads baked control values. It does not infer a foreign skeleton's
mapping, embed arbitrary Python in motion JSON, or replace Rigify's constraints.
Object placement, mesh shape keys and third-party feature-set controls require
an explicit appropriate rig/profile integration; they are not silently inferred
from humanoid motion.

## Beat matching and compilation

A `dancerudiments.rig-capture` stores physical frame values and timestamps without
binding them to music yet. A source `BeatMap` supplies strictly increasing
`(seconds, beat)` anchors, or a constant BPM plus a separately supplied beat-zero
time. There is no automatic tempo estimate or first-beat guess.

```sh
python tools/rig_motion.py compile generated/dance.capture.json generated/dance.motion.json --name dance_phrase --source-bpm 100 --source-beat-zero 0.18 --bpm 124 --samples 512
```

That example creates an eight-beat grid (512 pip rows). It requires sufficient
source motion after its 0.18-second beat origin. At every absolute output pip `p`:

```text
source_beat = source_beat_offset + motion_rate * p / 64
source_seconds = source_beat_map.inverse(source_beat)
```

`--source-beat-offset` selects a source excerpt. `--motion-rate 1/2` uses half a
source beat per playback beat; `2` uses two. `--start-pip` is an absolute output
beat position, including negative pickups; it is not an independent clip-local
offset. For a desired source beat `s` at start pip `p0`, use
`source_beat_offset = s - motion_rate * p0 / 64`.

For drifting tempo or manually marked motion accents, use
`--source-beat-map beats.json` instead of `--source-bpm`/`--source-beat-zero`.
Anchors interpolate linearly in accumulated beat position; the inverse maps back
to source time. A measured map is bounded unless extrapolation is explicitly
enabled. Source frame bounds are always enforced. There is no automatic looping,
endpoint extension, foot-plant correction or seam repair.

`--bpm` records the **nominal target tempo** for standard Recording compatibility.
The compiled samples are indexed by musical position and can subsequently play
under a different fixed or variable target tempo. The original source tempo map
is retained separately in provenance; it is not replaced by the target BPM.

## Native playback and Blender baking

```python
from dancerudiments_authoring import BeatMap, load_rig_motion

motion = load_rig_motion("generated/dance.motion.json")
player = motion.player()  # actual C++ SampledRecording
values = player.sample(64)              # physical values in channel order
numbered = player.by_channel(64)        # {one_based_channel_number: value}
target = BeatMap.from_bpm(124, beat_zero_seconds=0, source="song tempo")
values_at_time = player.sample_time(0.5, target)
```

The target transport determines each pip from **absolute** audio time. A variable
tempo map integrates successive beat intervals instead of multiplying all
elapsed time by the latest BPM. Repeated seeks do not leave an accumulated phase.
`pip_at()` uses floor for negative positions. There is no Python playback fallback
when the native extension is missing.

To apply a native sample or bake the whole motion into a new Blender Action:

```sh
blender --background dancer-retargeted.blend --python tools/blender_rigify_bridge.py -- apply --armature rig --motion generated/dance.motion.json --pip 64 --save posed.blend
blender --background dancer-retargeted.blend --python tools/blender_rigify_bridge.py -- bake --armature rig --motion generated/dance.motion.json --action-name DanceRudimentsDance --save danced.blend
```

`bake --target-beat-map beats.json` supplies a variable target tempo. The output
frame start anchors the recording's first pip; subsequent pip times use the
target map's inverse. Without a target map, the recording's nominal fixed tempo
sets spacing. This places a clip at `--frame-start`, including for negative or
nonzero starting pips, rather than preserving the original transport's absolute
beat-zero time. Baked keyframes use constant interpolation to retain the exact
integer-pip contract. Any smoother rendering is an explicit consumer choice.
`apply` creates a one-pose Action so the requested pose survives reopening the
saved scene. Both output operations use full-influence replacement and disable
NLA evaluation for that armature; previous Actions and NLA data are retained.
Output `.blend` files must be new paths. Rig/profile mismatches fail before
applying values.

## Interchange and existing consumers

`dancerudiments.rig-motion`, schema 1, contains `type_uri`, `profile_sha256`,
`profile` and an unchanged `dancerudiments.recording` schema-1 document. Loaders
reject unknown fields, duplicate JSON keys, non-finite values, invalid discrete
controls/quaternions and mismatched columns or profile hashes.

```sh
python tools/rig_motion.py inspect generated/dance.motion.json
python tools/rig_motion.py recording generated/dance.motion.json generated/dance.recording.json
```

The extracted recording works with the existing native C++/Python N-dimensional
sampler and shared recording harness. Its bar view can inspect all normalized
channels. It is not a mesh viewer. The typed Python layer performs physical-unit
decoding and target-profile checking. Existing C#/TypeScript XYZ wrappers remain
unchanged; this update does not claim new typed mesh renderers in DanceMoves or
FrameRudiments.

The existing recording bounds apply: at most **8,388,608 scalar values** and
**64 MiB JSON** per document. Long full-body recordings may require explicit
excerpts. No channel is discarded to make a file fit. Native sampling can run
without Blender; evaluating a full Rigify constraint rig requires Blender or a
separately implemented consumer capable of the same rig semantics.

## Examples, tests and next imports

The [synthetic quickstart](../examples/rig-motion/README.md) produces a capture,
source beat map and typed motion, then optionally samples it through C++ under a
variable tempo. It contains no third-party choreography or music.

```sh
python -m pip install .
python -m unittest discover -s tests/python -p 'test_motion*.py' -v
python -m unittest discover -s tests/python -p 'test_rig*.py' -v
python examples/rig-motion/quickstart.py --output generated/rig-example --native
```

The dedicated Rigify workflow installs the pinned official `bpy` runtime and
checks an actual generated armature, native sampling, skin deformation and
save/reopen persistence. Its synthetic BVH, FBX and GLB importer fixtures also
verify source timing, fractional capture endpoints and retained skin bindings.
See [motion-source research](motion-sources.md) for 100STYLE, CMU, Mixamo,
Rokoko, AIST++, AMASS, LaFAN1, Motorica and animal-motion candidates, with separate
format/access/licence notes. Dataset-specific SMPL conversion, general automatic
retargeting, automatic beat inference, contacts and loop/transition repair remain
future adapters rather than implied capabilities of this first implementation.
