# DanceRudiments

DanceRudiments is a small C++17 library of deterministic rhythmic position functions. One integer pip is `1/64` of a beat. The built-in rudiments use 64-, 128-, or 256-pip loops; custom compiled patterns can use any supported integral pip period. Every sampler wraps positive or negative input into its own loop before sampling.

Outputs are dimensionless offsets, normally in `[-1, 1]`. The caller chooses pixels, CSS units, metres, or another scale. There is deliberately no time interpolation in the public API: renderers advance with integer pips and get one exact sample per pip.

## Curve and event authoring

The optional **Python authoring tools** compile LFOs, segmented curves, sampled
waveforms, seeded repeating randomness and rational-beat event/gesture scores into
JSON packs or C++17 headers. **All movement playback remains C++**, including
Python and TypeScript/WASM consumers. The fifteen built-ins remain unchanged;
custom packs use independent `PatternLibrary` objects rather than global overrides.

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

GitHub automatically adds “Source code” ZIP and tar.gz links to every release; those are repository snapshots, not precompiled packages. Python wheels belong on PyPI and the TypeScript/WASM package belongs on npm, so GitHub's manually attached assets are intentionally C++-only.

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

## Continuous integration and releases

`.github/workflows/ci.yml` builds and tests the C++ core on Linux, Windows, and macOS; builds and imports the Python package; compiles/tests the TypeScript and browser runtime; and creates a Conan package on every push to `main` and every pull request.

Publishing is deliberately tied to a GitHub release with a `vMAJOR.MINOR.PATCH` tag. Before creating the release, update the matching version in `CMakeLists.txt`, `pyproject.toml`, and `package.json`. `.github/workflows/release.yml` rejects mismatches before it publishes anything, then:

- builds platform Python wheels and a source distribution and publishes them to PyPI using OIDC Trusted Publishing;
- builds the TypeScript wrapper and C++ WebAssembly module and publishes `@kieransimkin/dance-rudiments` to npm using npm Trusted Publishing and provenance;
- builds installable C++ archives for Linux, Windows, and macOS and attaches them, along with Python distributions, to the GitHub release; and
- builds a Conan package and uploads it only when a separate Conan remote has been configured. ConanCenter packages are submitted through `conan-center-index`; they are not directly uploaded by this repository.

One-time registry configuration is required before the first release:

1. On PyPI, create a pending Trusted Publisher for owner `kieransimkin`, repository `DanceRudiments`, workflow `release.yml`, environment `pypi`, and project name `dancerudiments`.
2. On npm, configure the package's GitHub Actions Trusted Publisher for `kieransimkin/DanceRudiments`, workflow `release.yml`, environment `npm`, with direct publishing allowed. Because npm Trusted Publishers are configured from an existing package's settings, the first scoped-package registration may require a granular `NPM_TOKEN` secret in the `npm` environment. Remove that bootstrap token after Trusted Publishing is configured.
3. Create GitHub environments named `pypi`, `npm`, and `conan`; add required reviewers if desired.
4. For an optional private or organisational Conan repository, set environment variable `CONAN_REMOTE_URL` and secrets `CONAN_LOGIN_USERNAME` and `CONAN_PASSWORD` in the `conan` environment. If they are absent, the recipe is built and verified but not uploaded.

