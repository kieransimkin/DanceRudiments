# Curve and event authoring

DanceRudiments is the motion-vocabulary component of Kieran Simkin's DanceFlow
workflow, alongside StemLab analysis and the WordPress DanceMoves runtime.

This infrastructure separates **offline authoring in Python** from **movement
playback in C++**. Authoring has no third-party Python dependencies and can run
without building the extension. It emits a versioned JSON sample pack, a standalone
C++17 header, or both. The existing fifteen built-in functions and global catalogue
are unchanged. No external presets, recordings or choreography datasets are bundled.

## Quick start from a source checkout

```sh
python tools/compile_patterns.py validate examples/patterns/starter.json
python tools/compile_patterns.py compile examples/patterns/starter.json --json generated/starter.json --cpp generated/starter.hpp
python tools/compile_patterns.py check examples/patterns/starter.json --json generated/starter.json --cpp generated/starter.hpp
```

`compile` writes outputs, `validate` checks without writing, and `check` exits with
status 2 if an output is missing or stale. All validation/rendering happens before
writes. Each output is replaced atomically, but writing two output files is not a
single filesystem transaction. An input cannot also be an output. `generated/` is
ignored by Git; commit deliberately curated packs under a different directory.

After installing the patched package with `python -m pip install .`, the same
commands are available as `dancerudiments-compile` or
`python -m dancerudiments_authoring`. Installing the package builds the native
extension; only the source-checkout authoring command avoids that build entirely.

The sample pack contains `wobble_xy`, `triplet_steps`, `segmented_sway` and
`seeded_drift`, demonstrating mixed axes/events, fractional timings, a three-beat
curve and a longer deterministic random loop respectively.

## Python playback: the extension does the movement sampling

```python
from dancerudiments_authoring import load_pack

compiled = load_pack("generated/starter.json")
library = compiled.to_native()  # dancerudiments.PatternLibrary, implemented in C++

print(library.sample("wobble_xy", 48).as_tuple())
print(library.sample("triplet_steps", -1).as_tuple())
print(library.sample("circle", 64).as_tuple())  # existing built-in remains available
print(library.catalogue())
```

Compile programmatically with a JSON-compatible dictionary:

```python
from dancerudiments_authoring import compile_score

pattern = compile_score({
    "name": "my_sway",
    "period_beats": 2,
    "tracks": [{
        "axis": "x",
        "curve": {"type": "lfo", "shape": "sine", "period_beats": 2}
    }],
    "provenance": {"author": "Your name", "license": "Your data licence"}
})
native_pattern = pattern.to_native()
print(native_pattern.sample(32).as_tuple())
```

`CompiledPattern.samples` contains offline data, not a Python runtime sampler.
`to_native()` requires the patched extension and raises a descriptive error if it
is unavailable. There is deliberately no silent Python playback fallback.

## C++ playback: no Python installation, parser, or runtime dependency

```cpp
#include "generated/starter.hpp"

int main() {
  // Allocation-free named function over constexpr sampled data:
  auto a = dancerudiments_generated::sample_wobble_xy(48);

  // Or a private, owning library with custom and built-in names:
  auto library = dancerudiments_generated::make_library();
  auto b = library.sample("triplet_steps", -1);
  return (a.x >= -1.0 && b.x >= -1.0) ? 0 : 1;
}
```

Link to `DanceRudiments::DanceRudiments` as usual. The header can use a custom
namespace with `--namespace myproject::patterns`. C++ namespaces cannot use reserved
keywords/identifiers; C++ export also rejects pattern names containing double
underscores, which are reserved inside C++ identifiers. Exported function names are
`sample_<pattern_name>`, tables are `table_<pattern_name>`, and
`provenance_<pattern_name>` retains the original metadata as a JSON string.

For applications loading data through their own parser:

```cpp
#include "dancerudiments/sampled_pattern.hpp"

using namespace dancerudiments;
SampledPattern custom("hand_authored", "A deliberately abrupt two-position loop",
                      {{-1, 0, 0}, {1, 0, 0}});
PatternLibrary library({custom});
auto value = library.sample("hand_authored", -1);
```

The C++ layer validates names, finite bounded components, sample counts and name
collisions. It does not re-run the Python curve-continuity checks; callers directly
constructing a `SampledPattern` are responsible for intended motion characteristics.

### Native API reference

