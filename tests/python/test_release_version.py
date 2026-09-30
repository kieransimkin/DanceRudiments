import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("release_version", ROOT / "tools/release_version.py")
assert SPEC and SPEC.loader
release_version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_version)


class ReleaseVersionTests(unittest.TestCase):
    def make_tree(self, root: Path, version: str = "0.1.3") -> None:
        (root / "bindings/csharp/DanceRudiments").mkdir(parents=True)
        (root / "package.json").write_text(json.dumps({"name":"x","version":version}, indent=2)+"\n")
        (root / "package-lock.json").write_text(json.dumps({"name":"x","version":version,"packages":{"":{"name":"x","version":version}}}, indent=2)+"\n")
        (root / "pyproject.toml").write_text(f'[build-system]\nrequires=[]\n\n[project]\nname="x"\nversion = "{version}"\n\n[tool.demo]\nversion="unchanged"\n')
        (root / "CMakeLists.txt").write_text(f'project(DanceRudiments VERSION {version}\n  DESCRIPTION "demo"\n  LANGUAGES CXX)\n')
        (root / "bindings/csharp/DanceRudiments/DanceRudiments.csproj").write_text(f'<Project><PropertyGroup><Version>{version}</Version></PropertyGroup></Project>\n')

    def test_prepare_updates_every_manifest_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); self.make_tree(root)
            self.assertEqual(release_version.set_version("v2.3.4", root), "2.3.4")
            self.assertEqual(set(release_version.manifest_versions(root).values()), {"2.3.4"})
            self.assertIn('version="unchanged"', (root/"pyproject.toml").read_text())

    def test_verify_rejects_one_stale_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); self.make_tree(root)
            data=json.loads((root/"package-lock.json").read_text()); data["version"]="9.9.9"
            (root/"package-lock.json").write_text(json.dumps(data))
            with self.assertRaises(ValueError): release_version.verify_version("0.1.3", root)

    def test_semver_is_strict(self):
        for bad in ("1.2", "1.2.3.4", "release-1.2.3", "1.2.3-beta"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                release_version.normalize_version(bad)
        self.assertEqual(release_version.normalize_version("v10.20.30"), ("10.20.30", "v10.20.30"))


if __name__ == "__main__": unittest.main()
