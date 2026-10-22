# Kandi Boom: character integration and release plan

**Series:** Bass Ben & Friends. **Character:** Kandi Boom.
**Baseline:** DanceRudiments `f8e7a9831d5f93d5e6e8f1160f395e23d976f370` (`adding kandi`).
**Status:** Phase 1 started. Do not call the standalone procedural FBX viewer a native
recording-player implementation. Do not claim that the character is a Rigify rig.

## Existing architecture to reuse

The project already publishes two skinned-mesh characters, Boxbot and Prism,
through the `meshes/` release gallery. Their respective rig profiles and
optional motion packages are loaded on demand. Their sampling uses the existing
C++/WASM recording sampler and 64 integer pips per nominal beat. See
`docs/mesh-demos.md`, `docs/rig-motion.md`, `docs/release-demo.md`,
`tools/build_mesh_demo_assets.py`, `tools/build_mesh_demo.mjs` and
`tools/test_mesh_demo_browser.py`. Musical synchronization requires separate
verified beat/downbeat anchors; original CMU recordings are time-based only.

The committed `harness/kandi-boom/` assets are **not yet wired into this pipeline**.
`harness/kandi-boom/index.html` is a standalone procedural proof of concept
whose JavaScript maintains its own clock. Preserve it until the production
mesh-gallery route has equivalent or better functionality.

## Phase A1 — Source-asset audit (this patch)

- [x] Add a reproducible, read-only FBX and PNG integrity audit at
  `tools/audit_kandi_boom.py`.
- [x] Check in `harness/kandi-boom/rig-audit.json` with per-asset SHA-256,
  asset sizes, source FBX version, mesh count, skeleton hierarchy and
  skin-cluster count.
- [x] Add source audit regression tests and missing-asset checks.
- [ ] Add Blender/Assimp-based deep checks for bind-pose matrices, weight sums,
  bone index ranges, UVs, texture orientation, transform handedness and
  normals. A dependency-free FBX hierarchy scan cannot validate these.
- [ ] Capture browser screenshot(s) of the actual rendered, textured character;
  confirm front view, floor position and deformation under controlled poses.

The scanned source has a **24-bone humanoid skeleton with 24 skin clusters**.
Its limb naming follows common exported humanoid conventions, not Rigify's
animator-control layout. A named-bone correspondence is **not** proof of rig
compatibility. Do not mark retargeting as complete from this audit.

Run from the repository root:

```sh
python tools/audit_kandi_boom.py --assets harness/kandi-boom/assets \
  --output harness/kandi-boom/rig-audit.json
python -m unittest discover -s tests/python -p test_kandi_boom_audit.py -v
```

Before accepting the regenerated report, diff it with the checked-in version.
Unexpected hashes, missing maps, or skeleton changes require review.

## Phase A2 — Rig profile and retargeter

1. Export the source rest matrices, bind matrices and parent hierarchy through
   a real scene importer (FBX SDK or Blender in an optional offline tool).
2. Define a distinct semantic type for the exact **Kandi Boom source skeleton**,
   such as `syn://type/danceflow/motion/rig/custom/kandi-boom`.
3. Generate stable one-based channel IDs (translation for the root, complete
   WXYZ quaternion groups for joints), interpolation policy and a profile
   fingerprint. Avoid passing unchecked Euler components into quaternion APIs.
4. Map the canonical source movements to named Kandi Boom joints with explicit
   missing-channel handling, joint-axis corrections, calibrated bone lengths,
   foot contact and root motion. Keep unmapped controls in the rest pose.
5. Verify all channels and resulting skin matrices with fixed reference frames.
   Unsupported source rigs must fail validation, not deform silently.

**Exit gate:** A source profile and reference pose test exist; one reference
clip retargets without inverted joints, stretching, or sinking below the floor.

## Phase A3 — Native clock and motion

- Use the production `SampledRecording`/WASM package loader, not another
  `requestAnimationFrame`-integrated clock. Request absolute integer pip samples
  from the established timing interface.
- Port the bounce/sway/groove modes to actual motion primitives or flag them as
  optional procedural layers; do not mislabel as captured dance recordings.
- Retarget at least three *available and licensed* actions (initial candidate:
  existing CMU salsa and ballet clips, plus an independently sourced third
  recording). Preserve original capture rates and provenance.
- Separate **source seconds**, **preview playback rate** and **verified musical
  beat matching**. Alignment requires provided beat anchors/target phase map.
- Add looping with continuous boundaries, quaternion SLERP, blended transitions,
  source-space motion and reproducible seek/restart.

**Exit gate:** Same source profile + motion + pip produces identical transforms
on repeat, including after seek, on native and browser builds.

## Phase A4 — Mesh-gallery integration

- Register Kandi Boom in the existing catalogue and character picker alongside
  Boxbot and Prism. Prefer a dedicated loader/adapter with one scene lifecycle.
- Load the five assets lazily and avoid loading every available motion.
- Expose orbit/zoom, current bone and channel inspection, skeleton overlay,
  BPM/phase, motion selection, seeking, pause, restart and unload.
- Render with correct albedo (sRGB), normal, metallic and roughness treatment.
  Keep texture maps correctly associated with the material's UV layout.
- Dispose geometry, GPU textures, active native recording and outstanding
  fetches when a character is switched or unloaded.

**Exit gate:** Gallery can load, operate and unload Kandi Boom and still render
Boxbot and Prism. No model bytes requested before explicit load.

## Phase B — Production checks and packaging

- Keep model/motions out of default core wheels, npm packages and C++ archives.
  Provide a separately downloadable, hashed optional character bundle.
- Extend `test_mesh_demo_browser.py` and release-site QA to cover Kandi Boom
  without weakening the original Boxbot/Prism reference-frame checks.
- Add screenshot and geometry-based comparisons at multiple pips, malformed
  profile and failed CDN/network tests, leak and disposal checks and mobile UI.
- Verify release packaging manifest, relative asset URLs and integrity hashes.
- Measure scene load time, JS heap, WASM allocation and GPU resources across
  repeated load/switch/unload cycles. Record machine/browser versions.

**Exit gate:** Automated browser and native tests pass and optional asset
loading maintains bounded memory under repeated transitions.

## Phase C — Release, deployment and ecosystem

- Extend the *existing* Release demo tag workflow and complete-site builder.
  Preserve its version/commit checks, existing release approvals and
  `DANCERUDIMENTS_PAGES_ENABLED` gate.
- Include `kandi-boom` in the release catalogue, site manifest and browser QA
  *coverage list*, not just an unchecked static folder copy.
- Ship a separately identifiable optional character archive and checksum.
- Update `README.md`, `docs/mesh-demos.md`, `docs/release-demo.md` and gallery
  navigation, with attribution and explicit source-vs-musical timing notes.
- Make the example discoverable through DanceFlow MCP after the actual native
  workflow is established; do not add a parallel package registration layer.
- Verify the **deployed** `https://kieransimkin.github.io/DanceRudiments/meshes/`
  route after a new tagged release. A successful PR or main build is not a
  Pages publication.

**Exit gate:** Deployed viewer loads Kandi Boom, plays three verified rigged
clips, survives mobile/desktop browser QA, and publishes reproducible checksums.

## Patch strategy

1. **A1 (this patch):** source audit, documented execution plan, regression tests.
2. **A2–A4:** deep FBX importer, semantic profile, retargeting and gallery.
3. **B:** reliable browser validation, lazy loading and packaged assets.
4. **C:** release workflow, Pages deployment and ecosystem documentation.

Do not combine asset audits, runtime feature implementation and publication in
an unchecked release. Every stage has an explicit validation gate.
