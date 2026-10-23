# DanceRudiments

[![DanceRudiments logo](https://raw.githubusercontent.com/kieransimkin/DanceRudiments/v0.2.3/docs/branding/logo.png)](https://kieransimkin.co.uk/danceflow/)

By **[Kieran Simkin](https://kieransimkin.co.uk/)** · [DanceFlow ecosystem](https://kieransimkin.co.uk/danceflow/) · [Vector logo and usage guide](docs/branding/README.md).

Deterministic rhythmic position functions with C++, Python, TypeScript/WASM and C# bindings. https://kieransimkin.co.uk/


By **[Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/)** · Part of the **DanceFlow** motion workflow.

[Visualizer](#visualizer) · [Language bindings](#language-bindings) · [C++](#c-binding) · [Python](#python-binding) · [C# / .NET](#csharp-binding) · [TypeScript / JavaScript](#typescriptwasm-binding)

<a id="visualizer"></a>

## Before every new workflow

Check the latest stable official release and the actual installed/imported version before starting; do not infer currency from a directory name or a development checkout. Read the current release notes, tagged capability documentation and relevant Potential problems. Use the [DanceFlow release preflight](https://github.com/kieransimkin/DanceFlow/blob/main/docs/workflows/release-preflight.md) and [complete capability references](https://github.com/kieransimkin/DanceFlow/blob/main/docs/capabilities/index.md).

People and agents should consider the full ecosystem, use all capabilities that materially serve the task, compose supported files/APIs, and improve a demonstrated reusable gap in its canonical tool. Record why no worthwhile change is justified when that is the result. Keep independent tool identities, compatibility, source clocks, privacy, model/download costs and publication/deployment permissions intact. Store weights and model-specific caches in the owning project's ignored `models/`.

## Find your route

[▶ Try the pattern visualizer](#-try-the-pattern-visualizer) · [3D dance examples](#3d-dance-examples) · [Which package should I use?](#which-package-should-i-use) · [Included rudiments](#included-rudiments) · [Default collections](#default-collections) · [Dancefloor 06](#dancefloor-06) · [BPM-synchronised N-dimensional recordings and comparison harness](#bpm-synchronised-n-dimensional-recordings-and-comparison-harness) · [Rigify character motion](#rigify-character-motion) · [Curve and event authoring](#curve-and-event-authoring) · [Language bindings](#language-bindings) · [Harness](#harness)

## ▶ Try the pattern visualizer

**[▶ Open the movement visualiser](https://kieransimkin.github.io/DanceRudiments/)**

[Download the self-contained HTML for offline use](https://github.com/kieransimkin/DanceRudiments/raw/refs/heads/main/harness/index.html)

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
workflow also rebuilds and tests a fresh artifact from every pushed native catalogue.
The **Release demo** workflow publishes the complete tagged site, including the
3D examples below, when Pages is enabled. Main-branch visualizer builds do not
replace that released site.
[Beat player, rebuilding, release downloads and optional live hosting](docs/midi-harness.md).

[![Four Amen-based movements compared in the real self-contained visualizer](https://raw.githubusercontent.com/kieransimkin/DanceRudiments/main/docs/images/visualizer-amen-desktop.png)](https://kieransimkin.github.io/DanceRudiments/)

*Captured from the running C++/WebAssembly visualizer at beat 2.75. Audio was not started during this screenshot.*

## 3D dance examples

The release build includes a separate **`meshes/` gallery** beside the pattern
visualizer. The production character is **Kandi Boom** from *Bass Ben & Friends*,
using the real checked-in FBX, 24-bone rig and PBR textures. Two pinned optional
source-motion packages can drive her through an explicit source-rig → Kandi
retarget adapter:

| Character | Movement | Source recording |
| --- | --- | --- |
| Kandi Boom | Salsa | CMU 60_01, with the reviewed 60 fps source timing restored |
| Kandi Boom | Ballet sequence: attitude, arabesque, turning jump and back bend | CMU 05_18 |

The source recordings preserve their own skeleton profiles, original timing and
calibration frames. The retained converter calibration T-pose establishes a
per-control retarget reference pose: Kandi keeps her FBX joint positions and
proportions, while each mapped continuation bone is oriented to the corresponding
CMU calibration direction before captured rotation deltas are applied. This is
especially important for the arms because Kandi's authored bind pose is a steep
A-pose while the CMU converter frame is near-T. Kandi's external PBR maps also
inherit the FBX diffuse map's image-Y orientation, UV channel, wrapping, scale
and translation instead of assuming glTF texture coordinates.
The captures have no verified musical beat/downbeat annotations and are not
presented as beat-matched to a song. Loading a performance fetches only its
optional motion package plus the hash-pinned Kandi target assets; switching
performances unloads the previous recording and target scene. Play, pause, seek,
restart and preview speed continue to use the existing native C++/WASM sampler.

### Playback-rate interpretations for rigged motion

The Kandi Boom gallery offers **half time (0.5Ã—)**, **original time (1Ã—)**
and **double time (2Ã—)** in addition to the 0.75Ã— and 1.5Ã— preview
rates. The TypeScript `motionTimeRate` and `motionSourcePipAtTime`
helpers convert elapsed presentation time to an original source pip.
The motion stays on the native 64-pip source clock, with no implicit
audio synchronisation, source-BPM correction, wrapping or resampling.

The gallery also supports **local StemLab rhythm-analysis review**. After loading
Kandi, import the corresponding `stemlab.rig-motion-analysis` JSON from the
complete salsa/ballet package. Source hashes and channel identity are validated
before estimated motion beats and selectable loop-preview boundaries appear on
the existing timeline. The analysis file stays in the browser; no musical
beat/downbeat approval, audio synchronisation or seam/foot-contact repair is
implied. See [mesh-demo rhythm review](docs/mesh-demos.md#review-motion-rhythm-and-loop-candidates).

For newly imported animation, the optional **source-first StemLab loop job**
analyses original BVH frames or evaluated Blender Action captures **before**
resampling to the native 64-pip grid. It ranks source-time beat and loop
hypotheses, then creates independent, review-only RigMotion previews; it never
changes the full source motions or adds assets to the default catalogue. Run
`python tools/analyze_source_motion.py original.bvh --output-dir .cache/source-loops/action`
or analyse all reviewed, locally cached source archives with
`python tools/analyze_motion_collection.py --sources cmu_dance`. See the
[source-first analysis guide](docs/source-loop-analysis.md). Musical beat-1,
audio alignment, rig deformation and repeat seams still require separate checks.

Kandi's canonical FBX contains vertices with more than four source influences.
The source remains untouched and fully audited; the WebGL renderer uses an
explicit, normalised four-weight runtime approximation and records that limit in
the build/browser evidence. The target is a custom Kandi rig, not a Rigify rig.

The release workflow browser-tests both performances on the real Kandi mesh,
attaches gallery/complete-site archives and deploys the existing visualizer and
gallery together when Pages is enabled. See [building and validating the Kandi
Boom motion demo](docs/mesh-demos.md) and the [release workflow guide](docs/release-demo.md).

DanceRudiments is a C++17 library of deterministic rhythmic position functions. One integer pip is `1/64` of a beat. Built-in and custom patterns each keep their own loop period. Every legacy pattern sampler wraps positive or negative input into its own loop before sampling.

Outputs are dimensionless offsets, normally in `[-1, 1]`. The caller chooses pixels, CSS units, metres, or another scale. There is deliberately no time interpolation in the public API: renderers advance with integer pips and get one exact sample per pip.

## Which package should I use?

| You are building | Install or download | What you get |
| --- | --- | --- |
| C# / .NET application | `dotnet add package DanceRudiments` from [NuGet.org](https://www.nuget.org/packages/DanceRudiments) after its first release | Managed .NET 8+ wrapper and x64/ARM64 native assets for Windows, Linux and macOS |
| Python application | `pip install dancerudiments` from [PyPI](https://pypi.org/project/dancerudiments/) | Native Python extension and the catalogue/sample API |
| TypeScript or JavaScript application | `npm install @kieransimkin/dance-rudiments` from [npm](https://www.npmjs.com/package/@kieransimkin/dance-rudiments) | TypeScript declarations, JavaScript wrapper, and WebAssembly module |
| C++ application using a listed release platform | Download the matching `DanceRudiments-cpp-<version>-<platform>-static.zip` from [GitHub Releases](https://github.com/kieransimkin/DanceRudiments/releases) | Headers, static library, CMake package files, licence, platform manifest, and instructions |
| C++ application using another toolchain or architecture | Build from source or use `conan create` with `conanfile.py` | A library compiled for your own settings |

GitHub automatically adds “Source code” ZIP and tar.gz links to every release; those are repository snapshots, not precompiled packages. Python wheels belong on PyPI, the C# package on NuGet.org (mirrored to GitHub Packages), and the TypeScript/WASM package on npm, while GitHub release attachments include C++ archives and the separately generated HTML demos, screenshots and checksums.

## Included rudiments

The general motions are `bounce`, `sway`, `circle`, `figure_eight`, `step_touch`, `box_step`, `helix`, and `clay_background`.

The first drum-derived set is `single_stroke_roll`, `multiple_bounce_roll`, `double_stroke_roll`, `single_paradiddle`, `flam`, `drag`, and `five_stroke_roll`. The first six mirror the fundamentals in Vic Firth's Tier One learning sequence and collectively cover the roll, diddle, flam, and drag families in the Percussive Arts Society's 40 International Drum Rudiments. A right-hand stroke moves right, a left-hand stroke moves left, and both rise slightly. Every stroke is a raised-cosine (`sin²`) gesture: zero displacement at the start, smooth attack, a rounded peak, and smooth decay back to zero before the next motion. Accents use greater amplitude rather than an instantaneous position jump.

Source references: [Percussive Arts Society International Drum Rudiments](https://pas.org/rudiments/) and [Vic Firth 40 Essential Rudiments](https://ae.vicfirth.com/education/40-essential-rudiments/), accessed 28 September 2026.

`clay_background` preserves the translation waypoints from the Clay/Stars `ks-particle-dance` background treatment as a normalized 256-pip lookup table. The source effect's opacity, rotation, and scale are not position offsets, so they are intentionally excluded.

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

## BPM-synchronised N-dimensional recordings and comparison harness

The additive `dancerudiments.recording` format stores **any number of named
float64 dimensions** at **64 pips per beat**, with a mandatory BPM estimate or
confirmed value and separate beat-phase provenance. `SampledRecording` provides
native non-looping C++/Python playback, including captures beyond the old
65,535-pip loop length; existing XYZ patterns and their wrapping rules are unchanged.

```python
from dancerudiments_authoring import load_recording
from dancerudiments_authoring.harness import build_recording_harness
r = load_recording("output/recordings/audio_recording.json")
values = r.to_native().sample(r.clock.start_pip)  # every dimension, real C++
build_recording_harness([r], "output/index.html")
```

The exported page uses **the same packaged visualizer assets as catalogue/release
pages**, with native WASM sampling, shared transport, four-card comparison and
review import/export. Recording mode adds arbitrary-axis X/Y/Z selection, locked
BPM/origin and non-looping completion. The tiny generic WASM sampler is bundled;
no compiler or CDN is needed at export time. StemLab's `record-rudiment` and
`generate-batch` produce individual or varied stem/filter combinations using this
API without copying it. Music is not bundled unless explicitly requested.

See **[recording format, harness, native API and compatibility](docs/recordings.md)**.
Build the updated source to use this unreleased API; earlier releases lack it.

## Rigify character motion

Typed rig motions now bind the native N-dimensional recording sampler to **Blender
Rigify character controls**. The pinned Blender **5.2.2 LTS** catalogue covers all
**eight built-in metarig presets** and **28 rig component types**, with numbered
channel manifests generated from actual rigs. Each channel identifies its bone,
property, component, physical units, range, neutral value and interpolation.
The [catalogue guide](docs/rigify-catalogue.md) records exact counts and any
component context; custom/generated characters can export their own profiles.

Model types use a hierarchy such as
`syn://type/danceflow/motion/rigify/metarig/human` and
`syn://type/danceflow/motion/rigify/component/limbs/arm`.
`synny://` is an equivalent spelling, not another type. Channel numbers persist
across explicit profile extensions; profile hashes prevent applying a recording
to an incompatible skeleton, rest basis or control layout.

```sh
python tools/rig_motion.py catalogue
python tools/rig_motion.py profile human --output generated/human.profile.json
python tools/rig_motion.py channels generated/human.profile.json --output generated/human.channels.csv
python examples/rig-motion/quickstart.py --output generated/rig-motion --native
```

The installed CLI is `dancerudiments-rig`. The optional Blender bridge imports
local **BVH, FBX and glTF/GLB**, captures animation already retargeted/baked onto
Rigify controls, and applies or bakes motion using the actual native sampler.
`dancerudiments.rig-motion` combines an exact profile with the unchanged normalized
Recording format: float64 `[-1,1]`, 64 pips/beat, explicit bounds and non-looping
playback. Scalar controls interpolate linearly during authoring, quaternion
groups use shortest-path SLERP, and discrete switches hold their values.

Source BPM/phase or measured beat anchors control compilation. A separate target
beat map permits variable-tempo playback, absolute seeking and explicit
half/double-time without accumulating frame-clock drift. The existing XYZ
catalogue and C++ playback engine remain the movement authority.

Read the **[complete rig-motion guide](docs/rig-motion.md)** for capture, compile,
native playback, Blender baking, actual model mappings and compatibility. The
**[motion-source research](docs/motion-sources.md)** records motion libraries and
their format/licence/access constraints. The
**[Blender import guide](docs/blender-motion-import.md)** covers multiple Actions,
source-skeleton reconstruction and explicit Rigify FK mappings. Musical beat
detection and foot-contact/transition repair remain separate authoring steps.
The dedicated **Rigify motion** CI checks native playback and an
actual skinned mesh using the pinned Blender runtime. These APIs require this
development revision until a new stable package is released.

### Optional model-specific motion packages

Large character recordings are **independent optional packages**. They are not
added to the 1,731 default rudiments, fetched at startup or loaded site-wide.
Each package shares one exact numbered rig profile and stores individual
compressed recordings with hashes, timing, source attribution and licence.
Only the selected page or scene loads its requested clips.

The new TypeScript `./motion-packages` subpath provides a lazy, scene-owned loader
and the existing native C++/WASM recording accessor. The
[page lifecycle example](examples/motion-packages/page-motion.mjs) follows the
host's integer beat clock, keeps one recording chunk loaded, handles seeking and
releases requests/memory on route exit. Rig application remains the consuming
scene's responsibility; the existing XYZ visualizer does not become a mesh renderer.

Python provides `MotionPackage`, `MotionPackageBuilder` and the explicit
`dancerudiments-motion-pack` install/inspect/export CLI. Offline BVH import uses
the optional `motion-import` extra; the base package does not acquire NumPy or
Blender dependencies. Public source plans and reproducible import tools produce
external data under ignored `motion-packs/`; the base npm/Python/native packages
exclude those assets.

Reproducible source recipes cover ACCAD human actions, 100STYLE locomotion,
Lifelike Agility dog captures, Space-XR dance/movement recordings, a deduplicated
CMU dance subset and all 14
Actions of Quaternius' CC0 robot. The [source plan index](motion-packages/README.md)
records separate data terms and acquisition commands. A collection can be large
without increasing the base package or its startup work.

```sh
python -m pip install '.[motion-import]'
python tools/import_motion_collection.py download --sources accad
python tools/import_motion_collection.py build --sources accad
python tools/motion_package.py list --root ./motion-packs
```

Complete source actions can span contiguous bounded chunks. Unknown musical
timing is labelled **time-only**: a 60 BPM seconds coordinate is not an observed
music tempo. Supply source tempo and beat phase or measured beat anchors before
claiming musical alignment. The [optional-package guide](docs/motion-packages.md)
describes formats, hosting, exact profile compatibility, source conventions,
native playback and separate package licences.

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

## Language bindings

All four language interfaces sample the **same C++ runtime**. Choose the interface, not
another movement implementation. The examples below are checked into
[`examples/bindings/`](examples/bindings/) so they can be built and tested.

| Interface | Catalogue | Sample | Loop-length field | Custom-library lifetime |
| --- | --- | --- | --- | --- |
| C++17 | `dancerudiments::catalogue()` | `dancerudiments::sample(name, pip)` | `period_pips` | Owned by its C++ object; normal RAII |
| Python | `d.catalogue()` | `d.sample(name, pip)` | `info["period_pips"]` | Owned by the Python object wrapping C++ |
| C# / .NET | `Rudiments.Catalogue` | `Rudiments.Sample(name, pip)` | `info.PeriodPips` | `using` / `Dispose()` for custom banks |
| TypeScript / JavaScript | `catalogue` (an array, not a function) | `sample(name, pip)` after `bindNative()` | `info.periodPips` | Call the custom bank's `dispose()` |

**One beat is 64 pips.** Supply a signed 32-bit integer, not milliseconds or a
floating-point beat number. Every legacy pattern sampler wraps negative as well as positive
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

<a id="csharp-binding"></a>

### C# / .NET binding

The **DanceRudiments** NuGet package wraps the original C++ library through a
versioned, exception-safe C ABI. It targets .NET 8+ desktop/server applications;
CI tests .NET 8 and .NET 10. Native Windows, Linux and macOS libraries are included
for x64 and ARM64, with automatic NuGet/.NET runtime selection. This does not
claim support for .NET Framework, Unity, mobile or browser-WASM hosts.

After the first release containing this binding has been published:

```sh
dotnet add package DanceRudiments
```

```csharp
using DanceRudiments;

Console.WriteLine(Rudiments.NativeVersion);
var amen = Rudiments.Catalogue.Single(p => p.Name == "beat_amen_four_bar_bounce");
int pip = Rudiments.PipAtTime(1.25, bpm: 140, periodPips: amen.PeriodPips);
Offset3 position = Rudiments.Sample(amen.Name, pip);
Console.WriteLine($"{position.X}, {position.Y}, {position.Z}");

// Full-loop export: one interop call; every sample is still calculated in C++.
Offset3[] loop = Rudiments.SampleMany(amen.Name, 0, amen.PeriodPips);
```

`Offset3` has read-only double-precision `X`, `Y`, `Z` fields. Negative pips wrap
normally. `SampleInto` fills an existing span; batches handle int32-boundary
crossings safely. `PatternLibrary.Load` / `FromJson` read the same compiled JSON
packs as the other bindings; a custom bank owns copies of its tables and should
be enclosed in `using`. SafeHandle protects native lifetime, including concurrent
sampling. No movements are reimplemented in C# and there is no Python dependency
at playback time.

For a checkout build, enable `-DDANCERUDIMENTS_BUILD_C_ABI=ON` in CMake, then build
`bindings/csharp/DanceRudiments/DanceRudiments.csproj` with `dotnet`. The
[runnable C# example](examples/bindings/csharp/Program.cs) and
[complete C# guide](docs/csharp.md) cover native loading, custom packs, supported
platform baselines, source development and one-time registry configuration.
[The NuGet README](bindings/csharp/README.md) is included in the output package
along with your usage guide, screenshots and
[Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/).

`.github/workflows/csharp.yml` builds/tests all six native targets, creates one
complete nupkg, and tests installing it on each target. A published GitHub release
then uploads to **NuGet.org and GitHub Packages**, plus release attachments.
Ordinary pushes and pull requests only build/test and retain CI artifacts.
NuGet.org requires a configured trusted publisher and `NUGET_USER`; see
[release setup](docs/csharp.md#one-time-nugetorg-setup). Until publication, use the
checkout or the `csharp-nuget` CI artifact; merging this code alone does not publish.

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

## DanceFlow ecosystem

DanceRudiments is the reusable motion-vocabulary layer in Kieran Simkin's DanceFlow BPM and motion-response ecosystem:

- **StemLab** is the music-understanding layer. It analyses audio to produce BPM, beat, structure, stem, lyric, harmony, and related timing evidence.
- **DanceRudiments** turns integer musical positions at 64 pips per beat into deterministic 1D, 2D, or 3D position offsets.
- **DanceMoves** is the WordPress EPK motion runtime. It schedules and applies BPM-, cue-, and lyric-timed effects on public pages.

The three components can also be used independently. They exchange explicit timing and analysis data rather than depending directly on one another. DanceRudiments' 64-pips-per-beat sampling convention is intentionally higher resolution and is not the same unit as DanceMoves' 16-ticks-per-beat runtime clock.

## Motion safety

Apply an output to a bounded subject. DanceRudiments changes position only; it must not be used to add a repetitive full-frame tint, brightness, flash, or colour-grade effect. Under `prefers-reduced-motion`, do not autoplay the harness or production motion.

## Troubleshooting history

See [build and release troubleshooting](docs/troubleshooting.md) for prior failures, causes and fixes.

### Switch the shared visualizer between trajectories and bars

Use **Movement view → X–Y plot / Bar graph**. Bar view uses the same native
C++/WebAssembly sample and the existing clock, shows **every dimension** as a
separate signed bar, and keeps comparison cards on one common scale. Switching
views does not interrupt playback or change the underlying recording. The
selection is local to your browser; long dimension sets scroll horizontally.
This applies to catalogue/release pages and recording harnesses exported by
StemLab. Rebuild old generated pages to include the control. See
[recording visualizer controls](docs/recordings.md#trajectory-or-all-dimension-bars).

## Continuous integration and releases

Run `python tools/check_package_docs.py` before packaging. Its source preflight
checks nested first-party `README.md` files in the package input trees, including
rig-motion examples and optional source-plan documentation, for the canonical
author music link. Third-party `sources/` documentation retains its original
attribution. Release jobs also check the actual archives; passing source checks
does not establish package publication or registry availability.

Tagged Pages deployments require an allowed **Tag** rule in the existing
`github-pages` environment, in addition to any allowed `main` branch rule.
A maintainer must explicitly authorize the intended release tags; the workflow
does not change environment protections. See [release demo recovery](docs/release-demo.md#recovering-a-deployment-rejected-by-environment-rules)
for retrying an already built site without rebuilding its immutable release assets.

The additional `.github/workflows/csharp.yml` builds the shared C ABI and C# wrapper, tests actual installed NuGet packages, and publishes .NET packages only for release tags. Its NuGet.org setup is documented in [the C# guide](docs/csharp.md).

`.github/workflows/ci.yml` builds and tests the C++ core on Linux, Windows, and macOS; builds and imports the Python package; compiles/tests the TypeScript and browser runtime; and creates a Conan package on every push to `main` and every pull request.

**A pushed `vMAJOR.MINOR.PATCH` tag is the CD trigger.** Use the release helper so all five version locations stay in sync:

```sh
python tools/release_version.py prepare 0.2.0
git diff
git add CMakeLists.txt pyproject.toml package.json package-lock.json bindings/csharp/DanceRudiments/DanceRudiments.csproj
git commit -m "Prepare v0.2.0 release"
git push
# Wait for the normal main-branch CI to pass, then:
python tools/release_version.py tag 0.2.0 --push
```

`prepare` updates CMake, Python/PyPI, npm + its lockfile and C#/NuGet together. `tag` refuses a dirty worktree, a non-`main` branch, mismatched manifests or an existing tag. The pushed tag runs `.github/workflows/release-tag.yml`, which revalidates the exact tagged checkout and creates the GitHub Release. The package and demo workflows are also tag-triggered; they do not depend on a GitHub Release event generated by another workflow.

`.github/workflows/release.yml` rejects mismatches before it publishes anything, then:

- builds platform Python wheels and a source distribution and publishes them to PyPI using OIDC Trusted Publishing;
- builds the TypeScript wrapper and C++ WebAssembly module and publishes `@kieransimkin/dance-rudiments` to npm using the configured publishing credentials and provenance;
- builds installable C++ archives for Linux, Windows, and macOS and attaches them to the GitHub release; and
- builds a Conan package and uploads it only when a separate Conan remote has been configured. ConanCenter packages are submitted through `conan-center-index`; they are not directly uploaded by this repository.

One-time registry configuration is required before the first release:

1. On PyPI, create a pending Trusted Publisher for owner `kieransimkin`, repository `DanceRudiments`, workflow `release.yml`, environment `pypi`, and project name `dancerudiments`.
2. On npm, configure the package's GitHub Actions Trusted Publisher for `kieransimkin/DanceRudiments`, workflow `release.yml`, environment `npm`, with direct publishing allowed. Because npm Trusted Publishers are configured from an existing package's settings, the first scoped-package registration may require a granular `NPM_TOKEN` secret in the `npm` environment. Remove that bootstrap token after Trusted Publishing is configured.
3. Create GitHub environments named `pypi`, `npm`, and `conan`; add required reviewers if desired.
4. For an optional private or organisational Conan repository, set environment variable `CONAN_REMOTE_URL` and secrets `CONAN_LOGIN_USERNAME` and `CONAN_PASSWORD` in the `conan` environment. If they are absent, the recipe is built and verified but not uploaded.
5. For C#, configure the `nuget` environment and NuGet.org Trusted Publisher as described in [the C# guide](docs/csharp.md#one-time-nugetorg-setup).

The PyPI publishing job requests short-lived OIDC identity. npm can use Trusted Publishing when configured; the workflow retains `NPM_TOKEN` as a bootstrap/fallback credential. See the official [PyPI Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/) and [npm Trusted Publishing](https://docs.npmjs.com/trusted-publishers/) documentation.

## Coordinated releases and latest-release dependencies

Keep `DanceRudiments`, `react-timeline-sequence`, and `stemlab` as sibling
checkouts. The release order is **React Timeline Sequence → DanceRudiments →
StemLab**: publish and verify the companions before updating the consuming app.
StemLab must use their **latest stable official releases**, not an unreleased
commit, sibling source package or vendored npm archive. Each build records exact
released versions/commits/integrity after latest-release resolution so all its
jobs use the same bytes; CI fails clearly when that snapshot is stale.

From the parent folder, preview and then explicitly execute:

```powershell
.\stemlab\scripts\Release-DanceFlow.ps1 -ProjectsRoot .
.\stemlab\scripts\Release-DanceFlow.ps1 -ProjectsRoot . -Execute
```

For the first migration use the same commands with
`.\release-kit\Release-DanceFlow.ps1` after extracting the complete kit. It
applies the three repository patches, updates versions, performs scoped commits
and normal pushes, waits for exact-commit CI, then creates **new** release tags.
The existing GitHub Actions workflows publish packages; no protection rules,
credentials, old tags or assets are changed. The initial expected next-minor
versions are only a preview proposal, never a claim that they are published.

Use Node.js 24, Python 3.11+, PowerShell 5.1+, Git and authenticated GitHub CLI.
Required main/registry/Pages jobs must pass; missing approvals and partial
publication are blockers, not success. The default script releases all three
projects, is opt-in via `-Execute`, and supports a saved exact-source `-Resume`
session. A changed checkout or pre-commit build failure requires review rather
than an automatic stash/reset or guessed recovery.

StemLab's helper updates npm manifests/lock, optional native dependency minimum,
release/build metadata and the genuinely rebuilt JS/CSS together. Its daily
release-update workflow proposes subsequent updates by PR without auto-merging.
A tagged StemLab release generates all four Arcadians pages and validates actual
Pages deployment, live HTML and seekable audio. Do not start a duplicate manual
Arcadians analysis during that tagged build. Read
**[the full release, resume, verification and troubleshooting guide](docs/released-viewers.md)**
before running it. Keep this README and AGENTS.md synchronized with future changes.

## Agents and contributors

Agents using DanceRudiments should inspect its available capabilities, use them fully where they fit the task, and look for useful improvements wherever possible. When a required feature is missing, or a reusable reliability, usability, performance or documentation gap is found, improve this tool rather than maintaining a separate workaround. If no worthwhile change is justified, explain why.

Submit every improvement as a pull request to [DanceRudiments](https://github.com/kieransimkin/DanceRudiments/pulls), with relevant tests, documentation and a reproducible example. Follow [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) for the contribution and validation workflow.

Project website: [https://kieransimkin.co.uk/danceflow/](https://kieransimkin.co.uk/danceflow/).