The publishing jobs use short-lived OIDC identity for PyPI and npm and do not require long-lived PyPI or npm tokens. See the official [PyPI Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/) and [npm Trusted Publishing](https://docs.npmjs.com/trusted-publishers/) documentation.

## Motion safety

Apply an output to a bounded subject. DanceRudiments changes position only; it must not be used to add a repetitive full-frame tint, brightness, flash, or colour-grade effect. Under `prefers-reduced-motion`, do not autoplay the harness or production motion.

## Potential problems

### GitHub release assets are ambiguous or incomplete

- **Symptom (28 September 2026):** the first C++ ZIPs were named only by platform, opened into a `stage/` directory, contained no licence or instructions, and installed exported targets without the `DanceRudimentsConfig.cmake` file needed by the documented `find_package` workflow. The release page also did not explain where Python and npm packages lived.
- **Cause:** the release job archived its temporary install directory verbatim and treated all language build artifacts as potential GitHub attachments instead of giving each package ecosystem one canonical destination.
- **Corrective action:** publish Python on PyPI and TypeScript/WASM on npm; reserve manually attached GitHub assets for C++. Name each archive `DanceRudiments-cpp-<version>-<platform>-static.zip`, use a versioned root directory, include the MIT licence, C++ usage guide, platform manifest, complete CMake config/version files, and publish `SHA256SUMS.txt`.
- **Verification:** ordinary CI builds a separate consumer against the installed CMake package on Linux, Windows, and macOS. Release QA must inspect archive names and contents, verify the checksum file, and confirm the README's package table links to PyPI, npm, and GitHub Releases.

### An older Windows `tar.exe` cannot inspect the release ZIP

- **Symptom (28 September 2026):** release QA invoked `tar -tf` but the command resolved to WinAVR 2010's `tar.exe`, which reported `Cannot open: I/O error` for the absolute Windows path even though the downloaded ZIP and checksum file were present.
- **Cause supported by current evidence:** command resolution selected the old WinAVR utility rather than a current ZIP-capable archive reader. The error does not establish damage to the published archive.
- **Corrective action:** use PowerShell's `Expand-Archive -LiteralPath <zip> -DestinationPath <directory>` for Windows release inspection, then compare `Get-FileHash -Algorithm SHA256` with `SHA256SUMS.txt`.
- **Verification:** the `v0.1.3` Windows archive expanded successfully, exposed its versioned root, README, licence, package manifest, header, static library, and complete CMake configuration, and its calculated SHA-256 matched the published checksum.
- **Research:** [Microsoft Learn: Expand-Archive](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.archive/expand-archive), accessed 28 September 2026.

### Installed-package smoke test assumes the wrong motion coordinate

- **Symptom (28 September 2026):** the first installed-package consumer compiled and linked on Linux, Windows, and macOS, but its runtime assertion failed on every platform.
- **Cause:** the test incorrectly expected `circle(64)` to return `(1, 0)`. The 64-pip motion wraps that input to pip 0, whose documented phase starts at approximately `(0, -1)`.
- **Corrective action:** test the public modulo contract by comparing `circle(64)` with `circle(0)` using a small floating-point tolerance, rather than duplicating an assumed trajectory coordinate.
- **Verification:** require the separate installed-package consumer to pass on all three CI platforms.

### GitHub release attachment job has no Git checkout

- **Symptom (28 September 2026):** all `v0.1.2` package builds and both registry publications succeeded, but `attach-github-release` failed with `failed to run git: fatal: not a git repository (or any of the parent directories): .git`.
- **Cause:** that job intentionally downloaded build artifacts without checking out the repository, while `gh release upload` was invoked without `--repo` and therefore tried to infer its repository from local Git metadata.
- **Corrective action:** pass `--repo "${{ github.repository }}"` explicitly. A checkout is unnecessary because the upload only needs downloaded artifacts, the release tag, and the workflow token.
- **Verification:** upload the completed run's artifacts to `v0.1.2`, confirm them on the release page, and retain the explicit repository argument for future releases.
- **Research:** [GitHub CLI `gh release upload` manual](https://cli.github.com/manual/gh_release_upload), accessed 28 September 2026.

### MSVC core and Python import libraries have the same filename

- **Symptom (28 September 2026):** after excluding 32-bit wheels, the `v0.1.1` Windows wheel still failed at `cp39-win_amd64` with `LINK : fatal error LNK1114: cannot overwrite the original file '.../Release/dancerudiments.lib'; error code 5`.
- **Cause:** on Windows' case-insensitive filesystem, the static core's default `DanceRudiments.lib` filename collided with the Python extension's `dancerudiments.lib` import library. Both targets were valid, but MSVC placed their archive outputs in the same configuration directory.
- **Corrective action:** retain the public CMake target name `DanceRudiments::DanceRudiments`, but give its Windows archive the distinct physical filename `DanceRudimentsCore.lib`. Add a Windows Python-package job to ordinary CI so MSVC builds and imports the wheel before any release.
- **Verification:** CI must build and import the Python wheel on `windows-latest`; the release workflow must then complete every `win_amd64` wheel and import test.
- **Research:** CMake's [`OUTPUT_NAME`](https://cmake.org/cmake/help/latest/prop_tgt/OUTPUT_NAME.html) and [`add_library`](https://cmake.org/cmake/help/latest/command/add_library.html) documentation, accessed 28 September 2026, confirms that output filenames may be changed independently of logical target names and that Windows shared/module targets have associated import libraries.

### cibuildwheel attempts unsupported 32-bit Windows wheels

- **Symptom (28 September 2026):** the `v0.1.0` release workflow failed in `python-wheels (windows-latest)` while building `cp39-win32`; cibuildwheel reported that its isolated `python -m build` command exited with code 1. The Linux and macOS wheel jobs were unaffected, and the npm package published successfully.
- **Cause:** the broad `cp39-*` through `cp314-*` build selectors also include 32-bit Windows identifiers, while DanceRudiments currently targets 64-bit package architectures.
- **Corrective action:** add `*-win32` to `[tool.cibuildwheel].skip`, retaining the existing musllinux exclusion. Do not advertise or emit a 32-bit wheel until that architecture is deliberately supported and tested.
- **Verification:** the patch-release workflow must complete the Windows `win_amd64` matrix and its import tests before PyPI publication.
- **Research:** [cibuildwheel build/skip options](https://cibuildwheel.pypa.io/en/stable/options/), accessed 28 September 2026; the official examples explicitly use `*-win32` to skip 32-bit Windows builds.

### npm cache access is denied on Windows

- **Symptom (28 September 2026):** `npm pack --dry-run` failed with `EPERM: operation not permitted, open 'C:\Users\Kieran\AppData\Local\npm-cache\_cacache\tmp\…'` after the TypeScript tests had passed.
- **Cause:** the shared user cache could not create its temporary file. npm's Windows issue tracker records this class of `EPERM` failure, including cases involving cache files and real-time scanning; the exact process holding this particular file was not identified.
- **Corrective action:** keep the shared cache intact and run package validation with a repository-local cache: `npm pack --dry-run --cache .npm-cache`. The cache directory is ignored by Git.
- **Verification:** the dry-run package completed with the local cache. This workaround changes only npm's disposable cache location and does not change the package contents.
- **Research:** [npm CLI Windows EPERM report](https://github.com/npm/cli/issues/8072) and [npm CLI cache-isolation guidance](https://github.com/npm/cli/issues/1785), accessed 28 September 2026.

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

### An isolated Python build selects unavailable NMake on Windows

- **Symptom (28 September 2026):** the first scikit-build-core attempt failed during configuration with `Running 'nmake' '-?' failed with: no such file or directory` and `CMAKE_CXX_COMPILER not set`.
- **Cause supported by current evidence:** CMake selected the `NMake Makefiles` generator although this host provides Ninja and MinGW GCC, not NMake/MSVC. The first `uv run` invocation also attempted an unnecessary editable install of the current project before running the requested build command.
- **Corrective action:** set `CMAKE_GENERATOR=Ninja` for this local toolchain and use `uv run --no-project --with build python -m build`, leaving CI runners free to select their native supported compiler environment.
- **Verification:** the isolated build then produced `dancerudiments-0.1.0.tar.gz` and a CPython 3.13 Windows wheel, with the C++ extension compiled and installed successfully.
- **Research:** CMake documents `CMAKE_GENERATOR` as the supported generator-selection mechanism, while scikit-build-core documents Ninja selection and its `ninja.make-fallback` behaviour. Sources: [CMake generator environment variable](https://cmake.org/cmake/help/latest/envvar/CMAKE_GENERATOR.html) and [scikit-build-core configuration](https://scikit-build-core.readthedocs.io/en/stable/configuration/), accessed 28 September 2026.

### A MinGW-built Python wheel cannot locate its C++ runtime DLLs

- **Symptom (28 September 2026):** the first locally built Windows wheel installed successfully but `import dancerudiments` failed with `ImportError: DLL load failed while importing dancerudiments: The specified module could not be found.`
- **Cause supported by current evidence:** the MinGW-built extension dynamically referenced GCC runtime libraries that were available in the compiler directory but not in the isolated Python environment. This local toolchain differs from cibuildwheel's normal Windows MSVC environment.
- **Corrective action:** inspect the built `.pyd` with the matching toolchain's `objdump -p`. It identified `libwinpthread-1.dll` as the remaining non-system dependency after the standard C++ runtimes were made static. Only for MinGW, link with `-static-libgcc -static-libstdc++` and install the compiler's matching `libwinpthread-1.dll` beside the extension; do not apply that bundling to MSVC or other platforms.
- **Verification:** rebuild the wheel and import it in a fresh isolated environment; require the catalogue and modulo-sampling smoke assertions to pass. The release workflow independently runs cibuildwheel's installed-wheel test on every platform.
- **Research:** GCC documents `-static-libstdc++` as linking the C++ runtime statically without making the whole module static, and the pybind11 issue tracker records the same generic Windows import symptom when a compiler runtime DLL is missing. Sources: [GCC link options](https://gcc.gnu.org/onlinedocs/gcc/Link-Options.html) and [pybind11 missing-runtime discussion](https://github.com/pybind/pybind11/issues/2771), accessed 28 September 2026.

### Conan detects an unavailable future Visual Studio generator

- **Symptom (28 September 2026):** local `conan profile detect` selected `msvc` version 195 and generated `Visual Studio 18 2026`, while CMake 3.30 on this host only exposes Visual Studio generators through 2022. The recipe consequently failed before compiling.
- **Cause:** the host's compiler discovery evidence is inconsistent: no usable `cl.exe` is on the command path, but Conan detected a newer MSVC installation than the installed CMake understands. This is a local toolchain/profile mismatch, not a recipe failure established across supported runners.
- **Corrective action:** do not commit the guessed local profile or hard-code a generator in the portable recipe. CI detects and builds the recipe on `ubuntu-latest` with its supported native profile; Windows consumers should use a profile naming an installed compiler and generator combination.
- **Verification:** require the GitHub Actions Conan job to complete `conan create` from the committed recipe. Until that run passes, local recipe syntax/export is verified but the Conan binary build remains pending.
- **Research:** Conan's profile detector warns that detected profiles are guesses and not guaranteed stable; CMake documents that the selected generator must match an available build environment. See [CMake's user interaction guide](https://cmake.org/cmake/help/latest/guide/user-interaction/index.html), accessed 28 September 2026.
