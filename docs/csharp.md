# C# / .NET binding, native packaging and releases

By **[Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/)** · DanceFlow.

## Design and API

`DanceRudiments` is a NuGet package with an AnyCPU `net8.0` wrapper and a platform
C++ shared library, `dancerudiments_native`. The wrapper calls the versioned C ABI
in `include/dancerudiments/c_api.h` using cdecl P/Invoke and explicit UTF-8 strings.
No C++ exception, `std::string`, `std::vector` or allocator crosses the ABI.

The C ABI compiles the existing core source files unchanged. Every live XYZ value
comes from that core. C# performs validation, JSON parsing, memory management and
optional time-to-pip conversion, not a second set of movement equations.

| API | Meaning |
| --- | --- |
| `Rudiments.Catalogue` | Immutable copy of the actual native catalogue; not a handwritten name list |
| `Rudiments.Sample(name, pip)` | One double-precision `Offset3` |
| `Rudiments.SampleMany(name, start, count, step)` | A newly allocated array, sampled in one native call |
| `Rudiments.SampleInto(name, start, destination, step)` | Fills an existing `Span<Offset3>` without allocating a result array |
| `Rudiments.PipAtTime(seconds, bpm, periodPips, beatZeroSeconds)` | Floor fixed-tempo time, then wrap before narrowing to `int` |
| `new PatternDefinition(name, description, samples)` | Copies and validates an authored table |
| `new PatternLibrary(definitions)` | An independent owned C++ bank, also exposing defaults |
| `PatternLibrary.Load(path)` / `FromJson(json)` | Load schema-v1 `dancerudiments.compiled-pack` data |
| `PatternLibrary.Dispose()` | Releases the native bank; use a `using` declaration |

`Offset3` has immutable double fields `X`, `Y`, `Z`. `RudimentInfo` includes
`Name`, `Description`, `PeriodPips`, `PeriodBeats` and `Dimensions`. The first
binding exposes named movements through `Sample`; it does not manufacture 1,731
individual C# methods. Later registered defaults are discovered automatically.

Supply signed 32-bit pips. The native batch API evaluates `start + i * step` in
64-bit arithmetic before wrapping, so batches may cross either int32 boundary
without overflow. Zero and negative steps are supported. Limit a single batch
to 1,048,576 results. Compiled packs retain the existing limits: 1..1024 patterns,
1..65,535 samples per pattern and 1,048,576 total samples. Empty explicit native
banks are allowed. JSON loading rejects duplicate keys, incorrect format/version,
non-finite/out-of-bounds values, invalid lengths and missing required provenance
fields. The source digest is syntax-checked, not independently re-derived from
absent original score material. Do not treat a digest alone as proof of trust.

Default metadata is copied once using a thread-safe lazy initializer. Custom
metadata is copied during construction and remains usable after disposal. The
native bank is immutable: concurrent reads are supported. SafeHandle holds a
native reference for each P/Invoke, so racing disposal either lets an already
started call finish or raises `ObjectDisposedException`. Do not use the raw C ABI
with invalid handles, double-free a handle, or free a handle while C clients are
reading it; the C# wrapper manages those requirements.

## Use a released package

```sh
dotnet new console -n MotionDemo -f net8.0
cd MotionDemo
dotnet add package DanceRudiments
```

```csharp
using DanceRudiments;

var info = Rudiments.Catalogue.Single(p => p.Name == "beat_amen_four_bar_bounce");
int pip = Rudiments.PipAtTime(1.25, 140, info.PeriodPips);
Offset3 v = Rudiments.Sample(info.Name, pip);
Console.WriteLine($"Amen at {pip}: {v}");
Console.WriteLine($"Wrap backwards: {Rudiments.Sample(info.Name, -1)}");

// Reuse this array on subsequent frames/exports if needed.
var positions = new Offset3[info.PeriodPips];
Rudiments.SampleInto(info.Name, 0, positions);
```

The package is not live merely because its source is merged. Until the first
publishing workflow succeeds, use the checkout build or download the CI-produced
`csharp-nuget` artifact and restore from a local NuGet source. Check `Catalogue`
rather than hard-coding a count: registry packages can lag the checkout.

The first version targets .NET 8+ desktop/server CLR applications. CI tests .NET 8
and .NET 10. It does not claim .NET Framework 4.x, Unity/Mono, IL2CPP, mobile,
Blazor WebAssembly, NativeAOT, trimmed builds or single-file-native extraction
support. Those need dedicated builds/tests. A normal multi-file, framework-
dependent `dotnet publish -r <rid> --self-contained false` is covered.

