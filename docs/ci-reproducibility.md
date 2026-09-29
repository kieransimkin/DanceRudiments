# Cross-platform regeneration checks

## Failure corrected

Run `36634678019` (`Curve and event infrastructure`, a push of
`caae90f1a75d892ee299164681746328c332fb83`) failed on Ubuntu/Python 3.9 and on
Windows/Python 3.9 and 3.13. Linux/Python 3.13 and the real Emscripten/WASM job
passed. Both Windows jobs successfully built and installed their native Python
wheels; their failures concerned regeneration and exact authoring comparisons,
not native-table playback.

The old checks required fresh floating-point computations to reproduce every
stored decimal and diagnostic exactly on all hosts. The logs show last-decimal
sample differences and smaller diagnostic differences. Python math routines and
platform C math libraries need not round every intermediate result identically.
A changed norm diagnostic also changes a pack's JSON hash, even when its stored
movement samples agree. The logs do not identify every individual math operation
responsible for each mismatch.

There was a second bug: multi-command PowerShell steps continued after failed
native commands. A successful final command then made the step appear green.
The authoring/native matrix now explicitly uses Bash, whose GitHub runner wrapper
uses `-e -o pipefail`, for all its run steps. The matrix still exercises both
operating systems and both supported test interpreters.

## Exact artifacts, portable recipes

`DANCERUDIMENTS_REGENERATION_CHECK` selects the verification policy:

| Policy | Where used | What is compared |
| --- | --- | --- |
| `exact` (default) | Ubuntu/Python 3.13 CI, release rendering, normal checks | The original exact generation/output checks remain in force. |
| `portable` | Windows/Python 3.9 and 3.13, Ubuntu/Python 3.9 CI | Fresh recipes and recomputed values are compared numerically, followed by exact checks of the unchanged canonical artifacts. |

The portability comparison permits at most `2e-11` absolute difference between
two finite floating-point fields. There is no relative tolerance. All integers,
booleans, text, object keys, list order, lengths, rational beat strings and hash
strings still match exactly. Non-finite values always fail. The tolerance is
applied only to authoring/rebuild comparisons, not C++/WASM playback or native
sample tests. It is 20 units of the 12-decimal authoring grid; it is not a claim
of bit-identical cross-platform recipe evaluation.

For score-based collections a portable `--check`:

1. Evaluates the definitions and compares the resulting recipe with the saved
   score, including structure, event times, names and provenance.
2. Loads the saved compiled pack and validates its **exact SHA-256** against
   `collections/defaults.json`.
3. Independently recompiles the saved score on the current host and compares
   every field with that locked pack. No digest field is ignored.
4. Only after those checks pass, uses the saved score and pack to verify the
   generated C++ headers, manifests, embedded preview data and other outputs
   through their existing exact checks.

Dancefloor's directly baked recipes receive the equivalent numerical check
against their locked pack, including exact recipe hashes. The default registry
checker is unchanged. A tiny edit to a committed pack is still rejected by its
hash lock even when the edit is smaller than the numerical tolerance.

This separates the question "does this host calculate the same motion within a
small numeric tolerance?" from "are the shipped artifacts still exactly the
approved ones?" It does not regenerate or replace approved movement samples to
make a particular host pass. A meaningful recipe change, stale hash, changed
name, reordered pattern, altered rational event time or non-finite result still
fails verification. Ubuntu/Python 3.13 also continues to require exact recipe
regeneration, including differences smaller than the portable tolerance.

## Local use

Normal checks remain strict:

```sh
python tools/build_initial_collection.py --check
python tools/build_default_catalogue.py --check
```

To check existing artifacts on a different host, explicitly select portability
mode. In PowerShell:

```powershell
$env:DANCERUDIMENTS_REGENERATION_CHECK = "portable"
python tools/build_initial_collection.py --check
if ($LASTEXITCODE -ne 0) { throw "Initial collection verification failed" }
python tools/build_expansion_collection.py --check
if ($LASTEXITCODE -ne 0) { throw "Expansion verification failed" }
python tools/build_atlas_collection.py --check
if ($LASTEXITCODE -ne 0) { throw "Atlas verification failed" }
python tools/build_continuum_collection.py --check
if ($LASTEXITCODE -ne 0) { throw "Continuum verification failed" }
python tools/build_club_collection.py --check
if ($LASTEXITCODE -ne 0) { throw "Club verification failed" }
python tools/build_dancefloor_collection.py --check
if ($LASTEXITCODE -ne 0) { throw "Dancefloor verification failed" }
python tools/build_default_catalogue.py --check
if ($LASTEXITCODE -ne 0) { throw "Default registration verification failed" }
Remove-Item Env:DANCERUDIMENTS_REGENERATION_CHECK
```

For an already installed updated package, the same environment variable selects
portable comparisons in `python -m unittest discover -s tests/python -v`.
The workflow sets it automatically; users do not need to change GitHub settings.

**Write mode is unchanged:** running a generator without `--check` computes fresh
outputs, even when the environment variable is `portable`. Canonical artifact
updates should be produced and reviewed on the exact-check platform. Do not
regenerate hashes merely to conceal a mismatch.

## Scope

This change modifies only authoring verification, its regression tests and the
matrix shell policy. No movement definition, event score, generated movement
table, C++ runtime, public sampling API, version, or publishing workflow changes.
It does not claim that the hosted Windows/Python 3.9 matrix has been rerun before
the patch is committed and pushed. The next GitHub run is that validation.

## Primary references

- Affected run: https://github.com/kieransimkin/DanceRudiments/actions/runs/36634678019
- GitHub shell/error behavior: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsshell
- Python mathematical functions and implementation notes: https://docs.python.org/3.13/library/math.html
