#!/usr/bin/env python3
"""Prepare and verify DanceRudiments semantic-version releases.

Typical local flow:

    python tools/release_version.py prepare 0.2.0
    git diff
    git commit -am "Prepare v0.2.0 release"
    git push
    # wait for main CI to pass
    python tools/release_version.py tag 0.2.0 --push

Pushing the tag is the CD trigger. GitHub Actions calls ``verify-tag`` before
publishing any package or creating the GitHub Release.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(?:v)?([0-9]+)\.([0-9]+)\.([0-9]+)$")


def normalize_version(value: str) -> tuple[str, str]:
    match = SEMVER.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Version must be MAJOR.MINOR.PATCH (optionally prefixed with v); received {value!r}")
    version = ".".join(match.groups())
    return version, "v" + version


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_versions(root: Path = ROOT) -> dict[str, Optional[str]]:
    package = _read_json(root / "package.json")
    lock = _read_json(root / "package-lock.json")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    csproj = ET.parse(root / "bindings/csharp/DanceRudiments/DanceRudiments.csproj")

    py_match = re.search(r"(?ms)^\[project\]\s.*?^version\s*=\s*\"([^\"]+)\"", pyproject)
    cmake_match = re.search(r"project\(DanceRudiments\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)", cmake)
    return {
        "package.json": package.get("version"),
        "package-lock.json": lock.get("version"),
        "package-lock root package": lock.get("packages", {}).get("", {}).get("version"),
        "pyproject.toml": py_match.group(1) if py_match else None,
        "CMakeLists.txt": cmake_match.group(1) if cmake_match else None,
        "C# NuGet": csproj.findtext("./PropertyGroup/Version"),
    }


def verify_version(expected: str, root: Path = ROOT) -> str:
    version, tag = normalize_version(expected)
    versions = manifest_versions(root)
    bad = {name: value for name, value in versions.items() if value != version}
    if bad:
        details = ", ".join(f"{name}={value!r}" for name, value in versions.items())
        raise ValueError(f"Version mismatch for {tag}: {details}")
    return version


def _replace_once(text: str, pattern: str, replacement: str, name: str) -> str:
    changed, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"Could not find exactly one version field in {name}")
    return changed


def set_version(value: str, root: Path = ROOT) -> str:
    version, _ = normalize_version(value)

    package_path = root / "package.json"
    package = _read_json(package_path)
    package["version"] = version
    package_path.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lock_path = root / "package-lock.json"
    lock = _read_json(lock_path)
    lock["version"] = version
    root_package = lock.setdefault("packages", {}).setdefault("", {})
    root_package["version"] = version
    lock_path.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    pyproject_path = root / "pyproject.toml"
    text = pyproject_path.read_text(encoding="utf-8")
    project_match = re.search(r"(?ms)^\[project\]\s.*?(?=^\[|\Z)", text)
    if not project_match:
        raise ValueError("Could not find [project] in pyproject.toml")
    section = project_match.group(0)
    replaced = _replace_once(section, r'^version\s*=\s*"[^"]+"', f'version = "{version}"', "pyproject.toml")
    text = text[:project_match.start()] + replaced + text[project_match.end():]
    pyproject_path.write_text(text, encoding="utf-8")

    cmake_path = root / "CMakeLists.txt"
    text = cmake_path.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        r"(project\(DanceRudiments\s+VERSION\s+)[0-9]+\.[0-9]+\.[0-9]+",
        rf"\g<1>{version}",
        "CMakeLists.txt",
    )
    cmake_path.write_text(text, encoding="utf-8")

    csproj_path = root / "bindings/csharp/DanceRudiments/DanceRudiments.csproj"
    text = csproj_path.read_text(encoding="utf-8")
    text = _replace_once(text, r"<Version>[^<]+</Version>", f"<Version>{version}</Version>", "DanceRudiments.csproj")
    csproj_path.write_text(text, encoding="utf-8")

    verify_version(version, root)
    return version


def _git(root: Path, *args: str, capture: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True,
        text=True, capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


def create_tag(value: str, root: Path = ROOT, *, push: bool = False, remote: str = "origin") -> str:
    version, tag = normalize_version(value)
    verify_version(version, root)
    if _git(root, "status", "--porcelain"):
        raise ValueError("Working tree is not clean; commit and push the version bump before tagging")
    branch = _git(root, "branch", "--show-current")
    if branch != "main":
        raise ValueError(f"Release tags must be created from main; current branch is {branch!r}")
    existing = subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=root,
                              text=True, capture_output=True)
    if existing.returncode == 0:
        raise ValueError(f"Tag {tag} already exists")
    _git(root, "tag", "-a", tag, "-m", f"DanceRudiments {tag}", capture=False)
    if push:
        _git(root, "push", remote, tag, capture=False)
    return tag


def current_version(root: Path = ROOT) -> str:
    versions = manifest_versions(root)
    values = set(versions.values())
    if len(values) != 1 or None in values:
        details = ", ".join(f"{name}={value!r}" for name, value in versions.items())
        raise ValueError("Package manifests disagree: " + details)
    return next(iter(values))  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="Set every package manifest to VERSION")
    prepare.add_argument("version")

    verify = sub.add_parser("verify-tag", help="Verify a release tag matches every package manifest")
    verify.add_argument("tag")

    tag = sub.add_parser("tag", help="Create an annotated release tag after the version bump is committed")
    tag.add_argument("version")
    tag.add_argument("--push", action="store_true", help="Push the new tag to the remote")
    tag.add_argument("--remote", default="origin")

    sub.add_parser("current", help="Print the common manifest version")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare":
            version = set_version(args.version)
            print(f"Prepared DanceRudiments v{version} in all package manifests.")
            print("Review the diff, commit it to main, push it, wait for CI, then run:")
            print(f"  python tools/release_version.py tag {version} --push")
        elif args.command == "verify-tag":
            version = verify_version(args.tag)
            print(f"Release tag v{version} matches every package manifest.")
        elif args.command == "tag":
            tag = create_tag(args.version, push=args.push, remote=args.remote)
            action = "created and pushed" if args.push else "created"
            print(f"{tag} {action}. Tag-triggered CI/CD now owns publication.")
        elif args.command == "current":
            print(current_version())
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"release_version: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
