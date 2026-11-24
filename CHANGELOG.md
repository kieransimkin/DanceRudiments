# Changelog

## 0.4.11

- Share an in-flight character preparation when selecting a source and immediately
  pressing Audition. Repeated requests no longer cancel the same scene load;
  source changes and explicit unload preserve the existing disposal contract.
- Add regression checks for shared loads, superseded completions, unload and retry.
- Pin the authoring matrix to Ubuntu 24.04 so its required Python 3.9 check can
  run, retaining exact Linux/Python 3.13 regeneration and Windows coverage.

## 0.4.8 - 2026-11-02

- Isolate Windows pytest process, fixture and cache data in a probed per-run LocalAppData directory, with cleanup and a focused default test command.
- Normalize Git text to LF while retaining CRLF only for Windows command scripts, so content hashes remain stable across platforms.

## 0.2.4 - 2026-10-08

- Add explicit agent capability, improvement, validation and upstream PR guidance to the README and contributor instructions.

## 0.2.3 - 2026-10-08

- Preserve the canonical My Songs author link in the branding guide and validate it in source checks as well as real archives. Fixes the 0.2.2 Python/native packaging guard failure; already published 0.2.2 assets remain immutable.


## 0.2.2 - 2026-10-08

- Add an original tool-specific vector logo and PNG companion in the shared DanceFlow visual style.
- Clarify package descriptions from reviewed documentation and KeywordMoves literal-source evidence, without claims of measured search demand.
- Link package descriptions and READMEs to Kieran Simkin’s website and retain branding files in installable packages.


## 0.2.1 - 2026-10-08

- Verify delayed NuGet indexing with bounded, authenticated publication evidence rather than treating an immediate index miss as publication failure.
- Preserve the existing motion catalogue and bindings unchanged.
- Keep all package manifests aligned with the fresh release version.
