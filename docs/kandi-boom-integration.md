# Kandi Boom integration

**Series:** Bass Ben & Friends  
**Character:** Kandi Boom  
**Canonical target rig:** `syn://type/danceflow/motion/rig/custom/kandi-boom`

## Status

The source-asset audit and production gallery integration are implemented. The
remaining release gate is operational rather than architectural: merge the
integration, publish a new compatible release tag, and require the release demo
workflow plus live Pages verification to pass before describing the hosted route
as deployed.

The production `/meshes/` route no longer renders the procedural Boxbot/Prism
fixtures. Those historical modules may remain in the repository as isolated
unit-test fixtures, but the release bundle imports Kandi Boom's real FBX and
retargets both reviewed source performances to its real skeleton.

## Completed source acceptance

- Canonical FBX and four 2048×2048 PBR maps are hash-pinned.
- The FBX contains one 29,965-triangle mesh and a 24-bone humanoid skeleton.
- All control points are weighted; bind-pose and cluster matrices were audited.
- `source-rig.json` records the target hierarchy, rest transforms, inverse binds
  and stable fingerprint.
- The FBX animation stack is correctly treated as rest/static data, not as a
  dance recording.
- The source's >4-influence vertices are documented rather than silently
  relabelling the source as a native four-weight asset.

See [Kandi Boom source audit](kandi-boom-source-audit.md) for the detailed source
evidence and exact hashes.

## Completed production integration

- The release-site builder independently verifies and copies Kandi's FBX,
  target-rig JSON, albedo, normal, roughness and metallic maps.
- The source-motion packages remain lazy, independently hashed optional data.
- A dedicated runtime target adapter composes the selected source skeleton in
  source space. The retained converter T-pose is captured explicitly and used
  to construct per-control target reference orientations from corresponding
  parent-to-child bone directions. Kandi's FBX local joint offsets remain intact;
  world-space motion is applied as deltas from the calibrated source reference
  to the anatomically aligned Kandi reference rather than directly from her
  authored A-pose bind orientation.
- Source Z-up motion is converted to Kandi's Y-up target basis without changing
  the canonical recordings.
- Root motion is scaled by source/target skeleton height and measured from the
  same retained calibration frame outside the FBX rest hierarchy.
- The renderer applies Kandi's external PBR maps with the albedo in sRGB space
  while preserving the FBX diffuse map's image-Y orientation, UV channel,
  wrapping, repeat, offset, centre and rotation contract.
- Runtime four-weight skinning is explicit and validated; the canonical FBX is
  never rewritten or substituted.
- The UI presents Kandi Boom for both performances and no longer presents
  Boxbot/Prism as characters.
- Browser diagnostics retain the exact source-pose matrix checks while exposing
  Kandi target identity and deformation statistics.
- Existing native WASM sampling, integer-pip transport, lazy chunk loading,
  cancellation and resource disposal remain shared rather than forked.

## Release acceptance

A release is complete only when all of the following are true for the same tag
and commit:

1. Kandi source audit/regression tests pass.
2. Motion-package, TypeScript and release-page tests pass.
3. The release gallery loads the hash-pinned Kandi FBX and PBR assets only after
   explicit user action.
4. Both CMU performances pass independent sampled-channel/source-matrix checks
   and visibly deform the Kandi target in Chromium.
5. Desktop and mobile screenshots are retained as CI evidence.
6. The complete-site archive and gallery archive are sealed with checksums.
7. If Pages is enabled, the newest stable release is deployed and every live
   public asset is reverified against the tested site manifest.

Do not report the hosted Kandi gallery as live until the new release workflow
has completed those deployment checks.
