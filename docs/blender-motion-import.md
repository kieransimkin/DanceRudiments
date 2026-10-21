# Import source skeletons and map explicit FK controls

The optional Blender authoring module can extract individual recorded Actions
from local **BVH, FBX, glTF/GLB and BLEND** files. It preserves the source skeleton
under a distinct `syn://type/danceflow/motion/skeletal/source/...` identity.
Generating a source profile does not turn that skeleton into a Rigify rig.

The implementation is `dancerudiments_authoring.blender_import`; the checkout
wrapper is `tools/blender_motion_import.py`. Importing, extracting and retargeting
are offline operations. Playback continues to use native `SampledRecording`
through `RigMotion.player()`, with 64 integer pips per beat. No downloaded motions
are added to the default catalogue or automatically loaded into a website.

## Inspect and extract a local file

Run these commands in a dedicated Blender process, or with a Python environment
containing the pinned official `bpy` runtime:

```sh
blender --background --factory-startup --python tools/blender_motion_import.py -- inspect character.glb --output inspected.json
blender --background --factory-startup --python tools/blender_motion_import.py -- extract character.glb --source-id my_character --output-dir extracted --sample-fps 30
```

The inspector lists armatures, Action names, slots, source frame ranges, animated
bone/property paths and rejected candidates. An existing Action/slot or NLA
association establishes ownership. Otherwise an unbound Action must contain
bone paths that resolve on the selected armature. Object-only animation needs
an existing association. This avoids applying an unrelated camera Action to a
character simply because it contains location curves.

Select specific `--armature NAME`, `--action NAME` or `--binding-id ID` values
from the report; each option may be repeated. BLEND files with multiple scenes
require an explicit `--scene NAME`. Embedded scripts are not executed. Original
files are preserved, and output paths must be new.

Each successful extraction writes a `.capture.json` and `.profile.json` pair.
`index.json` records source file SHA-256, importer options, exact Action/slot,
frame count, channel count, duration, relative output names and unsupported
animation. `--continue-on-error` retains successful captures and records failures;
the process returns status 2 if any selected Action failed. A failure without
that option stops the batch and writes the partial index. The importer does not
download assets or infer permission from file format.

### Source time and coordinate conventions

The scene's effective `fps / fps_base` converts frames to seconds. BVH import
preserves the source FPS. glTF timestamps may produce fractional Blender frame
positions; those endpoints are retained. The shared Action range includes all
its slots, including an animated parent object's lead-in or final key. NLA
strip scaling, repeats and blending are not applied when extracting an
individual Action.

`--sample-fps` selects an explicit sampling rate. Omitting it uses the imported
scene's rate. `--frame-start` and `--frame-end` select a finite excerpt inside the
Action; they do not extrapolate choreography. The final endpoint is retained
even when it falls between regular samples. The first captured frame becomes
time zero, with original frame bounds and rate retained in provenance.

