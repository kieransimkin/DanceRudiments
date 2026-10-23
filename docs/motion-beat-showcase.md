# Rigged motion beat-finding CI showcase

This optional CI job tests **actual, originally timed CMU source skeleton Actions**,
not generated random motions or user-submitted meshes. It shows four animated
review candidates drawn from eight distinct, already SHA-256 + Git-blob-pinned
original BVH recordings in the existing `motion-packages/cmu-dance-sources.json`:

| ID | CMU description | Showcase purpose |
| --- | --- | --- |
| `103_03` | Charleston | Repetitive steps and alternating limbs |
| `106_12` | Twist | Lower-body torsion and repeated gesture |
| `143_34` | Chicken Dance | Gestural/cyclic movement |
| `143_35` | Macarena | Upper-body gestures and potential static holds |
| `05_11` | Sideways steps / pirouette | Turns, pose changes and unequal rhythm strength |
| `90_28` | Breakdance | Challenging floor-level/fast motion and loop rejection |
| `90_30` | Russian dance | Repeated leg/step phrasing |
| `55_01` | Dance, whirl | Continuous turning and ambiguous rhythmic accents |

The source styles are deliberately diverse; they are not automatically
**approved loops**. The job does not assume one musical BPM for all of them.

## Running

Use the new `.github/workflows/motion-beat-showcase.yml` manual dispatch or
push a change to its scoped source files. The job pins a tested StemLab source
revision, installs DanceRudiments' optional motion-import dependency and
Pillow, and runs the exact existing `analyse_source_capture` source-first
inference with native sampler verification. It validates the complete source
file hash and Git blob hash *before* interpreting any movement data. The
source archives are not downloaded unless the job explicitly supplies
`--download`. The exact source may include a converter calibration frame,
which is excluded from analysis only; the original source data is unchanged.

Run locally from the DanceRudiments repository root, after configuring a
compatible StemLab source checkout in `PYTHONPATH`:

```powershell
python -m pip install -e ".[motion-import]" soundfile pillow pytest
python -m pytest tests/python/test_motion_beat_showcase.py -q
python tools/build_motion_beat_showcase.py `
  --cache-root .cache/motion-beat-source-pool `
  --output-dir .cache/motion-beat-showcase-local `
  --download --max-selected 4 --minimum-previews 3
```

Change the new output path before repeating the job; existing outputs are never
overwritten.

## Ranking and safeguards

- Use **independent source IDs** and reject byte-identical aliases.
- Run StemLab on physical source-time channels **before** any 64-pip resampling.
- Retain ranked candidate BPM alternatives and heuristic complete-Action grid
  confidence. The 70% minimum to compile a whole Action is never weakened.
- Select a proposed loop only when it has an explicit estimated beat grid,
  provenance, **native-sampled preview verification**, original frame bounds,
  pose/velocity/root seam checks, and at least 0.9 seconds of duration.
- Compute quaternion-sign-invariant angular activity inside the proposed region.
  Reject near-static/idle material: an unmoving pose is not a good dance loop.
- Render at most one candidate per original Action so a single motion with
  dozens of similar moments cannot dominate the four-slot demo.
- Label every segment as requiring review. Do not assert audio beat alignment,
  meter/downbeat correctness, foot planting, topology, root compensation or
  seamless wrapping. Three good **review** candidates are the minimum CI gate;
  if fewer qualify the workflow fails transparently with an evidence summary
  rather than quietly reducing the acceptance criteria.

## Output and rights

The `dance-rig-beat-showcase` GitHub Actions artifact holds `index.html`,
`summary.json` and animated rendered source skeleton GIFs. These are viewable by
unzipping the artifact and opening `index.html`. The job does **not** upload the
BVH bytes, evaluated per-bone channel arrays, source captures, converted native
recordings, or user music files. The full private analysis stays in the
repository-local ignored `.cache/` directory and is not published. There is no
automatic GitHub Pages deployment until the motion and rights review is signed
off. This is a CI review demonstrator, not yet a production asset library.

Source attribution: **The data used in this project was obtained from
mocap.cs.cmu.edu. The database was created with funding from NSF EIA-0196217.**
BVH conversion by Bruce Hahne/cgspeed. CMU motion data can be copied or
modified but cannot be sold directly (even converted); retain the
[CMU FAQs](https://mocap.cs.cmu.edu/faqs.php) and the repository's
`motion-packages/licenses/CMU-Mocap.txt` terms.

The 120fps value in some converted BVH headers is **not independently certified
original capture timing**. In particular, previous CMU salsa `60_01` needs a
reviewed 60fps correction; this exploratory pool deliberately excludes it and
uses original pinned header time with a visible provenance caveat. Do not
interpret a high kinematic BPM as an artist-verified music tempo.

## Actual first CI run and verified fallback (23 October 2026)

The first complete eight-source CI analysis ([run 39907507217](https://github.com/kieransimkin/DanceRudiments/actions/runs/39907507217)) successfully parsed and analysed **all eight** SHA-pinned original BVH Actions. None passed the conservative fully native-verified physical loop selection. This is a meaningful negative finding, not a build infrastructure failure. Full-Action heuristic confidences ranged from about 40–62%; every result retained unverified musical phase. The original workflow treated that negative scientific result as failure and produced no animated output.

The improved generator now distinguishes two independent presentation types:

- **Unverified loop candidate:** only from an actual native-verified, source-tempo-grid-aligned preview that passes the existing physical seam/root-drift and activity checks. It can repeat in the review GIF, but remains neither seamless nor musically approved.
- **Non-looping source-motion study:** when a source has no qualifying loop, select a short active window from the original source rig (real measured quaternion angular movement, excluding static intervals). It is explicitly **not a loop**: the GIF plays once; beat alignment, repeat seam and native-converted loop verification are not asserted. The source and its file SHA-256 have still been verified, and its estimated whole-Action tempo remains a hypothesis.

The gallery ranks qualifying loop previews first, then active motion studies, with at most one preview per original Action and a preference for distinct dance styles. The CI floor of three now applies to **animated verified-source showcase segments**, not to loop candidates. It still fails when source extraction or meaningful movement are unavailable; full-length `>=70%` and all seam, contact and native-verification policies remain unchanged.

The `summary.json` reports `selected_loop_candidate_count` and `selected_motion_study_count` separately. Neither category represents artist-approved musical beat detection or an approved repeating motion. Before promoting clips to real loops, record verified foot contacts, source-beat phase, retargeted target-mesh quality and measured repeat seam.
