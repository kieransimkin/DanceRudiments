# DanceRudiments tag-driven release automation

This update makes a pushed semantic-version tag (`vMAJOR.MINOR.PATCH`) the CD trigger.

## Normal release flow

Prepare every manifest at once:

```powershell
python tools/release_version.py prepare 0.2.0
git diff
git add CMakeLists.txt pyproject.toml package.json package-lock.json bindings/csharp/DanceRudiments/DanceRudiments.csproj
git commit -m "Prepare v0.2.0 release"
git push
```

Wait for the ordinary `main` CI workflows to pass, then create and push the release tag:

```powershell
python tools/release_version.py tag 0.2.0 --push
```

The script refuses to tag a dirty tree, a branch other than `main`, mismatched manifests, or an existing tag.

## What the tag triggers

The tag starts four release paths directly:

- `release-tag.yml` verifies the exact tag and creates the GitHub Release with generated notes.
- `release.yml` builds/publishes PyPI and npm packages, builds C++ archives, and optionally publishes Conan.
- `csharp.yml` builds six native runtimes, creates/tests the NuGet package, and publishes it to NuGet.org and GitHub Packages.
- `demo-release.yml` renders and attaches the self-contained visualizers and screenshots.

The package workflows are tag-triggered directly rather than relying on a `release` event created by another workflow. This avoids GitHub's protection against recursively triggering workflows with `GITHUB_TOKEN`.

## Version fields managed by the script

- `CMakeLists.txt`
- `pyproject.toml`
- `package.json`
- `package-lock.json` (both root version locations)
- `bindings/csharp/DanceRudiments/DanceRudiments.csproj`

CI calls:

```sh
python tools/release_version.py verify-tag "$GITHUB_REF_NAME"
```

before registry publication.

## First C# hosted-run fix included

The first merged C# workflow successfully built all six native runtimes but failed while checking the packed NuGet archive because extensionless LICENSE `PackagePath` values were treated as directories. This update packages the root license into `licenses/`, the third-party notices into `licenses/`, and the D3 license into `licenses/d3-ease/`, and updates the archive verifier accordingly.

## Registry prerequisites

The existing one-time registry configuration still applies: PyPI and npm environments, optional Conan remote, and the NuGet.org Trusted Publisher + `nuget` GitHub environment / `NUGET_USER` described in `docs/csharp.md`.