## Native platforms

| RID | Native file | Build/test baseline |
| --- | --- | --- |
| `linux-x64` | `libdancerudiments_native.so` | Ubuntu 22.04, glibc 2.35, x64 |
| `linux-arm64` | `libdancerudiments_native.so` | Ubuntu 22.04, glibc 2.35, ARM64 |
| `win-x64` | `dancerudiments_native.dll` | Windows Server 2022, x64 |
| `win-arm64` | `dancerudiments_native.dll` | Windows 11 ARM64 |
| `osx-x64` | `libdancerudiments_native.dylib` | macOS 15 Intel, deployment target 14 |
| `osx-arm64` | `libdancerudiments_native.dylib` | macOS 15 Apple Silicon, deployment target 14 |

Use an OS supported by your chosen .NET runtime as well. Linux builds require
the normal system C/C++ runtime libraries, not Alpine/musl. Windows bridge builds
use MSVC's static CRT to avoid an extra redistributable DLL requirement. This
setting is scoped to the bridge and does not change ordinary Python/C++ builds.
macOS uses the system C++ runtime. ARM and Intel are separate native builds, not
emulated binaries renamed to a different RID. Hosted runner availability and
platform ABI requirements are recorded in `bindings/csharp/platforms.json`.

For package consumers, **do not copy DLLs manually or set a loader environment
variable**. NuGet places native files under `runtimes/<rid>/native/`; the .NET
loader uses the package's runtime assets. The CI consumer jobs verify this path.
If loading fails, inspect the application architecture, its `.deps.json`, the
included RID, OS baseline and system dependencies. Do not rename an x64 binary
to arm64 or use the visualizer's WASM module as a desktop native library.

## Build the checkout

Install a C++17 compiler, CMake 3.20+ and the .NET SDK. Building the contract suite
requires both .NET 8 and .NET 10 SDK/runtime installations. No Python is involved
in .NET movement playback; Python 3.13 is used by CI's packaging utilities.

```sh
cmake -S . -B build-csharp -DCMAKE_BUILD_TYPE=Release -DDANCERUDIMENTS_BUILD_C_ABI=ON
cmake --build build-csharp --config Release --parallel 2
ctest --test-dir build-csharp -C Release --output-on-failure
dotnet build bindings/csharp/DanceRudiments/DanceRudiments.csproj -c Release
```

For MSVC select `-A x64` or `-A ARM64` at configure time. MinGW is deliberately
rejected for this packaged bridge because its auxiliary DLL packaging is not
configured. This does not remove the existing library's other MinGW routes.

For **source development only**, point the managed process at the absolute
bridge filename before first use. Do not change the variable after first use:

```powershell
# Windows / PowerShell, from the repository root:
$env:DANCERUDIMENTS_NATIVE_LIBRARY = (Resolve-Path .\build-csharp\csharp-native\dancerudiments_native.dll).Path
dotnet run --project examples/bindings/csharp/Quickstart.csproj -c Release
dotnet run --project tests/csharp/DanceRudiments.Tests.csproj -c Release -f net8.0
dotnet run --project tests/csharp/DanceRudiments.Tests.csproj -c Release -f net10.0
```

```sh
# Linux; on macOS substitute libdancerudiments_native.dylib.
export DANCERUDIMENTS_NATIVE_LIBRARY="$PWD/build-csharp/csharp-native/libdancerudiments_native.so"
dotnet run --project examples/bindings/csharp/Quickstart.csproj -c Release
```

The example inside the NuGet archive should be run with
`-p:UsePackedBinding=true -p:BindingPackageVersion=<installed-version>`; its default
project reference is for the repository checkout. Alternatively copy `Program.cs`
into your own application with a normal `PackageReference`.

The example also accepts a path to a compiled custom pack as its application
argument. The authoring command is unchanged:

```sh
python tools/compile_patterns.py compile examples/bindings/pulse.score.json --json generated/tutorial.json
dotnet run --project examples/bindings/csharp/Quickstart.csproj -c Release -- generated/tutorial.json
```

## CI and packaging

`.github/workflows/csharp.yml` runs on pushes to main, pull requests, manually
triggered validation and published GitHub releases. Manual validation never
publishes a package. Every release job checks out that event's release tag.

