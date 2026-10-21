# Motion sources and import routes

Reviewed **21 October 2026** against the primary sources linked below. This is a
research index, not a bundled motion library or a blanket permission to use every
asset. No third-party motion, music, character mesh or model weights are included.
The matching machine-readable index is
[`motion_sources/manifest.json`](../python/dancerudiments_authoring/motion_sources/manifest.json).

## First working route

Use a local recording that you own or have permission to use:

1. Import its **BVH, FBX or glTF/GLB** animation into Blender using Blender's
   importers. Preserve source sample timing, units, axis convention, skeleton and
   rest pose. BVH provides a skeleton and animation; it does not provide a mesh.
2. Generate the chosen Rigify rig and bind the character mesh. Retarget the source
   motion onto the generated rig with an explicit bone map, rest-pose correction
   and root translation scale. Verify the chosen FK/IK controls and bake their
   animation. Renaming bones or copying Euler values does not perform this step.
3. Capture the **generated rig's control transforms and animatable custom
   properties** using its frozen channel manifest. This preserves the identity of
   each parameter independently of source bone names or enumeration order.
4. Supply source musical timing: confirmed/estimated BPM plus the first-beat
   offset, or explicit `(beat, source_seconds)` anchors. Keep tempo provenance
   separate from phase provenance. Crop/loop decisions must also be explicit.
5. Compile those channel frames onto DanceRudiments' **64-pips-per-beat** clock and
   play the result through the shared native N-dimensional recording sampler.
   The rig binding decodes each channel back into the declared physical unit.

The source skeleton, retargeted rig, mesh and music are distinct assets. A BVH
importer is not a Rigify retargeter, and a Rigify channel profile does not supply
missing choreography. The core library remains independent of Blender; Blender
is the optional import, rig evaluation and baking environment. See the existing
[recording contract](recordings.md) for native playback and bounds.

Capture uses explicit Blender frame positions at the scene's effective frame
rate (`fps / fps_base`) and sets **the first captured frame to local time zero**.
Fractional frame boundaries and steps are supported; `--sample-fps` selects an
explicit sampling rate. Imported glTF keys can fall at fractional Blender frames
because glTF stores timestamps in seconds. Preserve those boundaries when
capturing, and express the source beat-zero offset relative to the resulting
capture, including any trimming offset. Do not silently round the original phase
or assume the scene's default frame range is the clip range.

## Source comparison

