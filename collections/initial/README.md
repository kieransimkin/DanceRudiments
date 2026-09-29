# Initial 01 — audition before adopting

By [Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/).

28 optional candidates for Kieran Simkin's DanceRudiments / DanceFlow workflow.
The existing 15 built-ins are unchanged. This collection does not auto-register
anything globally, and **no candidate is pre-approved or preselected**.

## See the movements

Open `harness/initial-collection.html` in a modern browser. The generated HTML
contains its data, styling, interface code and compiled C++/WebAssembly sampler.
It needs no build, internet connection, CDN, Python runtime or audio download.
If your browser or organisation blocks local HTML, serve the checkout:

```sh
python -m http.server 4173
```

Then open `http://localhost:4173/harness/initial-collection.html`. The existing
`harness/index.html` also links to the new gallery.

Press **Play**. Adjust BPM, shared movement size and path display, or pause and
step by one pip. All candidates share the same clock: an eight-beat candidate
lasts twice as long as a four-beat candidate. A beat means a quarter note.
The grey path shows the full positional cycle; the small trailing dots show
recent motion. Below it, lavender is X and mint is Y; the white line is phase.
Groove timelines also show amber source event markers. Coordinates are shared,
+X points right and +Y down. No per-card automatic amplitude scaling is applied.
The size slider scales positions, not timing; waveform strips remain in source units.

Use **Compare** on up to four cards for a common side-by-side view. Mark candidates
**Keep**, **Maybe** or **Skip**, and add notes. Clicking the same status again restores
Not reviewed. Source details include licences, file identities, transformation
steps and compiler diagnostics. Filters do not erase decisions.

**Export review** saves statuses and notes tied to this exact collection revision.
It is the file to send back when discussing curation. **Import review** restores it;
wrong revisions, changed source identities and duplicate entries are rejected
before any state changes. Reviews persist in local browser storage where available.
Private browsing, local-file policies or storage quotas may disable persistence;
exports continue to work and a visible warning is shown. Importing a review replaces
current review decisions, so export first to retain both versions.

**Export kept pack** produces a normal `dancerudiments.compiled-pack` with only
Keep entries. **Export kept scores** produces editable authoring scores. Source
attribution is retained in both. Maybe and Skip do not enter the exported pack.

### Try your music

Expand **Play against your own track**, select a local audio file, set BPM, and
enter the time of beat zero in seconds. Nothing is uploaded. The audio element
becomes the clock, so play, pause and seeking follow the track. Timing is calculated
as `(audio_seconds - beat_zero_offset) * BPM / 60`. This is manual synchronisation,
not audio analysis or beat detection. Audio before beat zero gives negative phase.
No Groove source recording, drum sample or click sound is included.

The gallery starts paused for everyone. A change to `prefers-reduced-motion` pauses
playback. Motion is limited to bounded dots: no flashing backdrop, colour modulation
or full-frame zoom. All the current candidates are 1D/2D positional motions, not
full-body dance, rotation, opacity or scale animations.

## What is included

| Family | Count | Candidates |
|---|---:|---|
| Original LFO/envelope studies | 8 | Breathe; Surge & recover; Soft gate; Double pump; Ratchet & release; Glide staircase; Morphing wobble; Three-lobe orbit |
| Original rhythm studies | 4 | 3 in 8; 5 in 12; Three against two; Half-time lurch |
| Original rudiment interpretations | 4 | Double paradiddle; Paradiddle-diddle; Six-stroke; Flam accent studies |
| Easing loops | 4 | D3-derived Rebound, Anticipation, Overshoot & settle; original Elastic ring |
| Actual AKWF source shapes | 4 | Rounded saw; Quick return; Multiple lobes; Plateau |
| Actual Groove MIDI excerpts | 4 | Excerpt A played/grid; excerpt B played/grid |

There are 8,704 pip samples across the 28 candidates. The Groove cards use **two
8-beat excerpts from one 80-BPM funk performance**, each with a played-timing and
sixteenth-grid version. They are not four independent recordings. Source MIDI
was obtained from the identified MEI-GMD mirror; we do not claim to have downloaded
or verified the entire official GMD archive. Timing/velocities are actual imported
data; the conversion to position is an original interpretation. No source audio
or MEI engraving is included.

The rudiment studies are independently encoded sticking demonstrations, not copied
PAS artwork or recordings. Equal spacing and grace offsets are documented in each
score; these are visual movement interpretations, not comprehensive pedagogical
performance notation. No claim of endorsement is made.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Original code/motions are MIT,
AKWF data CC0-1.0, Groove data CC BY 4.0 and selected D3 equations BSD-3-Clause.
The MIT project licence does not erase these data-specific obligations.

## Use from Python (native playback)

After rebuilding/installing the patched package:

```python
from dancerudiments_authoring.collections import initial_pack

# Explicit opt-in; selecting does not alter the built-in catalogue.
pack = initial_pack(["lfo_flower", "akwf_multi_lobe", "groove_a_played"])
library = pack.to_native()
print(library.sample("lfo_flower", -1).as_tuple())
print(library.sample("circle", 64).as_tuple())  # Built-in fallback remains available.
```

