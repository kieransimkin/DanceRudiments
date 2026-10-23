# StemLab songs × source-first motion-loop review

This is an **audio-free, generated CI review artifact**, not a released motion
package, new pattern catalogue, automatically verified music sync, or public
music redistribution. DanceRudiments does not gain a StemLab runtime dependency.

The **Source-first motion loops** workflow in
`.github/workflows/source-motion-loops.yml` now also checks out a **pinned exact
StemLab source commit** containing three original example masters and its audio
loop analysis API. The song tests run after the source-motion job has produced
and native-verified optional synthetic `RigMotion` previews.

## Songs and timing authority

| Source master | Analysis clock | Status |
| --- | --- | --- |
| `examples/arcadians/Arcadians - 320kbps.mp3` | Live traditional beat tracker using artist-confirmed 145 BPM as *a hint* | Detector beat events and provisional four-pulse bar phase; not a measured downbeat |
| `examples/the-truth-is-a-virus/master.mp3` | Exact existing `beats/consensus.json` | Beat/downbeat detector evidence, not artist-approved sync |
| `examples/star-lights-glow-mystery-liquid-kick/master.mp3` | Live traditional beat tracker, no approved BPM | Beat events and provisional four-pulse phase only; no invented canonical tempo |

Every master is SHA-256-checked against its existing committed StemLab source
reference (Arcadians `reference.json`, Truth `analysis.json`, Star Lights
`evidence.json`). Wrong mix, wrong mastering or changed MP3s fail analysis.
No cross-song downbeat/tempo annotations are borrowed.

The source of beat evidence is explicit. For the two songs without saved beat
and downbeat maps, a local `librosa` onset/beat baseline produces independent
pulse timestamps. A four-pulse *preview hypothesis* is based on onset-accent
strength, not claimed to be a trained downbeat classifier or proven 4/4 metre.
A disagreement with Arcadians' artist-confirmed BPM is reported as a metrical
ambiguity, not overwritten. The original waveform samples are not retimed or
changed.

## Audio loop analysis and rig matching

The job calls the **real StemLab** `stemlab.analysis.loops.analyze_loops` API on
each entire MP3, in `exploratory / whole_song` mode, using up to eight proposed
bars or 30 seconds per candidate, with 24 ranked exploratory alternatives and
StemLab's `spectral_context` ranking (spectral similarity is **not** a safe
join). There is no full-vocal stem in this
lightweight test, so no audio loop is presented as vocal-clear or seamless;
exploratory ranking and `failed_gates` remain inspectable in each original
StemLab `loops.json` report. No audio snippets or models are exported.

The matcher now uses **the indices of the two actual song-beat events selected
by StemLab as each proposed cut's boundaries**; it does not assume that
`bars × 4` is the observed number of beats. Missing or non-aligned boundary
evidence cannot produce an audio-motion pairing. It joins those intervals to
whole numbers of previously analysed source motion cycles, retaining 64-pip source recordings,
source profile fingerprints, unverified source tempo, change-of-speed ratio and
ranking diagnostics. Half- and double-time interpretations are available only
where the **original StemLab motion report** contains an independently evidenced
alternative (at least one supporting control group, fit score at least 0.45,
correct relative BPM, correct metrical label). Alternatives retain their own
weaker score and phase-unverified warning. A 16-beat source Action interpreted
at double-time represents 32 musical beats, not a repeated 16-beat dance.
The playback-rate estimate is based on **the mean BPM of each cut's actual
indexed beat timestamps**, not the song-wide average; a strongly nonuniform
interval is marked as requiring variable-tempo preview time-warping rather than
pretending the whole interval has one clock. The shortlist reserves places for
both full Actions and short loop candidates
instead of silently filling every slot with complete dances. Motion is not inferred by analysing the MP3 as if it were
a mesh animation. In this CI job, the source animation is a **generated synthetic
BVH with independently moving arm and knee controls**: not the Kandi Boom
skinned mesh or third-party mocap. This checks the integration without bundling
restricted CMU motion or implying it has passed retargeting QA.

## Preview interface

The CI artifact `stemlab-song-motion-loop-preview` contains:

- `song-loop-preview/index.html`: self-contained review player that works after
  extraction (no JavaScript CDN, model download, application server or network)
- `song-loop-preview/report.json`: source SHA-256 identities, beat evidence,
  waveform peaks, motion candidates and reviewer flags
- `song-loop-preview/reports/<song-id>/loops.json`: the actual StemLab exploratory
  audio-loop output, plus TSV rank tables
- `song-loop-browser-qa/`: browser validation report and desktop/mobile
  screenshots when Chromium testing succeeds

Use the **song** and **ranked candidate** selectors to inspect detected pulses,
provisional bar anchors, possible audio loop segments, and the animated projected
source rig. **Silent motion** previews work without audio. To hear it with the
correct master, select the original MP3 with the local file picker. The browser
verifies its exact file length and SHA-256 before activating audio playback;
files remain in browser memory and are never copied into the artifact. If the
browser cannot verify a hash, playback stays locked. Clicking the timeline seeks
when the verified audio is loaded.

