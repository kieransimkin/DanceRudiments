# Optional rig motion packages

Rig recordings are independent data packages. They are **not default rudiments,
dependencies of the base package, or site-wide assets**. A character page opts
into one exact rig profile and loads selected recordings. Leaving the page can
release its network requests, cached recordings and native instances.

The existing 1,731-pattern catalogue is unchanged. Importing the Python authoring
package or TypeScript module does not read any optional motion package. NumPy is
an optional **offline BVH import** dependency; Blender is only required for the
Blender import/retarget bridge. Neither is a browser runtime dependency.

These APIs are development source until a matching stable release is published.

## Contents and identity

An independent package directory contains:

```text
manifest.json
profile.json
clips/<clip-id>.json.gz
README.md
LICENSE.txt
THIRD_PARTY_NOTICES.md
SOURCES.json
```

The manifest has format `dancerudiments.motion-package`, schema version 1, and an
independently versioned package ID. It declares one exact rig profile, its
SHA-256, canonical semantic type URI, ordered channel names, licence/provenance,
and descriptors for individual clips. Every descriptor includes a SHA-256,
stored/decoded byte lengths, encoding, absolute `start_pip`, `sample_count`, and
optional finite metadata. Catalogue reads need only this manifest.

`profile.json` is canonical ASCII JSON without a trailing newline. Its file
SHA-256 equals the existing `RigProfile.fingerprint`; consumers hash the actual
bytes instead of reserializing floats differently in JavaScript. Clip files
contain the standard `dancerudiments.recording` JSON, optionally gzip compressed.
The shared profile is stored once per package rather than repeated in every
clip. There is no second binary recording schema or second live sampler.

Compatibility requires **all three** of the scene's type URI, profile hash and
ordered dimensions. A matching humanoid label or similar bone names is not an
adequate rig binding. Source BVH/FBX rigs use the separate
`syn://type/danceflow/motion/skeletal/source/...` namespace. They must not be
represented as Rigify control recordings until explicitly retargeted.

The manifest is limited to 8 MiB and 10,000 descriptors; each profile, stored clip
and decoded clip is limited to 64 MiB. Each clip also obeys the native maximum of
8,388,608 scalar values and signed 32-bit pip bounds. Relative paths cannot
traverse directories, contain URLs, collide case-insensitively, or replace root
notices. Importers reject duplicate JSON keys, non-finite samples, incomplete
quaternions and invalid discrete selectors.

## Explicit local installation and loading

```sh
dancerudiments-motion-pack install robot-1.0.0.zip --root ./motion-packs --sha256 <archive-sha256>
dancerudiments-motion-pack list --root ./motion-packs
dancerudiments-motion-pack inspect ./motion-packs/robot/1.0.0
```

From a source checkout, use `python tools/motion_package.py` in place of the
installed command. Installation verifies a local ZIP and atomically creates
`<root>/<id>/<version>`; it preserves existing versions. It neither downloads nor
executes code from a package. Archive traversal, symlinks, undeclared files,
duplicates and configured size violations fail before installation. Every
declared payload is hash-checked; full recording validation occurs on loading.

```python
from dancerudiments_authoring import MotionPackage, load_profile

scene_profile = load_profile("my-character.profile.json")
with MotionPackage("motion-packs/my_character/1.0.0",
                   expected_profile=scene_profile) as package:
    choices = package.catalogue()       # metadata only
    motion = package.load(choices[0]["id"])
    player = motion.player()            # existing native SampledRecording
    physical_channels = player.by_channel(player.start_pip)
    package.unload(motion.name)
```

Python caches at most one clip by default; `cache_size=0` disables caching.
`close()` drops the package's references. Objects deliberately retained by the
caller remain that caller's responsibility. `discover_motion_packages(root)`
only searches the directory the caller explicitly supplies; no global install
scan or default-library registration runs automatically.

`MotionPackageBuilder` creates packages from validated `RigMotion` objects.
`add_bvh_chunk()` accepts the explicitly validated vectorized offline import
result. `export_motion_package()` writes a deterministic independent ZIP, and
`resume=True` only resumes a package with identical identity, profile, licence
and provenance. Existing clip IDs cannot silently be overwritten.

```sh
dancerudiments-motion-pack create first.motion.json second.motion.json \
  --output ./motion-packs/my_character/1.0.0 --id my_character \
  --title "My character movements" --license CC0-1.0 \
  --license-url https://creativecommons.org/publicdomain/zero/1.0/ \
  --attribution "My own capture" --source-url https://example.org/my-capture \
  --timing-kind music
dancerudiments-motion-pack export ./motion-packs/my_character/1.0.0 my-character.zip
```

Use the real source's licence and timing status. These command arguments record
the caller's declarations; a converter cannot grant rights or establish beats.

## Browser pages and the beat clock

The package exposes `@kieransimkin/dance-rudiments/motion-packages` separately.
Dynamic import it inside the character page's lifecycle. The base module also
exports the APIs for existing consumers, with no asset-fetch side effects.

