# N-dimensional BPM-synchronised recordings and the shared visualizer

This additive API represents **non-looping named dimensions**, sampled at **64
pips per quarter-note beat**, with mandatory BPM provenance. It does not change
`Offset3`, the built-in catalogue, existing XYZ compiled-pack schema, or legacy
loop rules. Audio DSP remains in StemLab, not in this library.

## Contract

`dancerudiments.recording` schema 1 declares `sample_dtype: float64` and
`sample_decimals: 12`. Components are finite, within [-1,1], and rounded to twelve
decimal places. Native code checks the IEEE-754 binary64 contract. JSON numbers
are not PCM audio samples with a 16/24-bit depth.

Each recording requires a finite positive BPM, `bpm_status` (`estimated` or
`confirmed`), and nonempty `bpm_source`. `phase_status` is separately `unverified`,
`estimated` or `supplied`; confirming BPM does not confirm the beat origin.

```
time(i) = beat_zero_seconds + (start_pip + i) * 60 / (64 * bpm)
```

A row is one pip window/sample; `start_pip` may be negative. `RecordingClock`
uses fractions derived from the decimal BPM instead of repeatedly rounded hops.
The rate in seconds is 128 Hz at 120 BPM. This contract is constant-tempo, not a
variable-tempo map; no default BPM, automatic beat detection or phase guessing.

```json
{
  "format": "dancerudiments.recording",
  "schema_version": 1,
  "pips_per_beat": 64,
  "sample_dtype": "float64",
  "sample_decimals": 12,
  "name": "four_axes",
  "dimensions": ["bass", "treble", "drums", "vocals"],
  "clock": {
    "bpm": 145.0,
    "bpm_status": "estimated",
    "bpm_source": "artist estimate",
    "beat_zero_seconds": 0.0,
    "phase_status": "unverified",
    "start_pip": 0
  },
  "samples": [[0.2, 0.6, 0.9, 0.1], [0.3, 0.4, 0.2, 0.7]],
  "provenance": {"producer": "example"}
}
```

Dimension identifiers are unique `[a-z][a-z0-9_]{0,127}` strings; every row has
exactly their number of values, in the declared order. Unknown fields, malformed
headers, ragged rows, non-finite data/metadata, duplicate JSON keys, missing BPM
and invalid dimensions fail validation. At least one row/dimension is required.
The resource guards are 8,388,608 scalar values and 64 MiB per JSON document,
not a fixed XYZ dimension ceiling. Recordings can exceed 65,535 pips. Clock/index
validation keeps recorded absolute pips representable by the native int API.

## Python and C++ playback

```python
from dancerudiments_authoring import load_recording, write_recording
r = load_recording("recordings/four_axes.json")
write_recording("copy.json", r)  # refuses replacement unless explicitly requested
native = r.to_native()  # real C++ SampledRecording, not a Python fallback
values = native.sample(r.clock.start_pip)
assert len(values) == len(r.dimensions)
```

`SampledRecording` owns and validates the data and returns **all dimensions**.
An out-of-range absolute pip raises instead of looping. Name, dimensions, count,
BPM, beat origin and first pip are readonly metadata. A moved-from object cannot
be sampled. Data I/O is standard-library-only; Python native playback needs the
updated extension, and raises clearly with an older/missing build.

```cpp
#include <dancerudiments/recording.hpp>
using namespace dancerudiments;
SampledRecording r("four_axes", {"bass","treble","drums","vocals"},
                   {{.2,.6,.9,.1}, {.3,.4,.2,.7}}, 145.0, 0.0, 0);
auto values = r.sample(1); // four doubles, non-looping
```

`recording_view.hpp` supplies the dependency-free `recording_component` accessor
shared by this C++ object and the generic recording WASM. The browser does not
regenerate mathematical curves or run a JavaScript motion fallback.

## Generate the actual DanceRudiments comparison harness

```python
from pathlib import Path
from dancerudiments_authoring.harness import build_recording_harness
from dancerudiments_authoring import load_recording
paths = sorted(Path("output/recordings").glob("*.json"))
report = build_recording_harness((load_recording(p) for p in paths),
                                  "output/index.html", collection_id="my-audio-batch")
```