Playback is a **review-level** browser audio seek loop, not sample-accurate
crossfade playback. It may click at the seam and does not prove motion continuity,
foot planting, target mesh deformation or exact musical downbeats. No frontend
claims `audio_beat_alignment_verified`, `loop_seam_approved` or publication
status. Browser evidence means functional controls, not subjective listening QA.

**Rights:** The Star Lights Glow repository expressly notes that a separate
redistribution licence has not been provided for its MP3 or artwork. **No master
MP3, WAV or cover file** is included in the generated CI artifact or screenshot
outputs. The existing software licences cannot confer music rights.

## Reproduce locally

From `DanceRudiments/`, after a compatible source-first motion analysis and
with the pinned StemLab checkout available at `.cache/stemlab-source/`:

```bash
python -m pip install '.[motion-import]' 'soundfile>=0.12,<1' 'librosa>=0.11,<0.12'
export PYTHONPATH="$PWD/.cache/stemlab-source/src"
python tools/build_song_loop_preview.py \
  --stemlab-root .cache/stemlab-source \
  --motion-job .cache/source-loop-smoke \
  --output-dir .cache/song-loop-preview --require-all-songs
python -m unittest discover -s tests/python -p test_song_loop_preview.py -v
```

Use `$env:PYTHONPATH="$(Get-Location)\.cache\stemlab-source\src"` in
PowerShell; the checkout/ref must contain all three song masters. No source
file or old output folder is overwritten. Each build writes into a project-local
temporary directory, then atomically moves a completed new result into place.

The browser smoke test is separate because it needs Playwright and a provisioned
Chromium runtime. The CI workflow runs it with the exact bundled Truth master
through a browser-local file picker and retains screenshot evidence, but never
uploads the underlying audio.

**Validation gates:** all three original media hashes and detector grids must be
valid; at least one audio/motion pairing must be available for the review UI;
no audio files may appear in the generated output; generated JavaScript must
parse; Chromium must render all three songs, accept the correct master by hash,
and successfully preview the synthetic motion at desktop/mobile widths.
Individual songs may have no compatible motion pair. That is a reported result,
not permission to fabricate a beat or accept a bad seam.

## Two classes of movement candidates

The song viewer now distinguishes **full-length** source Actions (only after
meeting the default 70% heuristic grid-fit gate) from **loopable** excerpts
(which require their own seam evidence). The embedded preview data includes the
source BPM, full-Action fit score, motion kind and exact rig profile source hash.
A full Action can be paired only once with a similar-length audio beat interval;
it must not be replicated to cover a song loop. A loopable excerpt may be repeated
for an audition, but no visual or audio seam is approved. The underlying original
rigs and all original music/audio are unchanged.

## Compare additional provenance-tracked motions locally

The preview builder accepts **multiple explicit** source-first motion jobs.
It validates each `job.json` and every selected `.motion.json` SHA-256, and
shows at most eight selected records in the viewer. No global motion search,
automatic import, or public third-party motion upload occurs:

```sh
python tools/build_song_loop_preview.py \
  --stemlab-root .cache/stemlab-source \
  --motion-job .cache/loop-analysis/salsa \
  --motion-job .cache/loop-analysis/ballet \
  --output-dir .cache/combined-song-preview --require-all-songs
```

The viewer labels primary/alternative metrical interpretations and distinguishes
original source BPM, interpreted beat count, sample replay rate, and scored
loop quality. Source profiles are **not automatically retargeted** onto Kandi
Boom. Local preview reports containing third-party skeletal trajectories are
user-controlled and should not be published without source-specific rights.

## Reproducible real-motion diagnostics (separate from public media preview)

The independent `real-motion-benchmark.yml` checks the two original, already
reviewed CMU BVH files used for Kandi's salsa and ballet. It uses the pinned
source and effective frame-rate policies in `tools/mesh_demo_sources.json`,
**then** calls StemLab on their source-time rig captures and evaluates the same
70% complete-Action gate plus independent loop candidates. It does not require
either genuine dance to pass that heuristic threshold; rejecting an unsuitable
Action is a valid measurement. CI explicitly fetches only the two pinned hashes
and uploads **summary.json only**, not original/converted motion samples or
audio. CMU source-specific terms, including no direct resale, continue to apply.

For an already-local cache, without downloading:

```sh
python tools/evaluate_real_rig_motions.py \
  --cache-root .cache/real-motion-sources \
  --output-dir .cache/real-motion-summary --max-previews 2
```

Add `--download` only when you explicitly want to fetch the two reviewed
source motions. `summary.json` records per-source real tempo hypotheses,
grid-fit scores, conversion outcomes and seam diagnostics; these values are
kinematic evidence, **not** a claim that the source music or Kandi's rendered
mesh has been validated.
