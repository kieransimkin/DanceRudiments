# Full-catalogue visualizer and MIDI beat player

The main `harness/index.html` is now a **single self-contained HTML file** with
all default movements, the C++/WebAssembly snapshot sampler, the complete beat
library, a small procedural percussion synthesiser, and all interface code.
`harness/index.json` is an audit sidecar, not a browser dependency. The top of the
README links directly to the downloadable HTML, rather than an unbuilt harness,
a GitHub source-code view, or an external JavaScript/WASM dependency.

## Listen and compare

Open the HTML locally and press **Play**. The initial beat is the complete
four-bar Amen study at the harness's current BPM. **MIDI sound** mutes/unmutes the
synthesiser; **Volume** controls its level. Nothing auto-plays. Tempo is shared
with animation, including pause, restart, seeking, single-pip stepping and live
BPM changes. Changing the beat preserves phase and BPM. **Use suggested BPM** is
the explicit action that changes tempo to the score's suggestion.

The Library menu separates dance music, recorded Groove MIDI excerpts, abstract
event studies, and the original C++ sticking rudiments. Search also matches IDs
and families. A selected beat remains available while filtering.

**Only matching movements** restricts the catalogue to movements derived from
that score. **Compare this beat's movements** selects its first four mappings;
other cards can be chosen normally. **Follow compared movement** automatically
selects the first newly compared movement's source beat. Individual cards also
have **Use this movement's beat**. A waveform or geometric path without scored
onsets can still be auditioned against any beat, but is not assigned a fictitious
source drum pattern.

Expand beat details for the complete onset grid, per-lane mutes, provenance and
MIDI import/export. The grid uses exact fractional source times and represents
velocity with dot size/opacity; its numbered axis counts quarter notes over the
whole loop. It is not an automatically quantised sixteenth-note grid.

The local-audio option is retained. Loading a track pauses MIDI and uses the
track's audio-element clock, BPM and manually entered beat-zero offset instead.
Remove the track to return to MIDI. The two audio sources are not accidentally
played together. Hiding the tab pauses playback to avoid background timer drift.

## Coverage

The current registry includes **305 scores**:

| Source | Scores |
| --- | ---: |
| Club 05 + Dancefloor 06, deduplicated by exact shared rhythm identity | 68 |
| Earlier authored event scores (Euclidean, additive, polyrhythm, swing, sticking, etc.) | 226 |
| Groove MIDI excerpt A/B, played and grid variants | 4 |
| Original C++ drum-sticking definitions | 7 |

They are linked to **1,325 movements**. All **1,731** movements are available in the
same visualizer; continuous shapes without note events can use any accompaniment.
This is not a claim that 305 unrelated dance genres or recordings were imported.
Some entries intentionally share timing while differing in instrument/gesture
emphasis. Abstract event lanes receive explicitly assigned audition timbres.

`tools/harness_beats.py` reads the committed `*/rhythms.json`, `*/*.score.json`,
pack provenance, and default-selection lock. It also extracts the seven legacy
stroke lists from their C++ function bodies rather than duplicating those lists.
A changed/unsupported C++ representation fails loudly. This preserves the saved
rhythms, not freshly recalculated platform-dependent motion definitions.

The original stroke timestamps represent **gesture starts**; those movement
peaks occur half a stroke-width later. Generated scores retain their declared
onset/peak/end anchor semantics. Neither the source timings nor movement tables
are silently shifted to conceal that distinction.

The Amen study retains all 16 quarter-note beats (four bars), 81 programmed note
onsets, ghost-note velocities, displaced later backbeats and the cymbal change.
**Amen / ghost notes A–B** switches to the existing no-ghost comparison, without
changing the animation tempo. It remains a quantised structural interpretation,
not the original recording or measured drummer microtiming.

## MIDI support

**Download beat as MIDI** writes a real type-1 Standard MIDI File, with a tempo
meta-event at the current animation BPM, meter when known, note-on/off events,
credits and an end-of-track marker at the exact loop endpoint where representable.
Percussion uses zero-based channel 9 (human channel 10); bass uses channel 1.
Built-in listening preserves rational source onsets; SMF export chooses a PPQ
that represents those fractions exactly where possible (maximum 32767). When the
combined denominators do not fit, it uses 30720 PPQ and reports the maximum timing
quantisation. MIDI velocities necessarily use 7-bit precision. Notes that would
extend past the loop end are gated at the boundary in exported files.