All candidates must share the exact clock and captured extent; their dimension
counts can differ. Input is consumed one recording at a time. Duplicate float64
columns are pooled by checksum, retaining all samples without repeating the same
stem/filter data for every candidate. Bounds are 1024 candidates and 128 MiB of
unique binary sample columns. The audit JSON reports native WASM/data/page hashes,
clock, counts, unique columns and byte size.

The builder uses **the same template, CSS, beat player and app as release/catalogue
pages**. Their former `tools/release_demo_assets` files now live under packaged
`python/dancerudiments_authoring/harness_assets`; `tools/release_demo.py` delegates
to this shared `render_template`. Do not create another renderer in StemLab.

The page retains search, original four-card comparison, review choices/notes and
review JSON import/download. Recording mode adds any-axis X/Y/Z projections and
JSON download links for files under the sibling `recordings/` directory. It locks
exported tempo/beat origin and stops at the end. Nothing autoplays. Paths are not
closed across a non-looping seam. Display-decimated traces do not change full
native samples. The exported JSON keeps axes not currently visible in the view.

Optional `audio` metadata may include a **plain local basename** `relative_path`
for a caller-copied track, plus its source hash and extent. The exporter does not
copy or upload music. Without included audio, the existing local-file picker or
silent transport can be used. Media playback uses the audio-element clock.
Source codec/security support is a browser concern; do not disable browser policy
to force loading. Review local storage is best-effort; download JSON for portability.

All HTML/JS/CSS, native WASM and sampled columns are embedded. No compiler/CDN or
external request is required to build/use a recording page. Keep any optional
media and recording JSON companions with the HTML for their controls to work.
The page is control-data inspection, not proof of comfortable full-body choreography.

## Rebuilding the tiny generic native sampler

```sh
python tools/build_recording_wasm.py
```

This uses clang++/wasm-ld, targets freestanding wasm32, and stores base64 bytes plus
source/binary hashes in packaged assets. Rebuild when `recording_view.hpp` or
`tools/recording_wasm.cpp` changes. Normal exports verify the bundled WASM checksum;
end users need no compiler. CI rebuilds and checks for a stale committed asset.
The existing catalogue export still follows its original native snapshot workflow.

## Explicit legacy XYZ conversion

```python
from pathlib import Path
from dancerudiments_authoring import emit_json
pack = r.to_compiled_pack(dimensions=("bass", "treble"), start=0, count=2)
Path("xy.compiled.json").write_text(emit_json(pack), encoding="utf-8")
```

Select 1..3 axes and at most 65,535 samples; missing XYZ components become zero.
A larger recording requires explicit axis/excerpt selection, never truncation.
The legacy sampler loops, so conversion retains a seam warning and source clock;
it does not smooth/close an arbitrary excerpt. The new native recording API does
not loop. Existing C#/TypeScript XYZ interfaces remain unchanged; this addition
provides N-D C++/Python and the recording harness, not new general N-D wrappers
for all languages.

## Validation

```sh
PYTHONPATH=python python -m unittest discover -s tests/python -p test_recording.py -v
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
node --test tests/typescript/beat-player.test.js
python tools/test_recording_harness.py ./test-harness/index.html --make-fixture
```

Browser testing requires Playwright/Chromium. Normal mode tests local-file loading;
`--in-memory` is an explicitly labelled fallback only for restricted environments.
With copied audio, that fallback hydrates the exact bytes into the existing audio
element as a Blob, retaining actual decoding/transport/renderer/native WASM. Its
report does not claim file loading or audible listening QA. The checker samples
every candidate against retained JSON and tests transport, arbitrary-axis
projection, non-looping bounds, no autoplay, search/comparison and review download.
Set `DANCERUDIMENTS_REQUIRE_NATIVE=1` to reject missing native tests rather than skip.

Existing versions/tags are unchanged by this patch. Publish a fresh matching
release only after review and CI. This source API is not present in earlier
published packages.
