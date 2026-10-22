# Optional motion source plans

Source-plan tooling by [Kieran Simkin — My Songs](https://kieransimkin.co.uk/my-songs/).
The motion data retains the source-specific authorship and terms below.

`sources.json` is reviewed metadata for explicit public source downloads and
offline imports. It does not load or install any motion data automatically.
The code and base packages contain no converted clips from these collections.

Run `python tools/import_motion_collection.py download --sources <id>` and then
`build --sources <id>` from the repository. Select only sources appropriate to
your intended use and retain their attribution/licence and modification notices.
The ignored `motion-packs/` directory contains independently versioned packages;
each manifest selects an exact skeleton and each recording loads separately.

| Source ID / recipe | Content | Data terms |
| --- | --- | --- |
| `accad` | Human actions, locomotion, gestures and individual samples | CC BY 3.0 |
| `style100` | 810 recordings in 100 stylized locomotion groups | CC BY 4.0 |
| `lifelike_agility` | 33 quadruped dog captures | CC BY 4.0 |
| `space_xr_yup`, `space_xr_zup` | 17 distinct dance, improvisation and movement recordings | CC BY-SA 4.0 |
| `cmu_dance` | 89 dance files, 84 unique sequences after exact deduplication | CMU custom terms; no direct data resale |
| `tools/import_quaternius_robot.py` | 14 robot Actions, including Dance, from an explicitly supplied original ZIP | CC0 |

For Space-XR, run `python tools/acquire_space_xr.py --download` before the generic
`build` command. Its pinned `space-xr-sources.json` distinguishes original
Y-up files from Z-up reexports and preserves performer/title provenance. The
acquisition command without `--download` is entirely local. The robot recipe
runs in Blender and accepts a local original archive; see the import guide.

For the CMU dance subset, run `python tools/acquire_cmu_dance.py --download`, then
`python tools/import_motion_collection.py build --sources cmu_dance`. The source
manifest pins the public mirror commit, individual Git blobs and SHA-256 values,
retains the original cgspeed conversion README and calibration frames, and
documents the explicit 60-fps correction for the 30 salsa recordings. Original
BVH bytes remain unchanged. The custom terms permit free redistribution of
these packages and forbid selling the motion data itself, including conversions.

All these imports use explicit time-only coordinates until source musical tempo
and beat phase are supplied. Counts refer to original recordings, not chunks;
each complete recording stays within a single compatible optional package.

See [the complete optional-package guide](../docs/motion-packages.md),
[the Blender extraction/retarget guide](../docs/blender-motion-import.md), and
[the motion-source research](../docs/motion-sources.md).

Licence texts in `licenses/` are the original Creative Commons public legal
texts from its own repository. They are included in converted optional packs.
They do not relicense the program or unrelated datasets.