```js
const {createMotionPackageLoader, createRecordingWasmAdapter} =
  await import('@kieransimkin/dance-rudiments/motion-packages');

const response = await fetch(characterPage.recordingWasmUrl);
if (!response.ok) throw new Error(`WASM HTTP ${response.status}`);
const nativeModule = await WebAssembly.compile(await response.arrayBuffer());
const motions = createMotionPackageLoader({
  manifestUrl: characterPage.motionManifestUrl,
  packageId: characterPage.motionPackageId,
  expectedProfile: characterRig.target,
  nativeFactory: createRecordingWasmAdapter(nativeModule),
});

const catalogue = await motions.catalogue();
const clip = await motions.load(catalogue.clips[0].id);
// hostPip is an absolute integer from the existing 64-pip beat transport.
if (hostPip >= clip.startPip && hostPip < clip.startPip + clip.sampleCount) {
  characterRig.applyChannels(clip.profile, clip.sample(hostPip));
}
// On character/page teardown:
motions.dispose();
```

`characterRig.target` must come from the actual saved rig. Copying an untrusted
manifest's identity into this field does not establish compatibility. Applying
channels requires the host's rig evaluator; Rigify constraints and IK require a
capable evaluator or an explicitly baked/deformation-rig export. This library
does not silently add a mesh renderer to the XYZ visualizer.

The raw native recording accessor is exposed at the `./recording-wasm` package
subpath. Configure its hosted URL using the consuming app's build system. It is
compiled from the existing C++ recording implementation and hash-checked against
its sources when packaged. It is not fetched or instantiated on module import.

`createMotionPackageLoader()` is inert until called. `catalogue()` loads metadata;
`load(id)` fetches the profile once and only the selected clip. Handles provide
`sampleNormalized(pip)` for native values and `sample(pip)` for decoded physical
channels. In-flight requests are deduplicated, failed requests may be retried,
and each caller's abort only cancels that caller's wait. When no waiters remain,
the request can be cancelled. `unload(id)` invalidates that clip and releases its
native instance; `dispose()` releases everything owned by that loader.

The general browser loader retains requested clips until explicitly unloaded.
The complete [page example](../examples/motion-packages/page-motion.mjs) maintains
**one current chunk**, cancels obsolete requests on seeking, ignores late
results, subscribes to the host clock and cleans up on route exit. Repeated
frame ticks reuse a pending chunk request. Failures require explicit retry,
avoiding a request loop on every animation frame. The host keeps the beat clock;
the example creates no independent clock or sampler.

For a static server, serve `.json.gz` assets as raw `application/gzip`, **without
`Content-Encoding: gzip`**. Otherwise HTTP auto-decompression changes the stored
bytes before integrity validation. JSON may use `application/json`; WASM may
use `application/wasm`. Cross-origin hosting also needs ordinary CORS permission.
No signed-in fetches are required by the package format.

## Source timing, complete actions and chunks

Unknown music timing is represented explicitly as `timing_kind: "time-only"`.
Its 60 BPM clock is a coordinate in which one beat equals one second, sampled at
64 pips per second. This value is **not an estimated musical tempo**. The original
frame time, FPS, frame count, duration and source hash remain in provenance.

To match a dance to music, supply source BPM **and** beat-zero phase, or use the
existing `BeatMap`/`compile_capture` path with measured variable-tempo beat
anchors. Tempo alone does not determine phase. Target tempo changes then follow
the same absolute native pip clock. Foot-contact correction, transition design
and automatic audio beat detection are separate authoring work.

Long actions are split at contiguous pip boundaries into chunks with at most
500,000 values. All chunks of one action stay together in one package. Metadata
records `original_clip_id`, `chunk_index`, `chunk_count`, `total_sample_count`
and exact source-time spans. Counts of source actions and recording chunks are
reported separately; splitting does not create new distinct performances.

Compilation includes every integer pip inside the valid original time interval,
including negative prebeat pips when phase requires them. It never extends or
holds the endpoint. The sub-pip head/tail remainder is recorded. Recordings stay
non-looping; a caller must deliberately author any loop or transition.

## Importing optional source collections

Install offline acceleration only when needed:

```sh
python -m pip install '.[motion-import]'
python tools/import_motion_collection.py download --sources accad
python tools/import_motion_collection.py build --sources accad
```

The explicit source plan is [`motion-packages/sources.json`](../motion-packages/sources.json).
It records original public URLs, licence/attribution, byte/checksum constraints,
coordinate policies and output groups. Downloads go to the ignored project
cache. Converted packages go to ignored `motion-packs/`. Neither is included in
the base npm package, Python wheel/sdist or native default catalogue. A download
is an explicit command, never an installation hook.

The same commands accept `--sources lifelike_agility style100` for the dog
capture and 100STYLE locomotion collections. These are general motion sources;
100STYLE's 100 styles are not 100 dance genres. Source and converted data can
require several gigabytes, so select collections deliberately.

Space-XR publishes individual files with two coordinate conventions. Its
pinned acquisition recipe keeps their original bytes, performer names, titles,
aliases and hashes, then assembles two deterministic local source ZIPs:

