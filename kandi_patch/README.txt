Kandi Boom final DanceRudiments integration bundle
==================================================

Baseline verified against GitHub main commit:
  9e1017dfbf714c4e5f0cff5ef1399e1699998325

This bundle finishes the production /meshes/ integration without replacing the
reviewed CMU source-motion package identities. It:

- makes the real Kandi Boom FBX/24-bone rig/PBR assets the single production target;
- hash-verifies the target from the checked-in source audit;
- retargets both pinned CMU source performances to Kandi at runtime;
- retains native WASM sampling and independent source-pose QA;
- lazy-loads Kandi and motion data only after explicit user action;
- removes Boxbot/Prism from the user-visible gallery while retaining the old
  internal motion-slot IDs for immutable source-package compatibility;
- records the explicit WebGL four-weight runtime approximation while preserving
  the untouched canonical FBX and its full source influence audit;
- binds Kandi target identity into browser evidence and release sealing;
- updates release/docs/CI checks and bumps the project to 0.4.4.

Apply on Windows PowerShell from the DanceRudiments repository root:
  .\Apply-KandiBoomFinal.ps1

Or on bash:
  ./apply-kandi-boom-final.sh

Both wrappers create a local `kandi-boom-final-integration` branch when run from
`main`. The Python patcher refuses locally modified integration files, uses
strict anchors, and rolls back all touched files if any patch or parse check
fails.

A source merge is not the same as a deployed release. After merge, publish a new
compatible tag and require the Release demo workflow/live Pages verification to
pass before treating the hosted Kandi gallery as live.
