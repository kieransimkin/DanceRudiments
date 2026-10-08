# DanceRudiments for C# / .NET

[![DanceRudiments logo](https://raw.githubusercontent.com/kieransimkin/DanceRudiments/v0.2.2/docs/branding/logo.png)](https://kieransimkin.co.uk/danceflow/)

[DanceFlow](https://kieransimkin.co.uk/danceflow/) · [Kieran Simkin](https://kieransimkin.co.uk/)

By **[Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/)**, part of DanceFlow.

A C# interface to the **original C++ rhythmic movement library**, not a managed
reimplementation. Enumerate the native catalogue, sample XYZ offsets at 64 pips
per beat, fill a `Span<Offset3>` in one native call, or own a private pattern bank.

## Install

After a release containing this binding has been published:

```sh
dotnet add package DanceRudiments
```

The package includes the managed `net8.0` assembly and native x64/ARM64 libraries
for Windows, Linux and macOS. It targets .NET 8+ applications;
CI executes the contract suite on .NET 8 and .NET 10. Prefer a supported .NET
runtime. Native availability is not the same as support for every .NET host:
.NET Framework, Unity/Mono, IL2CPP, mobile, browser-WASM and NativeAOT are not
claimed as supported by this first binding. Linux packages target glibc, not musl.

```csharp
using DanceRudiments;

Console.WriteLine($"C++ version: {Rudiments.NativeVersion}");
Console.WriteLine($"{Rudiments.Catalogue.Count} movements");
var amen = Rudiments.Catalogue.Single(p => p.Name == "beat_amen_four_bar_bounce");
int pip = Rudiments.PipAtTime(1.25, bpm: 140, periodPips: amen.PeriodPips);
Offset3 position = Rudiments.Sample(amen.Name, pip);
Console.WriteLine($"{position.X}, {position.Y}, {position.Z}");
Offset3[] loop = Rudiments.SampleMany(amen.Name, 0, amen.PeriodPips);
```

No compiler or Python runtime is needed to **consume** a matching released NuGet
package. Its native assets are selected automatically by NuGet/.NET. For an
explicit target, publish with `dotnet publish -r win-x64 --self-contained false`
(or another included runtime identifier). A source checkout needs CMake, a C++17
compiler and the .NET SDK; see [the full guide](https://github.com/kieransimkin/DanceRudiments/blob/main/docs/csharp.md).

## Custom data

```csharp
using var bank = PatternLibrary.Load("my-patterns.compiled.json");
var custom = bank.Sample("my_pattern", -1);
```

Use the existing Python `dancerudiments-compile` command to author/compile JSON;
loading and **all movement evaluation at runtime** are C++. `PatternDefinition`
also accepts an explicit table. Samples and metadata are copied; `using` disposes
the native bank. SafeHandle protects calls against disposal races and provides a
finalizer fallback. An exact default reload is idempotent; changed defaults under
the same name are rejected. No override of the global catalogue is permitted.

## Timing and errors

A pip is **1/64 of a quarter note**, not a millisecond or a MIDI tick. Negative
pips wrap; each pattern has its own period. `PipAtTime` floors and wraps absolute
fixed-tempo time, avoiding frame-by-frame drift. For tempo changes, integrate a
musical timeline rather than multiplying all past time by the latest BPM.

Unknown names or invalid native input become `ArgumentException`; range failures
become `ArgumentOutOfRangeException`. Missing or wrong-architecture native files
produce the usual loader exceptions. Calling a disposed bank throws
`ObjectDisposedException`. The API changes position only; respect reduced-motion
preferences in the consuming application and keep movement within bounded subjects.

## Included material

The package contains its README, full C# guide, a runnable C# example, existing
visualizer screenshots, author credits, original third-party notices, and per-RID
native hashes/source revisions. Symbols in `.snupkg` cover the managed assembly;
they are not native debugging symbols.

[Download the self-contained visualizer](https://github.com/kieransimkin/DanceRudiments/raw/refs/heads/main/harness/index.html)
for audible beat/movement comparisons. It is separate from the .NET binding and
its large HTML snapshot is deliberately not duplicated into the NuGet package.

[Source and releases](https://github.com/kieransimkin/DanceRudiments) ·
[Music / My Songs](https://kieransimkin.co.uk/my-songs/)

An offline copy of the guide is included as `docs/csharp.md` inside the NuGet package.