There is **no assumed musical BPM or phase**. Compile the resulting capture with
the existing rig-motion compiler and explicit source beat annotations. A pack
may use a declared time-only 60-BPM coordinate so one beat represents one second;
that is a duration convention, not evidence that the dance was performed at
60 BPM. See [rig-motion compilation](rig-motion.md#beat-matching-and-compilation).

BVH accepts explicit `--axis-forward`, `--axis-up` and `--global-scale` options.
The defaults match Blender's BVH importer: `-Z`, `Y` and `1`. BVH files do not
establish a physical unit. FBX uses its importer and embedded coordinate metadata,
with an optional `--global-scale`. glTF and BLEND keep their declared transforms;
source-axis overrides and a source import scale are rejected for those formats.
glTF external buffers/textures are not included in the main file's SHA-256; use
the original dependency set or a self-contained GLB when distributing an asset.

## Portable source profile and native playback

The source carrier has the original named hierarchy and bone rest matrices,
plus an explicit synthetic root containing the armature object's evaluated
world transform. Every source bone is considered, including fingers and bones
with Rigify internal prefixes. Object parenting, constraints and bone inheritance
are evaluated by Blender and baked into local translation, unit quaternion
`w,x,y,z`, and scale values on a constraint-free carrier.

The profile stores the portable skeleton as a list of names, parents, row-major
rest matrices, lengths and deform flags. Carrier inheritance is explicitly full
scale, inherited rotation and local location, and its object transform is
identity. A pure BVH decoder may use the actual root joint instead of a synthetic
object root. It can choose identity joint rest rotations while preserving exact
joint offsets; displayed bone-tail direction is then a visualization convention.

Only transform groups that remain neutral within the declared tolerance are
omitted. The default tolerance is `1e-6`; set `--neutral-tolerance 0` to retain
all numerical differences. Every omitted group and its neutral values are stored
explicitly. Constant non-neutral groups remain recorded, and quaternion groups
are always complete. The adapter expands omitted groups during pose application,
so switching from a previously posed rig cannot leave stale values behind.
Each compact profile has its own exact fingerprint and numbered channel list;
do not reuse a channel number from a different profile merely because the source
skeleton type is the same.

For a package containing several Actions on that same source skeleton, use
`union_source_profile(capture.profile for capture in captures)` and then
`rebind_source_capture(capture, union_profile)` for each capture. The union
preserves the first profile's channel IDs and appends missing bindings in a
deterministic order. Rebinding expands only the explicitly declared neutral
groups; it cannot discard movement or change a channel's units or bounds.
Different skeletons, rest bases, import options or physical bounds need separate
packages. This explicit conversion gives every clip the exact profile expected
by the optional package loader without padding every source bone to ten channels.

Physical bounds are fixed options, not fitted independently to each Action:
locations default to ±10,000 Blender units, scales to ±100, and quaternion
components to ±1. Negative scale can represent an actual source reflection.
Out-of-range values fail. Matrices containing shear that local TRS cannot
represent also fail instead of being silently approximated. The existing scalar
budget is checked before allocating dense sampled rows; choose an excerpt or
lower explicit sample rate when necessary.

Create a compatible armature from a profile without requiring the original rig:

```sh
blender --background --factory-startup --python tools/blender_motion_import.py -- create-carrier extracted/CLIP.profile.json --name source_carrier --save source-carrier.blend
blender --background source-carrier.blend --python tools/blender_rigify_bridge.py -- apply --armature source_carrier --motion compiled.motion.json --pip 64 --save sampled-source.blend
```

The carrier supplies the skeleton, not mesh geometry. Keep a licensed source mesh
and its rest-space skinning data with an optional asset package if a renderer
needs them. The existing native `apply` and `bake` bridge commands accept source
profiles, validate the carrier's actual rest basis and hierarchy, expand declared
neutral groups and save a new Action. They preserve prior actions and prevent
old NLA blending from contaminating the saved result.

B-Bone segment curvature and mesh shape keys are reported as unsupported
deformations. Their skeletal bone transforms can still be captured, but the
carrier does not reproduce those additional deformations. Animated dependencies
outside the selected Action are rejected by default. Use
`--allow-scene-dependencies` only after choosing the intended scene context; the
dependency names are then retained in provenance.

## Rebuild the optional Quaternius Robot package

`tools/import_quaternius_robot.py` is a complete source-to-package example using
the general APIs above. Supply the original public ZIP from the creator's
[Animated Lowpoly Robot page](https://opengameart.org/content/animated-lowpoly-robot).
The recipe verifies its exact SHA-256 and the original BLEND, FBX and licence
members before opening Blender data. It has no downloader. The package contains
14 original Actions, including the dance, under the CC0 licence preserved in the
archive; the equivalent FBX motions are not counted a second time.

With the pinned `bpy==5.2.2` environment and matching native extension installed:

```sh
python tools/import_quaternius_robot.py --archive Animated_Robot_Oct_2018.zip --work-dir robot-import --output-dir optional-packs/quaternius_robot/1.0.0 --package-archive quaternius_robot-1.0.0.zip
```

All output paths must be new. The work directory retains the exact source
archive, licensed source mesh files, captures and verification report. The
optional motion package contains the union profile, 14 compressed recordings,
source hashes and notices, and stays separate from the default catalogue. Its
178 numbered channels retain the source skeleton and fingers. Every compiled
pip is checked through the native sampler before a package ZIP is produced.

The explicit 60-BPM coordinate preserves elapsed time; musical tempo and phase
remain unverified. To reproduce an earlier package's exact ingestion provenance,
pass `--source-record PATH/TO/SOURCES.json` from that package. The recipe verifies
all source identity fields and retains the original date record. A later run
without that option records the recipe's source verification date, without
claiming that it downloaded a file.

## Explicit Rigify FK mapping

The retargeter provides an explicit FK adapter, verified with a generated Basic
Human Rigify rig and a skinned mesh. It does not infer a bone map from names or
claim to solve IK poles, foot contacts, collision repair, missing fingers or
facial morphs.

First export the exact target rig's normal Rigify profile. Then supply a
`dancerudiments.fk-map` schema 1 JSON document with these fields:

| Field | Required meaning |
| --- | --- |
| `source_type_uri` | The exact portable source skeleton type |
| `target_profile_sha256` | The exact exported target Rigify profile fingerprint |
| `source_reference_object_matrix` | Explicit rigid 4×4 reference object transform, row-major; it establishes the source's rest coordinate basis |
| `source_to_target_rotation` | Explicit unit quaternion in `w,x,y,z` order aligning source motion directions with the target |
| `root_translation_scale` | Positive, explicit root distance scale; never inferred from an arbitrary bone length |
| `bones` | Entries with exact `source`, `target`, `rotation` and `translation` fields; flags are Boolean and targets are unique |
| `setup` | Explicit `{ "channel_number": ..., "value": ... }` entries, including required IK/FK switches |

The source reference matrix and alignment quaternion are separate choices. The
first removes the source object's declared reference orientation/placement when
forming rest-relative deltas. The second aligns those deltas with the target.
An identity reference is appropriate only when that is the intended source
reference. Scale belongs in `root_translation_scale`, not in the reference matrix.

For each mapped joint, the adapter computes the source's evaluated orientation
relative to its rest basis, aligns that rotation, and applies it to the target
control's rest orientation. Controls are solved in parent order using Blender's
[pose/local matrix conversion](https://docs.blender.org/api/5.2/bpy.types.Bone.html#bpy.types.Bone.convert_local_to_pose).
One mapping may transfer root translation. Source scale animation remains in the
source capture; target FK scales retain the explicit target baseline. Existing
target rotation modes and numbered property bindings are preserved. A constraint
that prevents reaching the requested control orientation causes an error.

```sh
blender --background --factory-startup --python tools/blender_motion_import.py -- retarget source.capture.json --target-blend dancer.blend --scene Scene --target-armature rig --target-profile dancer.profile.json --mapping source-to-rigify.json --output rigify.capture.json
```

The output capture uses the exact target Rigify profile. Its provenance includes
the complete mapping, source capture/profile hashes, fixed setup channels,
unmapped source bones, unmapped target channels and measured control orientation
error. Unmapped target controls retain their explicitly documented neutral/setup
baseline; they are not presented as captured source movement. The operation
restores the original target pose and animation assignment after authoring.

## Reproducible verification

```sh
python tools/test_blender_motion_batch.py --output-dir .cache/blender-motion-batch
python tools/test_blender_motion_imports.py --output-dir .cache/blender-imports
python tools/test_blender_rigify_bridge.py --output-dir .cache/rigify-bridge-smoke
```

The new regression creates its own two-action BLEND fixture, non-aligned bone
rest axes, finger motion and object root translation. It compares evaluated
source/carrier matrices, verifies fractional multi-slot parent animation, checks
unresolved dependency rejection, and performs explicit FK retargeting to a real
generated Basic Human. Native pose application is saved and reopened in a fresh
Blender process, where actual skinned vertex positions are checked. No external
assets are downloaded by these tests.
