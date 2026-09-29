# Versioned release demos

The release renderer exports the real compiled default catalogue. It does not
change package versions, create releases, or configure GitHub Pages.

The **Release demo** workflow runs whenever a release is published. It checks out
the release tag, verifies the CMake/Python/npm versions, builds and installs that
checkout's native Python extension, and calls the native `catalogue()` and
`sample()` interfaces. There is no handwritten list of default movements: the current
catalogue produces 323 cards, and future defaults are picked up in the same way.

The builder embeds every native sample, source attribution, interface code, CSS
and a newly compiled C++ WebAssembly lookup sampler in one offline HTML file.
Python is used only during generation; live movement positions come from C++/WASM.
The snapshot sampler is distinct from the production Emscripten/Embind package.

Chromium then renders desktop/mobile screenshots, verifies every position against
the exported snapshot (including negative/extreme pips), checks playback and
filters, and records the results. The workflow attaches:

- `DanceRudiments-demo-vX.Y.Z.html` and desktop/mobile PNG screenshots;
- a version/commit/count/checksum JSON manifest;
- a ZIP and SHA-256 checksums.

The upload job re-downloads the attachments and verifies their bytes. Only that
job receives write permission. Manual re-runs replace matching demo assets using
`--clobber`; an interrupted replacement may leave an old demo asset absent, so
use the retained workflow artifact to recover or rerun it. Package assets with
other names are not modified. Existing package-release workflows are unchanged.

## Activate

Apply this patch to a checkout that does not already contain these demo tools,
commit and push it, then publish a new release whose tag contains the tools.
GitHub will run **Release demo** for that tag. The workflow must be present in
the tagged source. Its manual `release_tag` input can rebuild a compatible existing
tag; it cannot retrofit old tags that lack the builder files.

A release created using a repository's `GITHUB_TOKEN` may not trigger another
workflow in the usual way. Such release automation should invoke the demo build
as part of the same workflow, use an appropriately authorised app/PAT, or use
manual workflow dispatch. Ordinary user-published releases trigger `published`.

## Local build

```sh
python -m pip install .
python tools/release_demo.py --version X.Y.Z --commit YOUR_COMMIT --output-dir dist/demo
python -m pip install playwright
python -m playwright install chromium
python tools/render_release_demo.py dist/demo/DanceRudiments-demo-vX.Y.Z.html
```

The HTML generator needs the native library plus `clang++` and `wasm-ld`; the
renderer additionally needs Playwright/Chromium. Generated HTML needs none of
those tools, nor network access. Choose a version matching the installed package.
The page displays its version, commit, count and source notices.

This is a read-only native snapshot, not an editable authoring pack. Pack and score
export controls are intentionally hidden. Comparison, personal review notes and
local audio/BPM synchronisation remain available. 3D paths use an oblique projection
and a separate Z curve. Motion starts paused and respects reduced-motion settings.

By default the browser checks `file://` loading. An explicit `--in-memory` option
supports environments that forbid file navigation; the manifest records the
choice so it is not misreported as a file-navigation test.

## Default collections and stale-build protection

The default library now contains 323 motions: 15 original primitives, 256 Atlas presets, 28 approved
Initial 01 patterns, and 24 original Expansion 02 additions. Each published
release runs the three generation checks before building its native module.
The renderer verifies every required name from `collections/defaults.json` is
present; an older installed binary cannot silently produce a smaller demo.
Existing review/compare controls and each pattern's source notices are retained.

References:
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow
- https://cli.github.com/manual/gh_release_upload
- https://cli.github.com/manual/gh_release_download

## Larger catalogues

The demo now offers collection filtering as well as family, search and review
filters. All catalogue entries remain in the page. Only cards near the viewport
are animated; offscreen canvas backing stores are released and restored on
scrolling. Musical phase always comes from the shared clock, so reappearing
cards show their correct current position. No reduced-fidelity movement sampler
or JavaScript fallback is substituted. The builder validates Atlas regeneration
before the release native build. Existing release-asset upload behaviour is unchanged.

## Dancefloor 06 additions

The workflow also renders `DanceRudiments-demo-dancefloor-vX.Y.Z.html`: 68 rhythm studies
with 16 mappings each, four-slot comparison, synthesised audio and desktop/mobile captures.
The general native snapshot permits up to 4,096 patterns and 4,194,304 samples for the
expanded catalogue. Untrusted authoring/JSON pack limits remain 1,024 patterns and
1,048,576 samples per pack. Each pack remains independent.

### Large-catalogue snapshot storage (schema 2)

The full catalogue demo now stores its movement tables **once**, inside WASM,
not again as decimal JSON triples. Snapshot metadata retains a SHA-256 digest of
native-exported little-endian float64 XYZ values for every pattern. Signed zero
is normalised for these digests, matching the previous numeric-equality test.
The renderer reads all WASM samples in bounded batches and compares those digests,
as well as testing negative and extreme pip wrapping. It still validates schema-1
snapshots that contain decimal tables. This is an internal, read-only demo format;
the authoring and compiled-pack schemas are unchanged.

Base64 decoding uses bounded chunks rather than creating a character array for
the entire embedded module. On the 1,731-pattern preview this reduces the full
HTML from approximately 74 MiB to 35 MiB without changing movement data. The
focused sixteen-mapping page retains its inspection tables and separate exact
scalar tests. Neither page uses a JavaScript motion fallback.
