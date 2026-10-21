# Rigify model types and numbered control channels

DanceRudiments can describe and drive a generated Blender Rigify armature through
a versioned `dancerudiments.rig-profile`. A mesh bound to that armature deforms
through Blender's normal Armature modifier. The profile describes animator
controls; it does not replace skin weights, rig constraints or inverse kinematics.

The checked-in catalogue was extracted by **running Blender 5.2.2 LTS**, build
`d13f752e3b9c`, and generating its actual built-in rigs. It contains **8 metarig
presets and 28 component sample profiles**. Every entry has a hierarchical type
URL, a concrete numbered channel manifest and a SHA-256 fingerprint. The Blender
build, normalized Rigify Python-source digest and source URL are retained in each
profile. No third-party character mesh, motion recording or music is bundled.

## Complete metarig presets

| Blender model | Semantic type suffix after `syn://type/danceflow/motion/rigify/metarig/` | Channels |
| --- | --- | ---: |
| `human` | `human` | 1,967 |
| `Basic.basic_human` | `basic/basic_human` | 653 |
| `Basic.basic_quadruped` | `basic/basic_quadruped` | 799 |
| `Animals.bird` | `animals/bird` | 1,327 |
| `Animals.cat` | `animals/cat` | 2,379 |
| `Animals.horse` | `animals/horse` | 1,286 |
| `Animals.shark` | `animals/shark` | 579 |
| `Animals.wolf` | `animals/wolf` | 2,669 |

There are **11,659 channels across these eight preset manifests**. Numbers are
local to a profile: channel 265 in one model need not be the same parameter as
channel 265 in another. The profile type and fingerprint accompany the data.
`synny://` and `syn://` resolve to the same type identity; serialization uses
`syn://`. They are not two separate registries.

## Component samples

Rigify constructs complete metarigs from reusable component rig types. The
component profiles use `syn://type/danceflow/motion/rigify/component/` followed
by the dotted Blender name expressed as a path, for example `limbs/arm`.

| Component | Channels in the generated sample |
| --- | ---: |
| `basic.copy_chain` | 40 |
| `basic.pivot` | 20 |
| `basic.raw_copy` | 10 |
| `basic.super_copy` | 20 |
| `experimental.super_chain` | 70 |
| `face.basic_tongue` | 41 |
| `face.skin_eye` | 84 |
| `face.skin_jaw` | 132 |
| `faces.super_face` | 892 |
| `limbs.arm` | 113 |
| `limbs.front_paw` | 144 |
| `limbs.leg` | 146 |
| `limbs.paw` | 144 |
| `limbs.rear_paw` | 144 |
| `limbs.simple_tentacle` | 70 |
| `limbs.spline_tentacle` | 115 |
| `limbs.super_finger` | 52 |
| `limbs.super_limb` | 113 |
| `limbs.super_palm` | 14 |
| `skin.anchor` | 20 |
| `skin.basic_chain` | 38 |
| `skin.glue` | 20, in the explicitly declared containing-rig fixture |
| `skin.stretchy_chain` | 38 |
| `skin.transform.basic` | 20 |
| `spines.basic_spine` | 108 |
| `spines.basic_tail` | 69 |
| `spines.super_head` | 44 |
| `spines.super_spine` | 195 |

These are concrete upstream sample configurations, including their generated
root and containing controls. Changing chain length, component settings or the
metarig composition can change the controls; export a profile from the resulting
rig instead of assuming a sample's channel layout still applies.

`skin.glue` has **no independent animator control**: it connects to a skin control
created by another component. Its fixture adds a real `skin.anchor` at the glue
head, successfully generates both components and records their containing rig's
root/anchor channels. Both the catalogue and profile explicitly mark this context.
The channels are not represented as new controls created by glue. Similarly,
the default `basic.raw_copy` sample exposes its generated root while preserving
its deformation bone internally.

The catalogue also enumerates each component's **generation settings**—chain
segments, rotation-axis options and similar configuration. Those settings are
metadata, not animated control channels. They must be applied before generating
the rig. The runtime profile covers the generated result.

## Numbering and physical meaning