`initial_pack(names=None)` loads all 28. A nonempty iterable selects a subset in
catalogue order; unknown/duplicate names are rejected. This loader returns data,
not a Python movement sampler. `.to_native()` requires the C++ extension.
Load a gallery export with the existing `load_pack(path).to_native()`.
The wheel includes the compiled pack and notices under `dancerudiments_authoring/packs`.

## Use from C++17

```cpp
#include <dancerudiments/collections/initial.hpp>

const auto position = dancerudiments_initial::sample_lfo_flower(pip_count);
auto library = dancerudiments_initial::make_library();
const auto other = library.sample("groove_a_played", pip_count);
```

Link the existing `DanceRudiments::DanceRudiments` CMake target. The generated header
is included by the existing header installation rule. Named functions are
allocation-free table samplers; `make_library()` explicitly constructs an owned bank.
The bank contains the 28 custom entries plus the 15 built-ins. No core version bump
or global catalogue expansion is made by this patch.

For only your choices, generate a smaller header from the gallery's kept scores:

```sh
python tools/compile_patterns.py compile DanceRudiments-chosen.score.json --cpp chosen.hpp --json chosen.json
```

That uses the existing default C++ namespace `dancerudiments_generated`.
Keep the source notices and embedded provenance when redistributing selected data.

## Use from TypeScript / JavaScript

The npm package exports the JSON at `@kieransimkin/dance-rudiments/collections/initial`.
A JSON-capable bundler or Node runtime with import attributes can load it:

```js
import {bindNative, createPatternLibrary} from "@kieransimkin/dance-rudiments";
import createDanceRudiments from "@kieransimkin/dance-rudiments/wasm";
import pack from "@kieransimkin/dance-rudiments/collections/initial" with {type: "json"};

bindNative(await createDanceRudiments());
const library = createPatternLibrary(pack);
try {
  const offset = library.sample("lfo_flower", 48);
  // Apply offset.x / offset.y to a bounded subject.
} finally {
  library.dispose();
}
```

A fetched/exported JSON document can also be passed to `createPatternLibrary`.
This is the production Emscripten binding, distinct from the self-contained gallery
binding described below. The pack is optional, so importing the main npm module
does not automatically load 753 KiB of JSON or allocate all sample tables.

## Rebuild and verify, offline

```sh
python tools/build_initial_collection.py
python tools/build_initial_collection.py --check
```

No third-party Python packages are needed for either command. The builder checks
exact source-file Git blob identities before parsing numeric tables and MIDI bytes.
The MIDI adapter supports SMF format 0/1 with PPQ timing and rejects unsupported,
truncated or malformed inputs. The committed original `.mid.b64` decodes to the exact
verified MIDI; it is not a hand-entered transcription. No input is executed as code.

`definitions.py` contains the source adapters and editable original definitions.
The builder emits the score pack, Python package JSON, C++ header, manifest,
freestanding preview table, and standalone HTML. Changes to sampled data or the
preview C++ source invalidate the bundled WASM. Recompile it with LLVM clang++ and
wasm-ld (no Emscripten SDK is needed for this small binding):

```sh
python tools/build_initial_collection.py --rebuild-wasm --compiler clang++
```

The gallery's freestanding C++ sampler only wraps an integer pip and returns three
doubles from the generated table. It has no host imports, network, audio DSP or
JavaScript fallback. Its samples are tested against both the real C++
`PatternLibrary` and every named generated function. It is not a substitute for the
normal Emscripten package and does not claim to test that binding.

LF line endings are pinned for exact-source and generated collection files so
Windows autocrlf cannot invalidate source-byte checksums. The upstream AKWF tables
retain their original whitespace too: do not apply whitespace auto-fixes to these
source files, as that would invalidate their verified identities. `--check` re-evaluates the
Python authoring equations; it does not recompile WASM on every run. It checks the
compiled module's source/data identities and byte hash instead. The script avoids
modifying package versions, registrations or releases.

## Tests

```sh
# Set PYTHONPATH to python, or install the package first.
python -m unittest discover -s tests/python -v
node --test tests/typescript/initial-wasm.test.mjs
python tests/browser/test_initial_gallery.py
```

The browser test needs Playwright and a Chromium installation; no browser package is
a runtime requirement. It injects the complete HTML into an isolated document to
avoid network navigation, tests actual blob downloads and local audio, and explicitly
covers the no-storage fallback. It does not establish file:// navigation permissions
or persistent localStorage behaviour in every browser. Desktop/mobile screenshots
can be written with `--screenshots output-directory`.

`tests/cpp/test_initial_collection.cpp` links the existing native core, sampled-pattern
source and `collections/initial/preview_sampler.cpp`. The new CI workflow runs its
parity checks, the full Python tests and actual WebAssembly checks, then smoke-tests
the installed wheel's bundled data. Source regeneration is checked in Linux CI.
