# DanceRudiments

By **[Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/)** · Part of the **DanceFlow** motion workflow.

[Visualizer](#visualizer) · [Language bindings](#language-bindings) · [C++](#c-binding) · [Python](#python-binding) · [TypeScript / JavaScript](#typescriptwasm-binding)

<a id="visualizer"></a>

## ▶ Try the pattern visualizer

**[Download the self-contained visualizer — HTML](https://github.com/kieransimkin/DanceRudiments/raw/refs/heads/main/harness/index.html)**

Save the file and open it in a browser. **No install, server, CDN, soundfont or
separate WASM file is required.** The complete 1,731-movement catalogue includes a
shared-tempo beat player: **305 scores**, including all 68 dance-music studies,
the **full four-bar Amen break**, four-to-the-floor, garage, drill, grime,
jungle, house, techno, Groove MIDI excerpts and the earlier event/sticking studies.

Choose a beat, press **Play**, and change **BPM** to retime the sound and animations
together. Compare any movements, or use **Only matching movements** and
**Use this movement’s beat**. Local `.mid` import and MIDI export are included.
Sound is synthesised from note events, not the original Amen recording.

The downloadable file is the checked-in snapshot; the **Pattern visualizer**
workflow also rebuilds a fresh version from every pushed native catalogue.
[Beat player, rebuilding, release downloads and optional live hosting](docs/midi-harness.md).

[![Four Amen-based movements compared in the real self-contained visualizer](https://raw.githubusercontent.com/kieransimkin/DanceRudiments/main/docs/images/visualizer-amen-desktop.png)](https://github.com/kieransimkin/DanceRudiments/raw/refs/heads/main/harness/index.html)

*Captured from the running C++/WebAssembly visualizer at beat 2.75. Audio was not started during this screenshot.*



DanceRudiments is a C++17 library of deterministic rhythmic position functions. One integer pip is `1/64` of a beat. Built-in and custom patterns each keep their own loop period. Every sampler wraps positive or negative input into its own loop before sampling.

Outputs are dimensionless offsets, normally in `[-1, 1]`. The caller chooses pixels, CSS units, metres, or another scale. There is deliberately no time interpolation in the public API: renderers advance with integer pips and get one exact sample per pip.

## Default collections

The default catalogue contains **1,731 movements**: 15 original routines, 28 Initial 01,
24 Expansion 02, 256 Motion Atlas, 320 Continuum, **144 Club Rhythms 05** movements, and **944 Dancefloor 06** additions.
Use the ordinary `sample(name, pip_count)` API without loading a separate pack.

[Club Rhythms 05](collections/club/README.md) interprets 36 beat patterns, including
the four-bar Amen, four-to-the-floor, UK garage, drill, grime, jungle, house and
techno, using four different movement mappings. Its offline demo includes a
synthesised drum player, exact onset grid, and C++/WASM movement animations.

```sh
python -m pip install .
python tools/build_club_demo.py --output dist/club-demo.html
```

See the [default library guide](docs/default-library.md) for all collections.
Release demos enumerate the actual tagged native catalogue and also render the
focused Club Rhythms page. No original recordings are bundled.

## Dancefloor 06

The default catalogue now contains **1,731 movements**, including 944 new Dancefloor 06
entries. All 68 beat studies have sixteen movement interpretations. The previous Club 05
scores and their original 144 movements remain unchanged. Research, rhythm-specific notes,
and exact timing semantics are in the [Dancefloor guide](docs/dancefloor.md) and
[complete mapping catalogue](collections/dancefloor/README.md).

```sh
python tools/build_dancefloor_collection.py --check
python tools/build_default_catalogue.py --check
```

The release workflow builds the complete native catalogue demo plus an offline,
audio-enabled 68-rhythm / 16-mapping comparison page. All live motion comes from C++/WASM.

## Curve and event authoring

The optional **Python authoring tools** compile LFOs, segmented curves, sampled
waveforms, seeded repeating randomness and rational-beat event/gesture scores into
JSON packs or C++17 headers. **All movement playback remains C++**, including
Python and TypeScript/WASM consumers. The original fifteen motion tables are
preserved; additional custom packs use independent `PatternLibrary` objects
rather than global overrides.

```sh
python tools/compile_patterns.py compile examples/patterns/starter.json --json generated/starter.json --cpp generated/starter.hpp
```

The compiler runs from a checkout without third-party Python dependencies or a
native build. See the [authoring and native API guide](docs/authoring.md) for curve
formats, event anchoring, loop validation, generated functions, Python playback,
WASM loading, provenance and testing. These are original infrastructure examples,
not imported third-party preset banks.

## DanceFlow ecosystem

DanceRudiments is the reusable motion-vocabulary layer in Kieran Simkin's DanceFlow BPM and motion-response ecosystem:

- **StemLab** is the music-understanding layer. It analyses audio to produce BPM, beat, structure, stem, lyric, harmony, and related timing evidence.
- **DanceRudiments** turns integer musical positions at 64 pips per beat into deterministic 1D, 2D, or 3D position offsets.
- **DanceMoves** is the WordPress EPK motion runtime. It schedules and applies BPM-, cue-, and lyric-timed effects on public pages.

The three components can also be used independently. They exchange explicit timing and analysis data rather than depending directly on one another. DanceRudiments' 64-pips-per-beat sampling convention is intentionally higher resolution and is not the same unit as DanceMoves' 16-ticks-per-beat runtime clock.

## Which package should I use?

| You are building | Install or download | What you get |
| --- | --- | --- |
| Python application | `pip install dancerudiments` from [PyPI](https://pypi.org/project/dancerudiments/) | Native Python extension and the catalogue/sample API |
| TypeScript or JavaScript application | `npm install @kieransimkin/dance-rudiments` from [npm](https://www.npmjs.com/package/@kieransimkin/dance-rudiments) | TypeScript declarations, JavaScript wrapper, and WebAssembly module |
| C++ application using a listed release platform | Download the matching `DanceRudiments-cpp-<version>-<platform>-static.zip` from [GitHub Releases](https://github.com/kieransimkin/DanceRudiments/releases) | Headers, static library, CMake package files, licence, platform manifest, and instructions |
| C++ application using another toolchain or architecture | Build from source or use `conan create` with `conanfile.py` | A library compiled for your own settings |

GitHub automatically adds “Source code” ZIP and tar.gz links to every release; those are repository snapshots, not precompiled packages. Python wheels belong on PyPI and the TypeScript/WASM package belongs on npm, while GitHub release attachments include C++ archives and the separately generated HTML demos, screenshots and checksums.

## Included rudiments

The general motions are `bounce`, `sway`, `circle`, `figure_eight`, `step_touch`, `box_step`, `helix`, and `clay_background`.

The first drum-derived set is `single_stroke_roll`, `multiple_bounce_roll`, `double_stroke_roll`, `single_paradiddle`, `flam`, `drag`, and `five_stroke_roll`. The first six mirror the fundamentals in Vic Firth's Tier One learning sequence and collectively cover the roll, diddle, flam, and drag families in the Percussive Arts Society's 40 International Drum Rudiments. A right-hand stroke moves right, a left-hand stroke moves left, and both rise slightly. Every stroke is a raised-cosine (`sin²`) gesture: zero displacement at the start, smooth attack, a rounded peak, and smooth decay back to zero before the next motion. Accents use greater amplitude rather than an instantaneous position jump.

Source references: [Percussive Arts Society International Drum Rudiments](https://pas.org/rudiments/) and [Vic Firth 40 Essential Rudiments](https://ae.vicfirth.com/education/40-essential-rudiments/), accessed 28 September 2026.

`clay_background` preserves the translation waypoints from the Clay/Stars `ks-particle-dance` background treatment as a normalized 256-pip lookup table. The source effect's opacity, rotation, and scale are not position offsets, so they are intentionally excluded.

## Language bindings

All three interfaces sample the **same C++ runtime**. Choose the interface, not
another movement implementation. The examples below are checked into
[`examples/bindings/`](examples/bindings/) so they can be built and tested.

| Interface | Catalogue | Sample | Loop-length field | Custom-library lifetime |
| --- | --- | --- | --- | --- |
| C++17 | `dancerudiments::catalogue()` | `dancerudiments::sample(name, pip)` | `period_pips` | Owned by its C++ object; normal RAII |
| Python | `d.catalogue()` | `d.sample(name, pip)` | `info["period_pips"]` | Owned by the Python object wrapping C++ |
| TypeScript / JavaScript | `catalogue` (an array, not a function) | `sample(name, pip)` after `bindNative()` | `info.periodPips` | Call the custom bank's `dispose()` |

**One beat is 64 pips.** Supply a signed 32-bit integer, not milliseconds or a
floating-point beat number. Every sampler wraps negative as well as positive
positions into its own loop. Offsets are `{x, y, z}`, dimensionless and bounded to
`[-1, 1]`; choose the pixel/metre scale in your application. There is no automatic
interpolation, BPM detection or audio playback inside a binding.

For an absolute playback time, use
`floor((playback_seconds - beat_zero_seconds) * BPM / 60 * 64)`.
Use `floor`, not integer truncation, for negative positions. Do not add a rounded
pip increment on every frame: that accumulates drift. For a tempo map, integrate
the elapsed beats; do not multiply the entire song time by the latest tempo.
For long-running playback, wrap at the selected movement's period before passing
an integer that could overflow the API. Different movements have different periods.

> **Checkout versus published version:** these examples describe the current
> repository. `pip install` / `npm install` retrieve the latest *published*
> package, which may predate this catalogue. Inspect `catalogue()` / `catalogue`
> rather than assuming a fixed count. Build the checkout when trying unreleased
> patterns such as the expanded Amen interpretations.

### C++ binding

**Requirements:** CMake 3.20+ and a C++17 compiler. Python is not needed to build or
play the committed movement tables. Build and install the core from the repository
root; choose a prefix writable by your user:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PWD/install"
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
cmake --install build --config Release
```

In PowerShell, use an absolute prefix such as
`-DCMAKE_INSTALL_PREFIX="${PWD}/install"`. Multi-configuration generators put
executables under `Release/`; the `--config Release` arguments handle that.

In your application's `CMakeLists.txt`, create the executable before linking it:

```cmake
cmake_minimum_required(VERSION 3.20)
project(MyAnimation LANGUAGES CXX)
find_package(DanceRudiments CONFIG REQUIRED)
add_executable(my_animation main.cpp)
target_link_libraries(my_animation PRIVATE DanceRudiments::DanceRudiments)
```

```cpp
#include <dancerudiments/dance_rudiments.hpp>
#include <dancerudiments/sampled_pattern.hpp>
#include <iostream>

int main() {
    const auto& items = dancerudiments::catalogue();
    std::cout << items.size() << " movements\n";

    const auto position = dancerudiments::sample("beat_amen_four_bar_bounce", 48);
    std::cout << position.x << ", " << position.y << ", " << position.z << '\n';

    // Negative pips wrap; the original named C++ functions are also retained.
    const auto previous = dancerudiments::sample("circle", -1);
    const auto direct = dancerudiments::circle(-1);
    return previous.x == direct.x ? 0 : 1;
}
```

Configure the consumer with `-DCMAKE_PREFIX_PATH=/absolute/path/to/install`.
Alternatively, point that prefix at an extracted, compatible native release
archive. A static archive is specific to its OS, architecture, compiler and
runtime-library settings; use a source build or the Conan recipe for another
combination. The exported target handles the Windows `DanceRudimentsCore.lib`
filename, so do not hard-code an archive name.

Run the complete installed-package example (it also checks custom-table ownership):

```sh
cmake -S examples/bindings/cpp -B build-example -DCMAKE_PREFIX_PATH="$PWD/install"
cmake --build build-example --config Release
ctest --test-dir build-example -C Release --output-on-failure
```

**Custom data:** `SampledPattern` copies and validates an `std::vector<Offset3>`;
`PatternLibrary` owns its custom patterns and also exposes all defaults. Construct
it once, not on every frame. `catalogue()` metadata contains `string_view`s, so a
custom library must outlive those views. Unknown names and invalid custom tables
raise C++ exceptions. See the complete
[C++ source](examples/bindings/cpp/main.cpp) and
[authoring guide](docs/authoring.md#native-api-reference).

### Python binding

Install a released package, or build the checkout to use unreleased additions:

```sh
python -m pip install --upgrade dancerudiments
# Alternative, from this checkout (requires a C++17 compiler):
python -m pip install .
```

A matching prebuilt wheel does not require a local C++ compiler. A source build
does; pip's isolated build installs the declared scikit-build-core/pybind11 build
dependencies. Use the same Python interpreter for `-m pip` and your application.
The package metadata supports Python 3.9+; release wheel availability is narrower
than every possible Python/OS/CPU combination.

```python
import dancerudiments as d

items = d.catalogue()
info = next(p for p in items if p["name"] == "beat_amen_four_bar_bounce")
print(len(items), "movements")
print(info["period_pips"] / d.PIPS_PER_BEAT, "beats per loop")

position = d.sample(info["name"], 48)
print(position.x, position.y, position.z)
print(position.as_tuple())

# Original named functions are also exposed. Generated names use sample().
assert d.circle(-1).as_tuple() == d.sample("circle", -1).as_tuple()
```

`Offset3` exposes read-only `x`, `y`, `z` and `as_tuple()`; it is not a dictionary
or NumPy array. `catalogue()` returns dictionaries with `name`, `description`,
`period_pips` and integer `dimensions`. Sample values come from C++, not a Python
reimplementation. Native invalid-argument errors are exposed as `ValueError`;
use integers and catch errors for untrusted names or data.

Run the complete example, including validated time-to-pip conversion:

```sh
python examples/bindings/python/quickstart.py
# Export the complete loop as pip/beat/XYZ rows:
python examples/bindings/python/sample_motion.py --name beat_amen_four_bar_bounce --csv amen.csv
```

**Author and load a private pattern:** compilation is a Python build-time step;
`.to_native()` transfers the result to a C++ bank for runtime playback.

```sh
python tools/compile_patterns.py compile examples/bindings/pulse.score.json --json generated/tutorial.json --cpp generated/tutorial.hpp
python examples/bindings/python/quickstart.py --pack generated/tutorial.json
```

```python
from dancerudiments_authoring import load_pack

compiled = load_pack("generated/tutorial.json")
library = compiled.to_native()
print(library.sample("tutorial_pulse", 0).as_tuple())
print(library.sample("circle", -1).as_tuple())  # Defaults remain available.
```

The generated C++ header can instead be included by a native application.
Existing collections are already defaults: loading `initial_pack()` or
`dancefloor_pack()` is for inspection/subsetting, not a prerequisite for ordinary
sampling. An exact default reload is idempotent; changing a default under the
same name is rejected. Give an edited movement a new identifier.

### TypeScript/WASM binding

The npm package contains a typed ES-module wrapper and a **separate Emscripten
factory and `.wasm` binary**. JavaScript uses the same API; omit the TypeScript
`import type` statements. Initialise the factory once before sampling:

```sh
npm install @kieransimkin/dance-rudiments
```

```ts
import { bindNative, catalogue, sample } from "@kieransimkin/dance-rudiments";
import type { RudimentName } from "@kieransimkin/dance-rudiments";
import createDanceRudiments from "@kieransimkin/dance-rudiments/wasm";

const native = await createDanceRudiments();
bindNative(native);

const name: RudimentName = "beat_amen_four_bar_bounce";
const info = catalogue.find(item => item.name === name);
if (!info) throw new Error("This release does not contain the requested movement");
console.log(catalogue.length, info.periodPips / 64);
console.log(sample(name, 48));  // { x, y, z }, sampled in C++/WASM
```

The currently untyped factory subpath has a small local declaration in
[`examples/bindings/typescript/wasm.d.ts`](examples/bindings/typescript/wasm.d.ts).
Include that file in a strict TypeScript project; it derives the module type from
`bindNative` rather than inventing another motion API. The wrapper itself already
ships its declarations.

**Node.js:** use ESM (`.mjs` or `"type": "module"`) and a current supported Node
version. With the package installed, run
`node examples/bindings/javascript/node.mjs`. The factory loads its adjacent
WASM binary. The source-build route below avoids relying on an older published
package.

**Browser:** serve the loader and its binary over HTTP(S). Keep them adjacent or
supply `locateFile: (file, prefix) => ...` to the factory when your bundler moves
assets. The server must return the WASM bytes rather than an HTML fallback page;
`application/wasm` is the appropriate MIME type. Bare package imports require a
bundler or import map. The checked-in browser example supplies a map for a local
source build, starts paused, and preserves beat position when BPM changes.

To build from source, activate an Emscripten SDK environment first, then run from
the repository root:

```sh
npm ci
npm run build:harness
emcmake cmake -S . -B build-wasm -DCMAKE_BUILD_TYPE=Release -DDANCERUDIMENTS_BUILD_WASM=ON -DDANCERUDIMENTS_BUILD_TESTS=OFF
cmake --build build-wasm --config Release
node examples/bindings/javascript/node.mjs ./dist/typescript/index.js ./build-wasm/dancerudiments.js
npx tsc -p examples/bindings/typescript/tsconfig.json
python -m http.server 4173
```

Open `http://localhost:4173/examples/bindings/typescript/`. This small consumer is
not self-contained; the **main visualizer linked at the top of the README is**.
The visualizer's compact snapshot-WASM interface is not an Embind module and must
not be passed to `bindNative()`. No JavaScript fallback computes movement here.

**Custom compiled packs and cleanup:** fetch or import the JSON, then explicitly
release its native memory when finished:

```ts
import { createPatternLibrary } from "@kieransimkin/dance-rudiments";

const response = await fetch("/generated/tutorial.json");
if (!response.ok) throw new Error(`Pack request failed: ${response.status}`);
const bank = createPatternLibrary(await response.json());
try {
    console.log(bank.sample("tutorial_pulse", -1));
    console.log(bank.catalogue());
} finally {
    bank.dispose();
}
```

Create the bank after binding the native module. A disposed bank must not be
sampled. `dispose()` is idempotent; the wrapper releases its temporary native
objects automatically. The global default catalogue does not need disposal.
Keep a library alive for the lifetime of an animation rather than constructing it
inside `requestAnimationFrame`.

### Limits, attribution and troubleshooting

A private pack accepts at most 1,024 patterns and 1,048,576 total samples; a single
pattern is 1–65,535 pips long. These custom-pack validation limits are separate
from the larger built-in catalogue. Imported content retains its original
licences and notices: copying generated tables does not remove attribution.

The author/project link is **[Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/)**.
It is retained in package metadata, the packaged READMEs, `AUTHORS.md`, CMake and
Conan descriptions, and the C++ release's `PACKAGE-INFO.txt`. Original upstream
licences are not modified to insert project branding.

[Binding examples and screenshot notes](docs/bindings.md) ·
[Complete authoring format](docs/authoring.md) ·
[Historical build troubleshooting](docs/troubleshooting.md).

## Harness

Use the **self-contained HTML link at the top**. No server is required for that
page. Its 305 beat/event scores include the complete four-bar Amen study; all
1,731 movements remain available. Choose a score, press **Play**, set **BPM**,
and optionally restrict the catalogue to matching movements. The transport
coordinates synthesized MIDI notes and integer-pip C++/WASM motion.

![MIDI instrument lanes, event strengths and comparison controls](https://raw.githubusercontent.com/kieransimkin/DanceRudiments/main/docs/images/visualizer-midi-score.png)

The score view includes ghost-note strengths, fractional event positions, lane
mutes, MIDI import and export. It is a timing aid, not a General MIDI soundfont
emulator or the original Amen recording. View the
[mobile screenshot](docs/images/visualizer-mobile.png) or the
[full harness guide](docs/midi-harness.md).

For rebuilding rather than simply viewing, use `python tools/build_harness.py`
after installing this checkout's native extension. The builder also needs
`clang++` and `wasm-ld`; screenshot automation needs Playwright/Chromium. Those
are build-time requirements, not dependencies of the downloaded HTML.


## Continuous integration and releases

`.github/workflows/ci.yml` builds and tests the C++ core on Linux, Windows, and macOS; builds and imports the Python package; compiles/tests the TypeScript and browser runtime; and creates a Conan package on every push to `main` and every pull request.

Publishing is deliberately tied to a GitHub release with a `vMAJOR.MINOR.PATCH` tag. Before creating the release, update the matching version in `CMakeLists.txt`, `pyproject.toml`, and `package.json`. `.github/workflows/release.yml` rejects mismatches before it publishes anything, then:

- builds platform Python wheels and a source distribution and publishes them to PyPI using OIDC Trusted Publishing;
- builds the TypeScript wrapper and C++ WebAssembly module and publishes `@kieransimkin/dance-rudiments` to npm using the configured publishing credentials and provenance;
- builds installable C++ archives for Linux, Windows, and macOS and attaches them to the GitHub release; and
- builds a Conan package and uploads it only when a separate Conan remote has been configured. ConanCenter packages are submitted through `conan-center-index`; they are not directly uploaded by this repository.

One-time registry configuration is required before the first release:

1. On PyPI, create a pending Trusted Publisher for owner `kieransimkin`, repository `DanceRudiments`, workflow `release.yml`, environment `pypi`, and project name `dancerudiments`.
2. On npm, configure the package's GitHub Actions Trusted Publisher for `kieransimkin/DanceRudiments`, workflow `release.yml`, environment `npm`, with direct publishing allowed. Because npm Trusted Publishers are configured from an existing package's settings, the first scoped-package registration may require a granular `NPM_TOKEN` secret in the `npm` environment. Remove that bootstrap token after Trusted Publishing is configured.
3. Create GitHub environments named `pypi`, `npm`, and `conan`; add required reviewers if desired.
4. For an optional private or organisational Conan repository, set environment variable `CONAN_REMOTE_URL` and secrets `CONAN_LOGIN_USERNAME` and `CONAN_PASSWORD` in the `conan` environment. If they are absent, the recipe is built and verified but not uploaded.

The PyPI publishing job requests short-lived OIDC identity. npm can use Trusted Publishing when configured; the workflow retains `NPM_TOKEN` as a bootstrap/fallback credential. See the official [PyPI Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/) and [npm Trusted Publishing](https://docs.npmjs.com/trusted-publishers/) documentation.

## Motion safety

Apply an output to a bounded subject. DanceRudiments changes position only; it must not be used to add a repetitive full-frame tint, brightness, flash, or colour-grade effect. Under `prefers-reduced-motion`, do not autoplay the harness or production motion.

## Troubleshooting history

See [build and release troubleshooting](docs/troubleshooting.md) for prior failures, causes and fixes.
