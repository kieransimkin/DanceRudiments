import json
import pathlib
import re
import sys
import tomllib

root = pathlib.Path(__file__).resolve().parents[1]
tag = sys.argv[1] if len(sys.argv) > 1 else ""
version = tag.removeprefix("v")
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
    raise SystemExit(f"Release tag must be vMAJOR.MINOR.PATCH; received {tag!r}")

package_version = json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]
python_version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
cmake_text = (root / "CMakeLists.txt").read_text(encoding="utf-8")
match = re.search(r"project\(DanceRudiments VERSION ([0-9]+\.[0-9]+\.[0-9]+)", cmake_text)
cmake_version = match.group(1) if match else None

versions = {"release tag": version, "package.json": package_version,
            "pyproject.toml": python_version, "CMakeLists.txt": cmake_version}
if len(set(versions.values())) != 1:
    raise SystemExit("Version mismatch: " + ", ".join(f"{key}={value}" for key, value in versions.items()))
print(f"Release version {version} is consistent across all package manifests.")
