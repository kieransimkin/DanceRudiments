# DanceRudiments

DanceRudiments is a small C++17 library of deterministic rhythmic position functions. One integer pip is `1/64` of a beat. Every rudiment owns a 64-, 128-, or 256-pip loop and wraps any positive or negative input into that loop before sampling.

Outputs are dimensionless offsets, normally in `[-1, 1]`. The caller chooses pixels, CSS units, metres, or another scale. There is deliberately no time interpolation in the public API: renderers advance with integer pips and get one exact sample per pip.

## Included rudiments

The general motions are `bounce`, `sway`, `circle`, `figure_eight`, `step_touch`, `box_step`, `helix`, and `clay_background`.

The first drum-derived set is `single_stroke_roll`, `multiple_bounce_roll`, `double_stroke_roll`, `single_paradiddle`, `flam`, `drag`, and `five_stroke_roll`. The first six mirror the fundamentals in Vic Firth's Tier One learning sequence and collectively cover the roll, diddle, flam, and drag families in the Percussive Arts Society's 40 International Drum Rudiments. A right-hand stroke moves right, a left-hand stroke moves left, and both rise slightly. Every stroke is a raised-cosine (`sin²`) gesture: zero displacement at the start, smooth attack, a rounded peak, and smooth decay back to zero before the next motion. Accents use greater amplitude rather than an instantaneous position jump.

Source references: [Percussive Arts Society International Drum Rudiments](https://pas.org/rudiments/) and [Vic Firth 40 Essential Rudiments](https://ae.vicfirth.com/education/40-essential-rudiments/), accessed 28 September 2026.

`clay_background` preserves the translation waypoints from the Clay/Stars `ks-particle-dance` background treatment as a normalized 256-pip lookup table. The source effect's opacity, rotation, and scale are not position offsets, so they are intentionally excluded.

## Build and test the C++ core

```powershell
cmake -S . -B build -G Ninja
cmake --build build
ctest --test-dir build --output-on-failure
```

## Python binding

Install pybind11 in your chosen environment, then configure with `-DDANCERUDIMENTS_BUILD_PYTHON=ON`. The module exposes `sample(name, pip_count)`, the named functions, and `catalogue()`.

## TypeScript/WASM binding

Configure under Emscripten with `emcmake cmake -DDANCERUDIMENTS_BUILD_WASM=ON`, build `dancerudiments_wasm`, import its generated ES module, then call `bindNative(await createDanceRudiments())` from `bindings/typescript/index.ts`.

The dependency-free harness uses a browser-native mirror of the same discrete definitions so it can run without a toolchain. Its tests validate modulo wrapping and seam behaviour. Production TypeScript consumers should use the WASM binding so C++ remains the single runtime authority.

## Harness

Serve the repository root over HTTP and open `harness/index.html`. The harness provides play/pause, exact pip stepping, BPM, amplitude, trails, a numeric readout, and reduced-motion-aware manual operation.

```powershell
python -m http.server 4173
```

Then open `http://localhost:4173/harness/`.

## Motion safety

Apply an output to a bounded subject. DanceRudiments changes position only; it must not be used to add a repetitive full-frame tint, brightness, flash, or colour-grade effect. Under `prefers-reduced-motion`, do not autoplay the harness or production motion.

## Potential problems

### CMake stalls while detecting the C++ compiler ABI on this host

- **Symptom (28 September 2026):** CMake 3.30 with Ninja and the project-available MinGW GCC 16.2 compiler stopped after `Detecting CXX compiler ABI info` for more than 90 seconds. Compiler identification itself succeeded, and no diagnostic failure was emitted.
- **Cause:** unknown. Similar CMake reports show that this stage is a nested `try_compile`, but the available reports do not establish the cause on this Windows/Z-drive setup.
- **Working validation route:** compile the exact core and test sources directly with `g++ -std=c++17 -I include src/dance_rudiments.cpp tests/cpp/test_main.cpp -o build/dancerudiments_tests.exe`, then run the executable. Do not weaken or hard-code CMake's portable compiler detection merely to hide the local stall.
- **Verification:** the direct GCC build completed and all C++ assertions passed. This verifies the library sources with the available compiler; it does not claim that CMake configuration succeeded on this host.
- **Research:** [CMake discussion of a compiler-ABI detection hang](https://discourse.cmake.org/t/how-to-debug-detecting-c-compiler-abi-info-hanging-cygwin-on-github-actions/4580), accessed 28 September 2026.

### Node test isolation is denied

- **Symptom (28 September 2026):** `node --test "tests/typescript/*.test.js"` failed before assertions with `Error: spawn EPERM`.
- **Cause:** the restricted Windows host denied Node's child-process worker spawn.
- **Corrective action:** run `node --test --test-isolation=none "tests/typescript/*.test.js"`.
- **Verification:** both runtime suites passed in the single process. Keep tests free of shared mutable global state when adding more files.
