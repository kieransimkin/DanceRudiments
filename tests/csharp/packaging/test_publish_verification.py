"""Regression checks for delayed NuGet.org indexing."""
import inspect
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("csharp_package", ROOT / "tools/csharp_package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PublishVerificationTests(unittest.TestCase):
    def test_default_indexing_window_is_about_fifteen_minutes(self):
        signature = inspect.signature(package.verify_published)
        self.assertEqual(signature.parameters["attempts"].default, 60)
        self.assertEqual(signature.parameters["delay_seconds"].default, 15)

    def test_invalid_retry_configuration_is_rejected_before_package_access(self):
        with self.assertRaises(ValueError):
            package.verify_published(Path("missing.nupkg"), "nuget.org", attempts=0)
        with self.assertRaises(ValueError):
            package.verify_published(Path("missing.nupkg"), "nuget.org", delay_seconds=-1)

    def test_manual_verification_accepts_an_explicit_release_version(self):
        with self.assertRaises(FileNotFoundError):
            package.verify_published(Path("missing.nupkg"), "nuget.org", "0.2.0", attempts=1, delay_seconds=0)
        with self.assertRaises(ValueError):
            package.verify_published(Path("missing.nupkg"), "nuget.org", "v0.2", attempts=1, delay_seconds=0)


if __name__ == "__main__":
    unittest.main()