| Source | Available motion and formats | Timing and practical import route | Use and redistribution constraints |
| --- | --- | --- | --- |
| [100STYLE](https://www.ianxmason.com/100style/) | 100 human locomotion styles, BVH; author also links a retargeted FBX/BVH version. | 60 fps, 28-bone skeleton; supplied trim-frame CSV. No musical beat map documented. Good first BVH source for locomotion, idles and transitions. | Author states [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), including creative/commercial work with credit. Preserve attribution and indicate modifications. |
| [CMU Graphics Lab](https://mocap.cs.cmu.edu/) | Human dance, locomotion and general activities. Original ASF/AMC and marker data; the [official resources page](https://mocap.cs.cmu.edu/resources.php) links BVH/FBX conversions. | Retain each recording's rate; no universal source beat map established. Use a documented conversion or convert before the Blender route. | Homepage permits inclusion in commercially sold products but prohibits selling the motion data itself, even converted. General raw-file redistribution permission was not independently verified. Credit requested; check conversion-specific additions and terms separately. |
| [Mixamo](https://www.mixamo.com/) | Bipedal humanoid character/animation library, including dance; FBX export. | Adobe ID and user download. Record source tempo and phase yourself; no beat-labelled public API established. Retarget downloaded FBX in Blender. | [Adobe FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html) permits royalty-free personal/commercial/nonprofit projects. It is not an open-data licence; that FAQ does not establish general raw-file redistribution rights. Keep clips as user-supplied assets. |
| [Rokoko free pack](https://www.rokoko.com/resources/download-263-rokoko-motion-capture-assets) | Official collection of 263 motion assets; FBX variants for Mixamo, UE4, UE5 and HumanIK skeletons. | 30 fps; no beat metadata documented. Obtain through the official download page, then retarget locally. | Page explicitly permits commercial projects. General raw-file redistribution rights are not established there; retain the downloaded pack's terms and import as user-supplied data. |
| [AIST++](https://google.github.io/aistplusplus_dataset/factsfigures.html) | 1,408 human dance sequences across 10 genres, represented by SMPL joint rotations/root trajectories; [`.pkl` annotation format](https://google.github.io/aistplusplus_dataset/download.html). | Exact 60 fps; paired music and published source BPMs. Needs a format adapter, calibrated skeleton/rest pose and phase. Python pickle requires a trusted conversion environment, not automatic loading of arbitrary files. | Google annotations are CC BY 4.0. Original AIST [music/video terms](https://aistdancedb.ongaaccel.jp/terms_of_use/) are academic-research-only unless permission, with application and no unauthorised redistribution. SMPL model files have separate terms. Do not combine these into one permissive licence claim. |
| [AMASS](https://amass.is.tue.mpg.de/) | Broad human motion collection in common SMPL-family body-model parameterisation. | Registration and per-dataset downloads; rates vary. Needs an adapter and separate source beat annotations. | [Licence](https://amass.is.tue.mpg.de/license.html) limits use to noncommercial research, education or artistic projects and prohibits redistribution. Commercial use requires separate permission. |
| [LaFAN1](https://github.com/ubisoft/ubisoft-laforge-animation-dataset) | 77 BVH sequences, including eight dance sequences, locomotion, falls, sports and transitions. | 30 fps; Git LFS archive; no beat stream documented. Useful research comparison for transitions. | [CC BY-NC-ND 4.0](https://github.com/ubisoft/ubisoft-laforge-animation-dataset/blob/master/license.txt): noncommercial and no sharing adapted material. Do not bundle retimed/retargeted derivatives under the project's code licence. |
| [Motorica Dance Dataset](https://github.com/simonalexanderson/MotoricaDanceDataset) | BVH hip-hop, popping, locking, krumping, jazz, Charleston, tapping and casual dance; finger coverage varies by session. | Associated music or audio features; source describes possible capture/synchronisation errors. Verify clip rate and alignment. | Repository terms permit research use; commercial/non-research use and redistribution require permission. Music copyright is separate. Optional private research import. |
| [AI4Animation quadruped data](https://github.com/sebastianstarke/AI4Animation) | Dog/quadruped motion and locomotion research, with a [dedicated quadruped project](https://github.com/sebastianstarke/AI4Animation/blob/master/AI4Animation/SIGGRAPH_2018/ReadMe.md). | Gait motion rather than paired dance music; inspect the selected source asset's format, rate and skeleton. | Repository identifies mocap as CC BY-NC 4.0 and restricts project use to research/education. Check asset-specific terms; not a general commercial animal-motion source. |

**Recommended order:** use 100STYLE/CMU to exercise import and retargeting, then
user-downloaded Mixamo/Rokoko dance clips, then an AIST++ adapter for music-linked
dance research. AMASS, LaFAN1 and Motorica are optional research sources with
material restrictions. A format being readable does not establish usage rights.

## Beat matching

The target transport supplies an **absolute integer pip**. It must derive that
position from absolute song time and the target tempo map, rather than adding a
rounded increment each render frame. The motion compiler samples source motion
at the corresponding musical beat; native playback reads the resulting pip row.
Source interpolation belongs in this offline compilation step, not a second
Python or JavaScript playback engine.

Between source anchors `(b0, t0)` and `(b1, t1)`, linear beat-to-source-time mapping
is `t = t0 + (b - b0) * (t1 - t0) / (b1 - b0)`. For fixed source tempo, the same
mapping follows from BPM and a separately supplied beat-zero time. Rotation
samples require quaternion interpolation as a group; scalar interpolation of
quaternion components or Euler wrapping can distort the pose. Discrete controls
use step interpolation.

[AIST's music table](https://aistdancedb.ongaaccel.jp/database_structure/) supplies
useful source tempo metadata: music suffixes `0` to `5` denote 80, 90, 100, 110,
120 and 130 BPM for the listed non-House genres; `mHO0` to `mHO5` denote 110, 115,
120, 125, 130 and 135 BPM. These values **do not establish a clip's first-beat
phase**, especially after trimming. They are metadata for a future adapter, not
an automatic AIST download/import feature.

No automatic inference of musical beats from arbitrary mocap is claimed. For
clips without music, users can author beat anchors deliberately. Foot contacts,
movement accents and musical downbeats are different annotations. Beat matching
alone does not solve foot sliding, collisions, loop seams or pose transitions.

Most listed sources are human. They cannot fill a bird's wings, a cat's tail,
facial controls or absent finger motion. A complete Rigify profile inventory must
not be described as a complete motion library or universal cross-species
retargeter. Unmapped controls need an explicit rest/default/omission policy.

## Existing import and retargeting tools

- **Blender:** use the [built-in interchange pipeline](https://www.blender.org/features/pipeline/)
  and [BVH importer](https://docs.blender.org/manual/en/latest/files/import_export/bvh.html).
  [Blender 5.0's notes](https://developer.blender.org/docs/release_notes/5.0/pipeline_io/)
  recommend `bpy.ops.wm.fbx_import` over the older `bpy.ops.import_scene.fbx`;
  capability-check when supporting multiple versions.
- **Rokoko Blender plugin:** the [official repository](https://github.com/Rokoko/rokoko-studio-live-blender)
  documents source/target selection, bone-map review, matching rest poses and
  scaling. Its [retargeting guide](https://support.rokoko.com/hc/en-us/articles/4410463481489-Retarget-an-animation-in-Blender)
  says retargeting is free. Evaluate compatibility and the plugin's source licence
  before adopting it; this update does not vendor or silently install it.
- **Three.js:** [`BVHLoader`](https://threejs.org/docs/pages/BVHLoader.html) yields
  a skeleton and animation clip (single-root BVH), and
  [`SkeletonUtils.retargetClip`](https://threejs.org/docs/pages/module-SkeletonUtils.html)
  provides mappings, scaling and local offsets. Useful for browser consumers;
  these tools do not evaluate Rigify's Blender constraint/custom-property rig.
- **ufbx:** the [upstream loader](https://github.com/ufbx/ufbx) offers FBX animation
  evaluation, layers, skinning and blendshapes under MIT or Unlicense. It is a
  possible independent importer later; using Blender first avoids adding a new
  native parser dependency to the core package.

Keep reusable timing and recording changes in DanceRudiments. StemLab remains
the existing audio-analysis producer, and consumers should use the shared native
recording API instead of copying a motion sampler. This research does not require
changes to unrelated DanceFlow tools, model downloads or training.
