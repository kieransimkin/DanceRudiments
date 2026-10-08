# DanceRudiments C++ static library

[![DanceRudiments logo](https://raw.githubusercontent.com/kieransimkin/DanceRudiments/v0.2.2/docs/branding/logo.png)](https://kieransimkin.co.uk/danceflow/)

[DanceFlow](https://kieransimkin.co.uk/danceflow/) · [Kieran Simkin](https://kieransimkin.co.uk/)

By **[Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/)**.

The illustrated multi-language guide and runnable examples are installed under
`share/DanceRudiments/README.md`, `share/DanceRudiments/docs/` and
`share/DanceRudiments/examples/bindings/`.

This archive is for C++ applications on the platform named in the ZIP filename.
It does not contain the Python, C#/.NET or TypeScript/WASM packages; install those from
PyPI, NuGet.org or npm instead.

## DanceFlow ecosystem

DanceRudiments is the reusable motion-vocabulary layer in Kieran Simkin's
DanceFlow BPM and motion-response ecosystem. StemLab supplies music-analysis
and timing evidence, DanceRudiments maps integer positions at 64 pips per beat
to deterministic spatial offsets, and DanceMoves applies BPM-, cue-, and
lyric-timed effects in WordPress EPKs.

The components are independently usable and exchange explicit data rather than
having hard runtime dependencies. DanceRudiments pips are not the same unit as
DanceMoves' 16-ticks-per-beat runtime clock.

## Contents

- `include/dancerudiments/dance_rudiments.hpp` — public C++ API
- `lib/` — compiled static library
- `lib/cmake/DanceRudiments/` — CMake package configuration
- `PACKAGE-INFO.txt` — exact version, platform, architecture, and library type
- `LICENSE` — MIT licence

## Use from CMake

Extract this archive somewhere stable, then point CMake at the extracted root:

```cmake
find_package(DanceRudiments CONFIG REQUIRED)
target_link_libraries(your_target PRIVATE DanceRudiments::DanceRudiments)
```

```sh
cmake -S . -B build -DCMAKE_PREFIX_PATH=/path/to/DanceRudiments-VERSION
cmake --build build
```

The archive contains a static library for one operating system and CPU. C++
compiler and runtime-library compatibility still applies; use the source or
Conan recipe when you need a different architecture or toolchain.

## Other language packages

- Python: `pip install dancerudiments`
- TypeScript/WASM: `npm install @kieransimkin/dance-rudiments`
- C#/.NET: `dotnet add package DanceRudiments` (after its first NuGet release)
