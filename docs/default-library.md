# Default movement library

The native catalogue contains **67 movements**: 15 original primitives, all
28 user-approved Initial 01 patterns, and 24 original Expansion 02 patterns.
The default API samples each directly. No pack registration, runtime Python,
network access, or JSON parsing is required by C++/WASM movement playback.

```python
import dancerudiments as d
assert len(d.catalogue()) == 67
print(d.sample('path_torus_knot', 48).as_tuple())
print(d.sample('rhythm_seven_four', -1).as_tuple())
```

```cpp
#include <dancerudiments/dance_rudiments.hpp>
auto p = dancerudiments::sample("lfo_twin_swell", pip_count);
```

```ts
import { bindNative, catalogue, sample } from '@kieransimkin/dance-rudiments';
import createNative from '@kieransimkin/dance-rudiments/wasm';
bindNative(await createNative());
console.log(catalogue.length); // 67
const p = sample('path_woven_3d', -1);
```

## Reproducible selection

`collections/defaults.json` is a schema-2 selection manifest with independent
SHA-256 locks, namespaces, headers and ordered names for each collection.
`tools/build_default_catalogue.py` validates all selections before generating
C++ includes, native registration and TypeScript metadata. It does not resample.
A changed digest requires a deliberate manifest update rather than being accepted
silently. The existing Initial 01 digest and all its tables are unchanged.

```sh
python tools/build_initial_collection.py --check
python tools/build_expansion_collection.py --check
python tools/build_default_catalogue.py --check
```

C++ consumers build from the checked-in generated tables; these commands do not
become runtime or CMake dependencies. Python 3.9+ with its standard library is
sufficient for the generators. Third-party packages are needed only to build
bindings or render browser screenshots, as before.

## Compatibility

`initial_pack()` and `expansion_pack()` expose source/provenance data for authoring,
and their `.to_native()` loaders remain idempotent for exact default copies.
The analogous generated C++ `make_library()` and TypeScript pack loaders also
retain 67 catalogue entries. A duplicate name in a supplied pack or an attempt
to change a default's samples, period, or description is rejected. Customise a
motion under a new name rather than silently overriding a default.

```python
from dancerudiments_authoring.collections import expansion_pack
pack = expansion_pack(['path_torus_knot'])
assert len(pack.to_native().catalogue()) == 67
```

The old 15-primitive harness and the editable Initial 01 audition page are
retained. For the complete default catalogue use the versioned release HTML.
The initial collection remains 28 patterns; the new collection remains 24.

## Timing and bounds

One pip is 1/64 of a quarter-note beat. Every sampler wraps positive and negative
signed 32-bit positions into its own period; no accumulated playback state is
used. Expansion 02 includes 4-, 7-, 8-, and 16-beat loops. Fifths, sevenths and
swung thirds remain rational during authoring. Sampling their continuous gesture
at an integer pip does not claim that every peak lies on the grid.

Original primitive sample tables are unchanged. The promotion also retains the
previously prepared overflow fix: grace-stroke offsets wrap before subtraction,
so `INT_MIN` remains defined. Source and JSON lookup values remain bounded.

## Licensing

New Expansion 02 definitions and data are original MIT material. Earlier source
terms remain: AKWF is CC0, Groove-derived data are CC BY 4.0, and the adapted D3
curves retain BSD-3-Clause attribution. The package-level licence expression
records the combination; it does not relicense the core or new originals.
Source notices remain in the generated headers, JSON, installed SDK and demos.
No new external dataset, preset bank or synthesis-engine code is imported.

## Release demo

The existing `demo-release.yml` workflow is preserved. It checks the generated
packs/registry, builds the exact release tag's native extension, and calls
`tools/release_demo.py`. The renderer refuses a stale native binary that omits
selected defaults. HTML, desktop/mobile screenshots, manifest, ZIP and checksums
are attached to published releases. Manual dispatch rebuilds compatible tags.
It does not publish packages, create a release, or configure hosting.

```sh
python -m pip install .
python tools/release_demo.py --version 0.1.3 --commit YOUR_COMMIT --output-dir dist/demo
python -m pip install playwright
python -m playwright install chromium
python tools/render_release_demo.py dist/demo/DanceRudiments-demo-v0.1.3.html
```

Use the version of the actual tag being built. `clang++` with `wasm-ld` is required
when generating the offline snapshot sampler. The renderer needs Chromium;
the resulting HTML needs no installation or network. It is a native-data
C++/WASM snapshot, distinct from the production Emscripten/Embind package.
Full workflow details and local-file policy notes are in `release-demo.md`.

The new pattern guide is `collections/expansion/README.md`.