Each channel defines its stable **one-based number**, safe Recording dimension
name, exact bone name, Blender property path, array component, unit, minimum,
maximum, neutral value, value type and interpolation policy. Quaternion channels
retain Blender's **w, x, y, z** ordering. Euler controls retain the actual Euler
order chosen by Rigify; the bridge does not change a rig's rotation mode.
Integer selectors also retain their allowed numeric enum choices and labels.

For example, the shipped `Basic.basic_human` profile assigns:

| Channel | Exact control parameter |
| ---: | --- |
| 203–205 | `hand_ik.L.location` X, Y, Z |
| 206–209 | `hand_ik.L.rotation_quaternion` W, X, Y, Z |
| 210–212 | `hand_ik.L.scale` X, Y, Z |
| 265–267 | `root.location` X, Y, Z |
| 268–271 | `root.rotation_quaternion` W, X, Y, Z |
| 272–274 | `root.scale` X, Y, Z |
| 617 | `upper_arm_parent.L["IK_FK"]` |
| 619 | `upper_arm_parent.L["IK_parent"]` |
| 621 | `upper_arm_parent.L["pole_vector"]` |

These are exact assignments from the checked-in profile, not a generic humanoid
bone convention. The complete list is machine readable and can be exported to
CSV with the motion CLI.

Local location is measured in Blender units; the scene's `scale_length` is part
of the profile. Angles are radians and scales are dimensionless. Controls use
local pose/basis space relative to the retained bone rest matrices and hierarchy.
Armature-object animation is not captured as a bone channel; bake locomotion to
the rig's root control first when it is part of the motion.

The built-in transform ranges are ±10 Blender units for local translation,
±4π radians for Euler/axis-angle rotation and 0–4 for scale. Quaternion components
use −1–1. Numeric custom properties use their declared limits; custom enums use
the actual allowed choices rather than Blender's generic int32 storage range.
The exporter accepts explicit range overrides. A capture that exceeds its
profile's bounds fails visibly; it is never silently clipped.

The encoding into the existing normalized Recording contract is:

```text
encoded = 2 × (physical − minimum) / (maximum − minimum) − 1
physical = minimum + (encoded + 1) × (maximum − minimum) / 2
```

The existing float64/twelve-decimal contract remains in force. Quaternion groups
must form a unit quaternion, and native output is normalized when applied in
Blender to remove small numerical drift. Boolean/integer/enum channels use step
sampling and reject invalid intermediate values; float blends remain continuous.
Euler curves preserve their sampled winding. Correct discontinuous Euler wraps
in the source action before capture, or use an appropriate quaternion control.

Initial exports enumerate bones deterministically and their writable transforms
and numeric custom properties in fixed order. Re-export with `--previous` to
retain every existing channel number and append new bindings. Removed channels,
changed ranges or changed parameter semantics require an explicit new profile;
old recordings are not silently reinterpreted. Rest-pose changes also change the
fingerprint even when names and numbers remain identical.

## Export and capture a real character

The helper lives in the installable package as
`dancerudiments_authoring.blender_bridge`; `tools/blender_rigify_bridge.py` is its
checkout entry point. Capture and profile discovery use Blender plus the Python
authoring package. Native apply/bake additionally require a DanceRudiments
extension built for the Python ABI used by that Blender installation.

```sh
blender --background character.blend --python tools/blender_rigify_bridge.py -- export-profile --armature rig --model my_character --output my-character.profile.json
blender --background character.blend --python tools/blender_rigify_bridge.py -- capture-action --armature rig --profile my-character.profile.json --frame-start 1 --frame-end 241 --output my-character.capture.json
```

Use `--location-range`, `--rotation-range` and `--scale-max` on `export-profile`
when the character needs different explicit transform bounds. Use `--previous`
with a prior profile to preserve numbering when adding controls. A saved profile
fingerprints the actual rest matrices, modes, source version and unit scale, but
does not include the current pose or random Rigify instance ID. Applying to a
different rig fails with a fingerprint mismatch.

