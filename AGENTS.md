# Agent instructions for DanceRudiments

- Read README.md, docs/ and the binding examples. Check the native catalogue, integer-pip timing, compositions and the C++, Python, WASM and C# bindings before adding a pattern or adapter.
- Use the relevant existing capabilities as fully as the task warrants. Always look for a useful improvement to this tool. Fix a reusable gap here rather than copying its engine or carrying a private workaround; record why no change is justified when that is the result.
- Submit improvements as PRs to https://github.com/kieransimkin/DanceRudiments/pulls. Never leave a completed reusable improvement only in a local fork. Keep changes focused and preserve the tool's identity and compatibility contracts.
- Add relevant regression coverage, documentation and a reproducible example when behaviour changes. Use tools/release_version.py and tools/check_release_version.py. Run the native and relevant binding tests from .github/workflows/ before packaging.
- Keep credentials, account data, private media and rights records out of source, fixtures, logs and packages. Use synthetic fixtures or explicitly authorised public examples and preserve their provenance/licences.
- Use [CONTRIBUTING.md](CONTRIBUTING.md) for review. Maintainers publish accepted, validated improvements as a fresh matching GitHub release and verify configured registry destinations. Preserve existing tags and release assets; publication and deployment remain subject to applicable authorisation.
- Website: https://kieransimkin.co.uk/danceflow/

## Keep README documentation current

- Whenever a feature is added or changed, update the relevant README.md in the same change to reflect the resulting behaviour. This applies to every feature addition or modification, including APIs, commands, configuration, defaults, integrations and removals.
- Update affected feature descriptions, usage instructions, options, examples and limitations. For tools or packages with their own README.md, update that README as well as the repository README when its overview or usage is affected.
- Check the README against the implemented and verified behaviour before committing, opening or merging a PR, publishing a release or handing off the work. A feature change is incomplete until its README documentation is current; a changelog or other documentation does not replace this requirement.

## Released viewers and coordinated CI/CD

- Read [docs/released-viewers.md](docs/released-viewers.md) before changing dependency, build or release behaviour. The sibling layout is `DanceRudiments/`, `react-timeline-sequence/`, and `stemlab/` under one parent.
- Release the two companions first (React Timeline Sequence, then DanceRudiments), verify their configured publication workflows and public registries, then synchronize/rebuild/test/release StemLab. A merge or tag alone is not a verified release.
- StemLab must target the **latest stable official releases**. No unreleased main commit, mutable development override, local `file:` archive or vendor package may substitute for a missing release. Latest is resolved before the build and locked to exact published versions, release commits and registry hashes for that run; fail visibly on stale or incompatible dependencies rather than falling back silently.
- Use the canonical `stemlab/scripts/Release-DanceFlow.ps1` coordinator from the shared parent directory. Preview first; `-Execute` explicitly performs scoped commits, normal pushes and fresh tags; `-Resume` must preserve source identities and existing tags/assets. Never force-push, move release tags, commit unrelated work, bypass failed checks or change approvals/protections/credentials to manufacture a pass.
- Update this repository's README.md and AGENTS.md in the same change whenever release policy, dependency rules, automation, commands, controls or validation change. Keep relevant package/feature READMEs current too. A separate guide or changelog does not replace the root README update.
- Preserve the master-plus-drums/percussion beat-routing contract, 64-pips-per-beat native recording clock, per-dimension bars and combined waveform/spectrogram lanes. New UI features must be supplied by released shared APIs and genuinely rebuilt frontend assets, not copied engines or marker strings.
- Distinguish source CI, package publication, full-song inference, browser/audio QA, artifact packaging, actual Pages deployment and live URL/audio verification. Keep all four Arcadians pages together; do not report unexecuted, skipped or older-commit checks as success. CI playback evidence is not subjective listening QA.

## Full ecosystem and release preflight

Before every new workflow run, check the latest stable official release and observe the actual runtime used by the job. Follow [the shared preflight](https://github.com/kieransimkin/DanceFlow/blob/main/docs/workflows/release-preflight.md) and this project's [people-and-agent guide](docs/ECOSYSTEM.md). Review the complete relevant capability inventory rather than only a familiar command. Consider every DanceFlow component against the actual task; use and compose all applicable supported capabilities, and improve a concrete reusable gap in its canonical repository. Record why existing capabilities suffice when no change is justified. No catalogue checklist expands the task, authorises model downloads/training, or proves integration. Preserve exact source/package identity, clocks, model-local storage, privacy, costs, immutable releases and separate deployment gates.

## Rigify motion validation

For rig-motion changes, read `docs/rig-motion.md`, `docs/rigify-catalogue.md` and
`docs/motion-sources.md`. Keep native 64-pip playback and the existing normalized
Recording contract; do not introduce another live sampler. Preserve each saved
profile's numbered channels and fingerprint. Regenerate built-in profiles only
with the explicitly pinned Blender/Rigify source, and label contextual components
and custom rigs accurately. Run the `test_motion*.py` and `test_rig*.py` suites
and `tools/test_blender_rigify_bridge.py` in the pinned `bpy` environment for
Blender-facing changes. For interchange changes, also run
`tools/test_blender_motion_imports.py --output-dir .cache/blender-imports`.
The `Rigify motion` workflow supplies that optional
integration gate. Use synthetic fixtures; research catalogue entries do not
authorize downloading or bundling third-party motion, models or media.

## Optional motion packages

Read `docs/motion-packages.md` and `docs/blender-motion-import.md` for changes to
optional model recordings. Keep motion payloads in ignored `motion-packs/`,
outside base npm/Python/native artifacts and the default catalogue. Do not add
automatic downloads, global data registration or a second live sampler.
Source-package downloads require task authorization and source-specific rights;
retain licence, attribution, source hash and conversion changes with every pack.
Never label a source skeleton as a Rigify retarget or time-only data as musical
beat alignment. Preserve complete-action pip bounds and distinguish action counts
from chunk counts.

Run `test_motion_packages.py`, `test_bvh_import.py`, the TypeScript package/page
tests via `npm test`, and the existing rig/recording tests. Blender import changes
also require `tools/test_blender_motion_batch.py` in the pinned runtime. The
`motion-import` extra supplies NumPy only for offline BVH conversion. Verify
base-package file lists exclude generated motion data before packaging; npm's
separate recording WASM asset must match its checked-in source hashes.

## Preflight temporary-directory access

Before any long, costly, model-backed, media-rendering, build, test, packaging or release command that creates private or atomic temporary directories, run a disposable preflight with the exact runtime, user or sandbox, and intended output parent. The probe must create a unique directory, write and read a file, atomically rename it, then remove the file and directory.

Keep temporary data and caches under the owning project on `Z:`; model weights and model-specific caches remain under that project's ignored `models/`. If the probe returns `WinError 5`, access denied, a rename failure or a cleanup failure, stop before the expensive command. Preserve the exact error and use the documented narrowly approved unrestricted recovery from the outset only when the task requires it. Use a fresh output directory and do not repeat the already-failing full job in the restricted shell.

After any unrestricted recovery, verify that the final output is readable and writable from the normal managed environment. If it is not, copy the completed bytes into a pre-created project-local directory that passed the probe, verify hashes, and retain the original failure and recovery evidence. Do not edit global ACLs, switch caches to `C:`, terminate unrelated processes or claim the underlying permission problem is fixed. Repositories that own temporary-directory creation should provide and test a reusable preflight helper rather than relying only on this instruction.
