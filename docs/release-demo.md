# Versioned release demos

This standalone change adds release-demo generation only. It does not register
optional movement packs, promote patterns into the default library, change
package versions, create releases, or configure GitHub Pages.

The **Release demo** workflow runs whenever a release is published. It checks out
the release tag, verifies the CMake/Python/npm versions, builds and installs that
checkout's native Python extension, and calls the native `catalogue()` and
`sample()` interfaces. There is no handwritten list of default movements: a tag
with 15 defaults produces 15 cards, a tag with 43 produces 43, and future defaults
are picked up in the same way.

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

## Scope of the recovered patch

The prior combined default-promotion/release-demo files were not retained in the
current working environment. This patch independently restores release rendering;
it does **not** claim to recover or apply the separate 43-default promotion change.
The supplied renderer preview uses the intact earlier 28-pattern collection and
is labelled as a preview fixture, not as the deployed default catalogue.

References:
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow
- https://cli.github.com/manual/gh_release_upload
- https://cli.github.com/manual/gh_release_download
