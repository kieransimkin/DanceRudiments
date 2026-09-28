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