**Import MIDI** supports PPQ type-0/type-1 `.mid`/`.midi` files, up to 2 MiB, 65,536
notes, 128 tracks and 4,096 quarter notes. It handles running status, note-offs,
velocity-zero note-ons, track-end silence, tempo/meter metadata and ignorable
SysEx. Invalid/truncated input fails without replacing the current beat. SMPTE
and independent-sequence type-2 files are deliberately rejected.

Imported tempo maps do **not** change the animation tempo; tick positions are
normalised to quarter notes and played at the harness BPM. The first embedded
tempo is offered as a suggestion. Channel-10 notes use the synthesised kit;
other channels use simple pitched cues. This is a rhythm audition player, **not**
a full General MIDI sound module: patch changes, controllers, pitch bends,
sustain pedals and expressive articulation are not emulated. Long imported scores
have a horizontally scrollable grid; at most 32 distinct lanes are drawn, while
all valid notes remain scheduled. There is a defensive 256-voice playback cap.
No MIDI hardware access or permissions are requested.

The Groove MIDI attribution/licence and source/transformation notes are retained
in the HTML and exported MIDI copyright/text metadata. Original recordings and
commercial samples are not included. Existing source terms still apply.

## Clock design

Web Audio's `currentTime` is the scheduling clock once audio is enabled. A 25 ms
control timer schedules a short 100 ms look-ahead window; `requestAnimationFrame`
never triggers drum hits. Visual phase uses `getOutputTimestamp()` where available
and a reported-latency fallback, so it follows the output audio clock rather than
an unrelated elapsed-time counter. Device/display latency can still affect
perceived synchronisation; this is not a hardware calibration tool.

Each musical window is half-open to avoid duplicate hits at loop boundaries.
Beat times remain unwrapped; every movement applies its own C++ loop modulus.
Pause, seek, source changes, mutes and tempo edits cancel queued voices and rebase
the same clock. Pending audio unlocks are invalidated by pause. A short scheduling
lead is used when rebasing; the beat position is preserved, but sample-seamless
DJ-style tempo warping is not promised. Web Audio must first be enabled through
a user gesture. The maximum accepted tempo is 300 BPM and the minimum is 20 BPM.

## Build and test

```sh
python -m pip install .
python tools/build_harness.py
python tools/harness_beats.py --output harness/beats.json
node tools/export_harness_midi.mjs dist/midi
node --test tests/typescript/beat-player.test.js
python tools/test_midi_harness.py harness/index.html
```

Generation requires clang++ and wasm-ld, as the previous native release demo did.
The browser test requires Playwright/Chromium. `--in-memory` is available only for
restricted test environments and is recorded in the report; normal CI tests local
file loading. The checked-in HTML is an immediate download; regenerate and commit
it when changing the catalogue or player. The per-push build produces a fresh
artifact even when a checked-in preview has not yet been refreshed.

Release generation uses the same template/player and reads that tag's native
catalogue. The release workflow validates MIDI playback before packaging its
HTML, screenshots and checksums. Stable `DanceRudiments-visualizer.html` and
`DanceRudiments-visualizer.json` aliases are attached as well, enabling a stable
`releases/latest/download/DanceRudiments-visualizer.html` URL after the next release
containing these changes. Older releases are not retroactively altered.

## Optional live GitHub Pages site

The README's **downloadable HTML works without Pages**. For a hosted click-to-play
copy at `https://kieransimkin.github.io/DanceRudiments/`:

1. Set Repository **Settings → Pages → Source → GitHub Actions**.
2. Add the repository Actions variable `DANCERUDIMENTS_PAGES_ENABLED` with value
   `true`, then run **Pattern visualizer**, or push another commit to `main`.

The workflow builds and tests on pushes and pull requests. Pages deployment is
opt-in and main-only; it cannot deploy untrusted pull-request content. It uploads
**only `dist/visualizer`**, never the repository root, so unrelated source files
or credentials cannot leak into the site. No public site or release has been
published by supplying this patch.

## Protocol and hosting references

- W3C Web Audio API: https://www.w3.org/TR/webaudio/
- MIDI Association, Standard MIDI Files: https://midi.org/standard-midi-files
- GitHub Pages custom workflows: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- GitHub Pages publishing source: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
