# Build and release troubleshooting

By [Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/).

Historical notes below describe the stated versions and host environments, not the current state of every build.

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