Capture accepts fractional `--frame-start`, `--frame-end` and `--frame-step`
values. It always retains the explicit last endpoint. `--sample-fps` selects an
explicit sampling rate instead of `--frame-step`, including subframes. Time zero
is the first captured frame; source frames, FPS and time origin are recorded in
provenance. Supply musical beat anchors relative to this origin when compiling
the capture. Captures are bounded by the existing scalar-count and file-size
limits; select an excerpt when a long, high-channel-count motion exceeds them.

## Import and retarget motion

```sh
blender --background --factory-startup --python tools/blender_rigify_bridge.py -- import-source dance.bvh --save dance-source.blend
```

The bridge delegates `.bvh`, `.fbx`, `.gltf` and `.glb` to Blender's own importers.
BVH import preserves the source FPS in the scene and updates its duration.
FBX/glTF may have fractional keyframe endpoints; choose explicit capture bounds
and sampling rates after retargeting. Imports retain their original skeleton
until an explicit retargeting/baking step maps them to the generated Rigify
**controls**. Bone-name copying is not sufficient to compensate for rest-pose
axes, scale, IK, poles or foot contacts. See [motion sources and tools](motion-sources.md).

After retargeting, export the exact destination rig's profile and use
`capture-action`; the regular motion compiler maps this capture to 64 pips per
beat. The adapter does not infer musical tempo or foot-contact events.

## Native playback and saved Blender actions

```sh
blender --background character.blend --python tools/blender_rigify_bridge.py -- apply --armature rig --motion dance.rig-motion.json --pip 64 --save pose-at-beat-one.blend
blender --background character.blend --python tools/blender_rigify_bridge.py -- bake --armature rig --motion dance.rig-motion.json --target-beat-map song-beats.json --frame-start 1 --save song-matched-character.blend
```

Both commands sample the existing native C++ recording engine. `apply` writes a
new one-pose Action, so the requested pose persists after reopening the file.
`bake` writes a new Action with a key at every recorded pip and explicitly sets
constant interpolation, retaining the integer-pip playback contract without
Bezier overshoot. It anchors the recording's first pip at `--frame-start`.
With `--target-beat-map`, each following pip uses the map's inverse beat-to-time
conversion; otherwise it uses the recording's nominal tempo.

The saved output uses the new Action at full replacement influence and disables
previous NLA evaluation, preventing accidental mixing with existing animation.
Previous Action and NLA data are retained. A failed operation restores the old
Action and animation settings. Output `.blend` paths must be new files.

The bridge never animates `DEF-`, `MCH-`, `ORG-` or visual helper bones directly.
It drives animator controls and lets the generated rig evaluate its constraints,
drivers and skin deformation. Mesh shape keys, arbitrary external feature-set
semantics and automatic universal retargeting are outside this profile contract.
For another Blender/Rigify version or a customized metarig, discover the actual
rig rather than assuming these pinned manifests remain valid.

## Reproduce the manifests and integration check

```sh
blender --background --factory-startup --python tools/blender_rigify_bridge.py -- catalogue --output-dir python/dancerudiments_authoring/rig_profiles
PYTHONPATH=python python -m unittest discover -s tests/python -p test_rigs.py -v
python tools/test_blender_rigify_bridge.py --output-dir .cache/rigify-smoke
```

The last command runs in a Python environment with `bpy==5.2.2` and the matching
compiled DanceRudiments extension. It builds an actual Rigify basic human,
captures synthetic movement, compiles beat samples, drives a weighted test mesh,
checks fractional capture and selector handling, bakes variable-tempo native
motion, reopens saved apply/bake outputs in fresh Blender processes to verify
their control values and skin deformation, and verifies the contextual glue
sample. It uses no third-party motion.

## Primary references

- [Pinned Blender 5.2.2 Rigify source](https://github.com/blender/blender/tree/v5.2.2/scripts/addons_core/rigify).
- [Rigify component model and generation stages](https://developer.blender.org/docs/features/animation/rigify/).
- [Blender Rigify rig types](https://docs.blender.org/manual/en/latest/addons/rigify/rig_types/index.html).
- [Blender Rigify metarig construction](https://docs.blender.org/manual/en/latest/addons/rigify/metarigs.html).
- [Blender PoseBone API](https://docs.blender.org/api/current/bpy.types.PoseBone.html).
- [Official bpy distribution](https://pypi.org/project/bpy/5.2.2/).
