# Kandi Boom motion demo

The `meshes/` route is the production 3D character demonstration for
DanceRudiments. It renders **Kandi Boom** from *Bass Ben & Friends* using the
checked-in FBX, skeleton and four PBR texture maps. Two separately packaged CMU
motion-capture performances can be loaded on demand and retargeted to Kandi's
verified 24-bone source rig.

| Character | Performance | Source recording | Source duration |
| --- | --- | --- | ---: |
| **Kandi Boom** | Salsa | CMU `60_01` | about 37.37 s at the reviewed 60 fps timing |
| **Kandi Boom** | Ballet sequence: attitude, arabesque, turning jump and back bend | CMU `05_18` | about 15.24 s at approximately 120 fps |

The internal motion-package slot IDs remain `boxbot` and `prism` for compatibility
with the already reviewed source-recipe identities. They are not character names
and are not exposed as rendered characters. Both slots target the same Kandi Boom
FBX at runtime.

## Asset and rig identity

The canonical target assets live under `harness/kandi-boom/assets/`. The release
builder verifies their SHA-256 identities against `harness/kandi-boom/rig-audit.json`
and verifies `harness/kandi-boom/source-rig.json` before copying anything into the
site. The target rig type is:

`syn://type/danceflow/motion/rig/custom/kandi-boom`

The source audit established a 24-bone humanoid skeleton, one skinned mesh,
29,965 triangles and complete skin coverage. The original FBX has vertices with
more than four influences. The canonical FBX remains untouched; Three.js/WebGL's
standard four-weight GPU path is treated as an explicit runtime approximation.
The browser integration normalises every runtime weight set and fails if a vertex
loses all influence. The exact source influence statistics remain in the audit.
When the external albedo/normal/roughness/metallic maps replace the FBX material
maps, they inherit FBXLoader's texture image orientation and UV/sampler transform;
only colour-space semantics remain map-specific.

## Retargeting contract

The CMU packages retain their own exact source skeletons and source profiles.
Runtime retargeting is explicit rather than pretending those profiles are Kandi's
rig. Each sampled source pose is first composed in source space. The retained
converter-added calibration T-pose is captured as the source neutral pose, but it
is not equated to Kandi's authored bind pose. Kandi's audited bind vectors put
the left/right upper arms about 57/59 degrees below horizontal, whereas the CMU
converter reference is near-T. For each unambiguous continuation chain, the
adapter derives a minimal world-space correction that aligns Kandi's bind
direction with the source calibration direction while preserving Kandi's own
joint positions and bone lengths. Source world rotations are then measured
relative to calibration, converted from source Z-up into Kandi Y-up, and applied
from that per-control reference pose.

The mapping covers hips, both leg chains, the three Kandi spine bones, neck,
head, shoulders, arms, forearms and hands. CMU convenience joints that do not
exist in Kandi's rig are folded into mapped descendant world transforms instead
of creating fake Kandi controls. Per-control orientation offsets are derived only
from non-zero, unambiguous parent-to-child directions; zero-length CMU helper
links are excluded. Global source translation drives a separate motion root
scaled by source/target skeleton height, while Kandi's FBX local joint offsets
and proportions remain unchanged.

This is a custom Kandi Boom rig adapter. It is **not** labelled as Blender
Rigify, and the source motions are not rewritten as Kandi-native recordings.

## Lazy loading and playback

Initial navigation loads the interface and renderer only. Pressing **Load &
play Kandi Boom** fetches the selected source-motion package, the native WASM
sampler and the verified Kandi target assets. Switching performances disposes
the previous native recording handle and Kandi scene before another package is
loaded. **Unload character** releases the target geometry, textures, motion
cache and native handle.

Play, pause, restart, integer-pip seek and preview speed use the existing native
DanceRudiments sampled-recording runtime. The two captures have **time-only**
timing: one second is represented by 64 integer pips. Their musical BPM and
beat/downbeat phase have not been established; no music is bundled and the UI
does not imply beat matching.

## Review motion rhythm and loop candidates

StemLab's `analyze-rig-motion` can inspect either original *complete* hashed
motion package after explicit local preparation. From sibling checkouts:

```sh
stemlab analyze-rig-motion DanceRudiments/generated/mesh-demo-assets/motions/boxbot --output salsa-rhythm.json
stemlab analyze-rig-motion DanceRudiments/generated/mesh-demo-assets/motions/prism --output ballet-rhythm.json
```

Open the gallery, load **Kandi Boom**, then use **Import analysis JSON** to
select the matching local StemLab report. The review panel remains disabled
until the verified source package and Kandi mesh have loaded. No report is
shipped or downloaded automatically and the source recording is never modified.
Analysis bytes are read locally in the browser only (2 MiB limit).

The gallery validates `stemlab.rig-motion-analysis` schema 1, the exact original
action, package ID and manifest SHA-256, the source rig type/fingerprint,
complete pip bounds and **every** chunk name and SHA-256 against the active
native package. The report must retain explicitly time-only, unverified
musical timing; it rejects confirmed beat maps and repaired or approved loops.
The inferred beat and movement-accent markers are read-only.

Selecting a loop previews its half-open source-time interval using the existing
64-pip native sampler and its normal seek/transport clock. A jump is **not** a
seam blend, pose correction, root-motion reset or verified foot plant. Manual
scrubbing exits a loop; switching characters or unloading discards all local
analysis and selected loop state. Even if a 120 BPM dance motion is inferred,
it is not a proven 120 BPM song or known downbeat. Rendered retargeting and skin
intersection require separate visual review. Source information and official
release-gated Pages publication rules remain unchanged.

Use `node --test tests/typescript/mesh-rhythm-review.test.js` for standalone
model-free schema, bounds and rejection tests. The existing `npm test` also
includes that suite; full browser acceptance requires a rebuilt actual gallery.

## Validation

The release workflow must pass all existing motion-package integrity tests plus
the Kandi source audit and Chromium gallery checks. Browser QA verifies that:

- no target FBX, texture, rig, recording or WASM payload is fetched on initial navigation;
- the requested source package and Kandi target assets match their hashes;
- native sampled values match independent Python-native reference poses;
- source-space joint matrices remain numerically consistent with the independent reference evaluator;
- the rendered object is the Kandi Boom target, contains real skinned geometry and visibly deforms across captured poses;
- the PBR maps retain the FBX diffuse texture-coordinate transform, Kandi's local joint offsets remain unchanged, and calibration builds a verified non-trivial per-control retarget reference pose;
- pausing, seeking, speed changes, switching performances and unloading preserve the native transport/resource contract;
- desktop and mobile layouts retain a usable WebGL canvas and use only bundled same-origin assets.

The release workflow packages the root visualizer and `meshes/` route together.
GitHub Pages deployment remains gated to the latest stable release and to the
existing `DANCERUDIMENTS_PAGES_ENABLED` repository setting. Source changes on
`main` alone do not prove or deploy a release; a new compatible tagged release
must complete the full browser and live-asset verification gates.