| API | Behaviour |
| --- | --- |
| `sample_table(std::array<Offset3, N>, int)` | Allocation-free discrete sampler; checks table size at compile time and wraps signed pips. |
| `SampledPattern(name, description, vector<Offset3>)` | Owns and validates a copy/moved vector of one sample per pip. |
| `SampledPattern::sample(int)` | Wraps and returns one stored sample, with no interpolation. A moved-from empty pattern throws `logic_error`. |
| `SampledPattern::name()`, `description()`, `period_pips()` | Read-only metadata. |
| `SampledPattern::info()` | `RudimentInfo`, with dimensionality inferred from active axes. |
| `PatternLibrary(vector<SampledPattern>)` | Immutable-through-API, independent bank; duplicate names and built-in shadowing are errors. |
| `PatternLibrary::sample(name, int)` | Custom pattern lookup, then existing built-in lookup; unknown names throw `invalid_argument`. |
| `PatternLibrary::catalogue()` | Built-ins followed by custom patterns, preserving input order. |

String views in native catalogue/info results refer to their owner. Keep the owning
object alive and do not move from or assign to it while retaining those views.
Bindings copy metadata strings. Read-only sampling is safe across threads after
construction; concurrent assignment/destruction is the caller's responsibility.

The existing global `sample()` and `catalogue()` are not mutated by constructing a
bank. `dancerudiments.sample("wobble_xy", pip)` therefore remains an unknown-name
error; use your bank's `sample()` or the generated named function.

## TypeScript / JavaScript playback

```typescript
import { bindNative, createPatternLibrary } from "@kieransimkin/dance-rudiments";
import createDanceRudiments from "@kieransimkin/dance-rudiments/wasm";

bindNative(await createDanceRudiments());
const response = await fetch("/assets/starter.json");
if (!response.ok) throw new Error(`Pattern fetch failed: ${response.status}`);
const library = createPatternLibrary(await response.json());
try {
  const position = library.sample("wobble_xy", 48); // delegates to C++ WASM
  console.log(position, library.catalogue());
} finally {
  library.dispose(); // releases native memory; safe to call more than once
}
```

`createPatternLibrary(document: unknown)` validates the interchange header, names,
counts, bounded triples and source metadata before allocating C++ objects. It returns
`sample(name, pipCount)`, `catalogue()` and `dispose()`. Temporary native objects are
released on success or failure. Sampling after disposal is an error. Rebinding the
global module does not redirect an existing bank into a different WASM instance.

Both wrapper sampling APIs reject non-integers and values outside signed 32-bit
range rather than allowing Emscripten to truncate or overflow them. Python's new
native class methods similarly require a value representable by C++ `int`.

The dependency-free browser harness is still the existing built-in demonstration.
It does not load custom packs; custom browser playback requires the WASM binding.
There is no JavaScript implementation of the new motion sampler.

## Musical timing contract

One beat in authoring schema 1 is explicitly **one quarter note**. One beat is 64
pips. BPM, audio sample numbers, meter interpretation and host transport conversion
remain the caller's responsibility. Do not confuse this with DanceMoves' 16 ticks
per beat or a dotted-quarter pulse in compound meter.

Beat fields accept integers, finite decimal numbers or rational strings such as
`"1/3"`, `"7/2"` and `"0.125"`. Use rational strings for tuplets. Decimal numbers
mean their decimal spelling; `0.3333333333333333` is not treated as exact `1/3`.
Every sample is evaluated at absolute beat `Fraction(pip, 64)`. Durations are never
rounded and repeatedly accumulated.

The **enclosing loop** must contain an integer number of pips in `[1, 65535]`,
matching the existing native `RudimentInfo` period field. Three-, five-, seven-,
eight- and sixteen-beat loops work. A one-third-beat oscillator can run inside a
one-beat loop; a standalone one-third-beat loop cannot be stored exactly at this
resolution and is rejected. A `3/2`-beat loop is valid and contains 96 pips.

Sub-pip event times are preserved during compilation, not snapped to the grid.
Their exact peak may fall between stored samples. This is a deliberate sampling
limitation, not cumulative rhythm drift. The compiler warns about very short or
entirely missed events. It does not provide automatic band-limiting or recover
features that cannot be represented on the discrete grid.

## Score format (schema 1)

The CLI accepts a standalone score object or a pack:

```json
{
  "format": "dancerudiments.score-pack",
  "schema_version": 1,
  "patterns": [{
    "name": "my_pattern",
    "description": "Optional description",
    "period_beats": 4,
    "tracks": [{"axis": "x", "curve": {"type": "lfo"}}],
    "gestures": {},
    "events": [],
    "bounds": "reject",
    "loop_policy": "closed",
    "provenance": {"author": "Example", "license": "MIT"}
  }]
}
```