```sh
python tools/acquire_space_xr.py --download
python tools/import_motion_collection.py build --sources space_xr_yup space_xr_zup
```

Omit `--download` to require already cached originals. The 17 distinct files
include nine dances/improvisations, seven Laban exercises and one walk/arm
movement; repeated listing links are not counted as additional performances.
The adapted data remains **CC BY-SA 4.0**, with the licence and attribution
inside each optional package. Source plan entries marked `local_archive` are
assembled by their acquisition recipe, not fetched from a fictitious ZIP URL.

The CMU dance recipe selects 89 dance-specific files from a pinned public mirror
of the documented cgspeed conversion. Exact deduplication yields 84 source
sequences, including modern dance, salsa, Charleston and other named dances:

```sh
python tools/acquire_cmu_dance.py --download
python tools/import_motion_collection.py build --sources cmu_dance
```

It retains the converter's calibration first frame and custom CMU terms,
including **no direct resale of the data**, even after conversion. These terms
are independent of the software licence. Per-file original URLs, Git blobs,
SHA-256 values, titles and timing evidence are preserved. The 30 salsa trials
use the explicitly evidenced 1/60-second correction described below; the other
files retain their declared frame intervals. Musical beats remain unverified.

The Quaternius robot recipe extracts all 14 Actions from the explicitly supplied
original CC0 archive, including Dance. Run it in the pinned Blender runtime:

```sh
blender --background --factory-startup --python tools/import_quaternius_robot.py -- \
  --archive /path/to/Animated-Robot-Oct-2018.zip \
  --work-dir .cache/motion-sources/robot-rebuild \
  --output-dir motion-packs/quaternius_robot/1.0.0 \
  --package-archive optional-motion-packs/quaternius_robot-1.0.0.zip
```

Use a new work/output directory. This recipe downloads nothing, preserves the
source rig and forms one exact profile for its Actions. The separately supplied
Blender demonstration retains the original skinned robot and bakes native
DanceRudiments samples; the base library contains no robot mesh or recordings.

Bulk import publishes a complete original action in one atomic manifest update.
A failed later chunk leaves the prior complete catalogue intact. `--resume`
requires the same package identity, profile, licence and source plan; interrupted
clip assets are reused only if regenerated bytes match exactly. A private build
checkpoint makes interruption before the first manifest recoverable and is
excluded from exported packages. A new version/output directory is required
when changing conversion settings or source identity.

The importer parses bounded BVH text, preserves the declared hierarchy and Euler
orders, converts local rotations to continuous unit quaternions, and resamples
offline with linear translation and shortest-path SLERP. It reports malformed
files and deduplicates exact source-byte duplicates. Source FPS is read from
each file, not guessed from the collection name.

An explicitly reviewed per-file `frame_time_override` can correct a known bad
header. `override_bvh_frame_time(clip, frame_time_seconds="1/60", evidence={...})`
requires nonempty source evidence and retains the original byte hash, declared
header interval/FPS/duration, pose arrays and profile. Effective timing then
drives compilation, with the correction recorded in every chunk. It does not
infer or replace musical tempo. The CMU conversion is one concrete use: its
converter rewrote headers uniformly, while some original trials ran at 60 fps.

BVH does not declare physical units. Scale 1 preserves original numerical units
and is labelled `source-units-unverified`; an explicit caller scale is recorded.
Axis conventions and fixed location bounds are part of the profile identity.
The importer supports both additive BVH positions and Blender's absolute-local
position convention. Sources with position channels equal to their rest offsets
must use the latter to avoid doubled bone lengths. This is an explicit source
policy, not a silent heuristic.

The opt-in `root_offset_policy: "motion"` moves only the initial ROOT rest
translation into recorded root motion. It retains original root offsets in each
clip's provenance and leaves child proportions unchanged. Identical bodies can
then share a profile even when captures started at different floor positions.
The default `"retain"` preserves exact original rest origins. Both policies are
checked against Blender/native world-space poses; this is not anatomical retargeting.

For FBX, glTF/GLB and BLEND Actions, use the
[Blender import and explicit retarget guide](blender-motion-import.md). Imported
source rigs remain separately typed, and the exact source rest hierarchy is
available to reconstruct a compatible carrier.

## Validation and ecosystem ownership

The package tests cover lazy reads, identity, tampering, bounded decompression,
atomic installation, path handling and native playback. TypeScript tests use
the actual checked-in C++ recording WASM, including cancellation and page/chunk
lifetime. Python-built gzip packages are consumed by that same browser API.
Pinned Blender tests compare source and reconstructed world transforms, exercise
multi-action/slot extraction and verify explicit Rigify FK mappings with native
skin deformation after saving/reopening.

DanceRudiments owns the reusable profile, package and recording APIs. Its existing
native playback engine is sufficient and remains shared. StemLab beat maps can
supply timing when music exists; the present motion-only sources do not warrant
running audio inference. DanceMoves/FrameRudiments can consume the page API after
a compatible shared release; this work does not claim those consumers were
released or deployed. Motion packages and program releases have separate version
identities, and each source's licence remains attached to its data.