The workflow validates versions, builds the bridge on **six native runners**,
runs the original C++ tests plus C ABI parity tests, and runs the C# contract suite
on .NET 8 and .NET 10. An independent exporter linked to the original static core
produces per-pattern little-endian-double hashes for C# sample verification.

Each native job stages a checked architecture and a SHA-256/source-revision
manifest. One pack job gathers all six, rejects missing/mixed/stale binaries and
runs `dotnet pack`. The NuGet file contains the managed DLL/XML documentation,
six native runtimes, per-RID manifests, README, author credits, source licences,
usage guide, C# example and screenshots. There are no NuGet dependencies beyond
the chosen .NET framework itself. A separate `.snupkg` contains managed symbols.

A second six-runner matrix restores **that exact locally built package**, not a
project reference or existing public package. Package-source mapping permits Microsoft
framework packs from NuGet.org but forces `DanceRudiments` to the local artifact
feed, using a fresh cache. It reruns managed tests with normal
native probing and publishes/runs a RID-specific example outside the checkout.
Publishing waits for **all** of those jobs. Tests use executable contract suites
via `dotnet run`, with a nonzero exit status on failure; they do not require xUnit
or a separate test-runner NuGet dependency.

CI artifacts are `csharp-native-<rid>` and `csharp-nuget`. Ordinary commits do not
upload to registries. Do not label a locally fabricated or single-platform nupkg
as the complete release: the pack step refuses missing platforms.

## One-time NuGet.org setup

1. Sign in to the NuGet.org account that will own **DanceRudiments**. Confirm that
   this ID is available or owned by that account; this change does not reserve it.
2. Create a trusted publishing policy: repository owner **kieransimkin**, repository
   **DanceRudiments**, workflow filename **csharp.yml**, environment **nuget**.
   Scope the policy to `DanceRudiments`, allowing creation of a new package as
   well as uploading subsequent versions when the registry offers those scopes.
3. In GitHub create/use environment **nuget**, and set `NUGET_USER` to the NuGet.org
   **profile username**, not an email address. A repository/environment variable
   or secret is accepted. Set environment reviewers according to your policy.

The workflow uses `NuGet/login@v1` to exchange GitHub OIDC identity for a short-
lived publishing key. No long-lived NuGet API key is embedded or required. Missing
setup is an explicit failed publishing job, not a green silently skipped upload.
The NuGet.org account, policy and package ownership must still be configured by
the maintainer. See the official trusted-publisher reference below.

## Releases and package destinations

Before a new release, update the **same version** in `CMakeLists.txt`,
`pyproject.toml`, `package.json`, its lockfile, and
`bindings/csharp/DanceRudiments/DanceRudiments.csproj`. The release validator now
checks the .NET version too. Publish a GitHub release with its matching
`vMAJOR.MINOR.PATCH` tag; pushing a tag alone does not trigger registry uploads.

After successful native, managed and installed-package tests:

- **NuGet.org** receives `DanceRudiments.<version>.nupkg` plus managed symbols. The
  workflow downloads the indexed package and compares payload members, allowing
  NuGet.org's added repository signature rather than assuming ZIP bytes remain
  identical. Indexing can take time; an upload is not called verified prematurely.
- **GitHub Packages** receives the same nupkg under
  `https://nuget.pkg.github.com/kieransimkin/index.json`. `GITHUB_TOKEN` with
  `packages: write` authenticates; `RepositoryUrl` links the package to this repo.
  GitHub Packages may initially make a new package private, and consumers need
  feed authentication even for public NuGet packages there. Configure visibility
  and access in package settings. NuGet.org remains the default public install.
- **GitHub Releases** receives the nupkg, snupkg and `SHA256SUMS-csharp.txt` as
  attachments. They do not replace the existing Python/npm/C++ release routes.

A GitHub Packages permission failure is independent of NuGet.org availability.
Restore verification uses a temporary, isolated credentials file on the runner;
no credentials or recovery codes are committed. Azure Artifacts and MyGet are
not configured because no private feed was requested.

## Implementation references

- Native assets in .NET packages: https://learn.microsoft.com/en-us/nuget/create-packages/native-files-in-net-packages
- .NET native interop and SafeHandle: https://learn.microsoft.com/en-us/dotnet/standard/native-interop/best-practices
- NuGet trusted publishing: https://learn.microsoft.com/en-us/nuget/nuget-org/trusted-publishing
- GitHub NuGet registry: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-nuget-registry
- .NET support lifecycle: https://dotnet.microsoft.com/en-us/platform/support/policy
- Hosted runner labels: https://github.com/actions/runner-images