`name` and `period_beats` are required. A score needs at least one track or event.
Names match `[a-z][a-z0-9_]{0,127}`. Pack names must be unique and cannot shadow any
of the fifteen built-ins. `description` defaults to the empty string, `tracks` and
`events` to empty arrays, and `gestures` and `provenance` to empty objects. Unknown
fields are rejected, including common spelling mistakes. No Python expressions,
function names, modules, shell commands or `eval` payloads are accepted as curves.

### Scalar curves and axis composition

A track has exactly `axis` (`x`, `y` or `z`) and `curve`. Multiple tracks on one axis
are added. All curve nodes support finite numeric `gain` (default 1) and `offset`
(default 0), applied as `offset + gain * result`.

| `type` | Fields and meaning |
| --- | --- |
| `constant` | Required numeric `value`. |
| `lfo` | `shape` defaults to `sine`; also `triangle`, `skew_triangle`, `saw_up`, `saw_down`, `pulse`. `period_beats` defaults to the enclosing loop; `phase` is a rational **cycle fraction**, default 0; `duty` defaults to 0.5 and must be strictly between 0 and 1. Duty affects pulse width/skewed triangle peak. |
| `keyframes` | Required `points`, strictly increasing from beat 0 through the enclosing loop's endpoint. Each point has `beat`, `value`, and outgoing `interpolation`, default `smoothstep`. |
| `samples` | Required `values` containing 2..4096 scalar samples of one cycle, **without a duplicated endpoint**. `period_beats` and cycle `phase` work as for LFOs. `interpolation`: `linear` (default), `hold` or `smoothstep`, including the last-to-first interval. |
| `random_hold` | `steps` defaults to 8 (1..4096), `seed` defaults to 0 (signed 64-bit). Optional `period_beats` and cycle `phase`. Fixed hash-indexed values repeat exactly; this is not evolving white noise. |
| `random_smooth` | As above, smoothly connecting values including last-to-first. |
| `sum`, `product` | Required `curves`, a list of 1..32 recursively composed scalar curves. |
| `mix` | Required curve objects `a`, `b`; `amount` is a finite scalar or another curve. Evaluated amounts must lie in `[0,1]`; no implicit clipping. |

Sine starts at zero and rises. Triangle starts at -1, reaches +1 halfway through the
cycle and returns. Skewed triangle reaches +1 at `duty`. Saw-up starts at -1 and
rises toward +1; saw-down is its inverse. Pulse is +1 before `duty`, otherwise -1.
Saw/pulse/hold curves may deliberately jump. Their reset must comply with the
selected loop policy.

Keyframe interpolation choices are `linear`, `hold`, `smoothstep`, `smootherstep`
and `cubic`. A cubic segment requires numeric `control1` and `control2` on its
starting point; these are **absolute scalar value controls at one-third and
two-thirds of the segment parameter**, with linear beat-time parameterisation.
They are not two-dimensional Bézier time handles. The final keyframe does not start
a segment and cannot have cubic controls. Overshoot is possible and is handled by
the explicit bounds policy.

For a smooth pulse, asymmetrical attack/decay, ratchet or staircase, use event
gestures and/or keyframes rather than expecting a raw square wave to be smoothed
automatically. To build an XY path, use independent phase-related tracks.

### Events and gestures

```json
{
  "name": "offbeat_hit",
  "period_beats": 1,
  "gestures": {
    "right": {
      "duration_beats": "1/3",
      "peak_fraction": "1/4",
      "shape": "cosine",
      "axes": {"x": 0.8, "y": -0.3}
    }
  },
  "events": [{"beat": "1/3", "gesture": "right", "anchor": "peak", "strength": 0.9}]
}
```

A gesture requires a positive `duration_beats` no longer than the enclosing loop
and a nonempty `axes` object. Omitted axes are zero. `peak_fraction` defaults to
`1/2` and lies strictly between 0 and 1. `shape` is `cosine` (default), `smoothstep`
or `triangle`. The envelope is zero at both ends and reaches 1 at its peak, with
separate attack and decay durations determined by `peak_fraction`.

An event requires `beat` in `[0, period_beats)` and an existing `gesture` name.
`strength` defaults to 1 and is nonnegative; negative axis values reverse movement.
`duration_beats` can override the gesture's duration for one event.

`anchor` defines what the event's beat marks:

| Anchor | Event beat means |
| --- | --- |
| `onset` (default) | Start of the gesture. |
| `peak` | Peak displacement; the attack can begin in the previous loop. |
| `end` | End of the gesture; its entire body precedes this time. |

For a visible contact at a musical beat, use `peak` only when that gesture's peak
actually represents contact. There is no inferred skeletal contact model. Durations
and anchors wrap periodically, and overlapping events add component-wise.

