Kandi Boom final DanceRudiments integration bundle — corrected v2
=================================================================

Baseline verified against GitHub main commit:
  9e1017dfbf714c4e5f0cff5ef1399e1699998325

Correction in this bundle
-------------------------
The first ZIP accidentally declared docs/release-demo.md as a replacement
payload even though that file is patched in place. That caused the installer to
stop immediately after creating the integration branch. No source files were
changed because the Python patcher rolls back on failure.

This corrected bundle:
- removes that false payload requirement;
- verifies every real payload file before changing Git branches;
- resumes cleanly if `kandi-boom-final-integration` already exists;
- retains strict patch anchors and rollback-on-error behaviour.

If the first bundle already created the branch, simply extract this ZIP over the
old `kandi_patch` directory and run the PowerShell command again from the
DanceRudiments repository root. You do not need to delete the branch.

Apply on Windows PowerShell:
  .\kandi_patch\Apply-KandiBoomFinal.ps1

Or, if your shell is already inside the extracted `kandi_patch` directory:
  .\Apply-KandiBoomFinal.ps1

What the integration does
-------------------------
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

A source merge is not the same as a deployed release. After merge, publish a new
compatible tag and require the Release demo workflow/live Pages verification to
pass before treating the hosted Kandi gallery as live.
