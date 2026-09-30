# DanceRudiments tag-release automation v3 validation

Target source: `1da252f4905e9d1eb3ade56389f9c1cea0b0a664` (`main`).

This rebuild corrects the malformed v1/v2 handoff patch. The previous patch contained repeated per-file diffs whose hunk coordinates were not based on the actual files, causing `git apply` failures at line 1.

Validation performed:

- Current changed-file contexts were read directly from GitHub `main` at `1da252f4905e9d1eb3ade56389f9c1cea0b0a664`.
- Unified-diff hunk counts were recalculated and parsed successfully by `git apply --numstat`.
- A reconstructed baseline containing the exact current contexts for all modified hunks passed `git apply --check --verbose`.
- `tools/release_version.py` unit tests: 3 passed.
- `.github/workflows/release-tag.yml` parses as YAML (PyYAML treats the YAML 1.1 key `on` as boolean when printing, which is a parser-version quirk; GitHub Actions uses the workflow syntax normally).
- The patch also fixes the currently observed C# NuGet pack failure by preserving extensionless `LICENSE` filenames under package directories and updating the package verifier.

Not performed locally:

- Hosted GitHub Actions execution of the new tag workflows.
- Registry publication to PyPI, npm, NuGet.org, GitHub Packages or Conan.

The authoritative end-to-end validation remains the first push after applying this patch, followed by a release tag only after all branch CI is green.