The existing drum functions place the start of their envelope at each stroke's
pip. The new infrastructure does not reinterpret or change those built-ins.

### Bounds, seams and safety diagnostics

`bounds` is one of `reject` (default), `scale` or `clip`. Reject catches out-of-range
combinations. Scale applies **one common factor across all samples and axes** only
when the peak exceeds 1, preserving relative amplitudes and path aspect ratio.
Clip explicitly saturates components and records a warning. Tiny floating-point
roundoff around the bounds is tolerated; the stored data is always bounded.

`loop_policy=closed` requires the compiled curve's estimated left-hand position
limit at the seam to match the first position within `1e-7` after the bounds policy.
The probe lies one trillionth of the loop before its endpoint. This is a numerical
position check, not a proof for arbitrary curves and not a velocity/acceleration
continuity guarantee. `allow_jump` opts into reset jumps and records a warning.

The final stored sample is one pip **before** the endpoint, so a correct smooth
loop is not required to have identical first and last samples. The compiler does
not force the last sample to equal the first, crossfade the source, invent a return
path, or remove translation/rotation from imported choreography. A future importer
must do those operations explicitly and document them.

Diagnostics include `seam_position_error`, sampled `seam_step`, sampled `max_step`,
`unscaled_peak_component`, `normalization_scale`, bounds/loop policy, beat unit and
warnings. `max_step > 0.5` produces a review warning. Discontinuities *inside* the
loop are not prohibited by `closed`; review the samples and diagnostics.

Safety remains a host concern: scale to a bounded subject, respect reduced-motion
preferences, and do not turn control curves into full-frame brightness/flashing
modulation. Compiler bounds are not a medical or visual-comfort certification.

## Interchange and provenance

Compiled JSON uses `format: "dancerudiments.compiled-pack"`, `schema_version: 1`,
`pips_per_beat: 64`, and a `patterns` list. Each entry has `name`, `description`,
`period_pips`, `samples` (XYZ triples), `source_sha256`, `provenance` and `diagnostics`.
The sample count must equal `period_pips`; all components are finite and in `[-1,1]`.

The compiler rounds sample components to twelve decimal places. Those baked values
are the runtime authority across C++, Python and WASM. Playback does not regenerate
sine curves, hashes or events. Hash-indexed randomness is seek-order independent.
Regenerating mathematical curves on different libm versions can still affect
insignificant diagnostic or rounding-boundary details; retain compiled artefacts
when bit-for-bit reproducibility matters.

`source_sha256` hashes sorted, compact JSON of the authoring score; it is an
identity/provenance aid, not a signature, a compiled-payload checksum or proof of
licensing. JSON readers reject duplicate keys and non-finite constants. Metadata
must be JSON-serializable and finite. Suggested provenance keys include `source`,
`source_url`, `author`, `license`, `revision`, `source_checksum` and
`conversion_notes`; their domain-specific meaning is the importer's responsibility.

A pack contains 1..1024 patterns and at most 1,048,576 total samples. Source reads
are capped at 64 MiB. Curve depth, node count and compilation work are bounded;
overly complex scores fail instead of evaluating arbitrary programs.

This patch provides the common representation, composition, validation, compiler,
interchange and native sampling infrastructure. It does **not** yet provide a
MIDI/WAV/BVH/Taminations importer, a GUI curve editor, automatic beat extraction,
full-body/multi-actor motion, runtime score interpretation, or third-party packs.
Source-specific importers should produce these authoring scores (or validated
sampled curves) and retain their own source permissions. Compiling data into C++
does not change its original licence.

## Tests and CI

```sh
# Pure authoring tests from a checkout (native tests skip if unbuilt):
# POSIX:
PYTHONPATH=python python -m unittest discover -s tests/python -v
# PowerShell equivalent:
# $env:PYTHONPATH = "python"
# python -m unittest discover -s tests/python -v

# Installed package, including native round-trip tests:
python -m pip install .
python -m unittest discover -s tests/python -v

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
npm test
```

`DANCERUDIMENTS_REQUIRE_NATIVE=1` makes a missing extension fail rather than skip.
The separate pattern workflow tests installed wheels on Linux/Windows and Python
3.9/3.13. The existing C++ workflow also picks up the new release-active native tests.
The new WASM job uses the same Emscripten image as publishing and compares every
exported example sample, including negative and out-of-order seeks, with the actual
C++ module. Wrapper tests use mocks only for validation/ownership contracts; they
are not represented as real-WASM tests.

Package versions are unchanged. Applying this infrastructure patch does not publish
or trigger a release; choose a release version separately after CI validation.
