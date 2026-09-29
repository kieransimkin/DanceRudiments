"""Real pybind11 integration; DANCERUDIMENTS_REQUIRE_NATIVE=1 makes absence fail CI."""
import os
from pathlib import Path
import unittest
from dancerudiments_authoring import compile_pack, read_json

try:
    import dancerudiments as native
except ImportError:
    native = None
if os.environ.get('DANCERUDIMENTS_REQUIRE_NATIVE') == '1' and native is None:
    raise ImportError('Native extension is required for this test run')


@unittest.skipIf(native is None, 'Native extension not built')
class NativeTests(unittest.TestCase):
    def setUp(self):
        self.pack=compile_pack(read_json(Path(__file__).resolve().parents[2]/'examples/patterns/starter.json'))

    def test_every_sample_and_arbitrary_seek(self):
        bank=self.pack.to_native()
        for p in self.pack.patterns:
            direct=p.to_native()
            positions=list(range(-2*p.period_pips,2*p.period_pips))+[2147483647,-2147483648]
            # Descending seek order detects accidental stateful playback.
            for pip in reversed(positions):
                expected=p.samples[pip%p.period_pips]
                self.assertEqual(bank.sample(p.name,pip).as_tuple(),expected)
                self.assertEqual(direct.sample(pip).as_tuple(),expected)

    def test_existing_api_is_unchanged(self):
        bank=self.pack.to_native()
        self.assertEqual(len(native.catalogue()),15)
        self.assertEqual(len(bank.catalogue()),19)
        self.assertEqual(bank.sample('circle',64).as_tuple(),native.circle(0).as_tuple())
        with self.assertRaises(ValueError): native.sample('wobble_xy',0)

    def test_validation_and_ownership(self):
        samples=[[0,0,0],[1,0,0]]
        p=native.SampledPattern('custom','',samples)
        samples[0][0]=.5
        self.assertEqual(p.sample(0).x,0)
        for row in [[float('nan'),0,0], [2,0,0]]:
            with self.assertRaises(ValueError): native.SampledPattern('bad','',[row])
        with self.assertRaises(ValueError): native.PatternLibrary([p,p])
        with self.assertRaises(ValueError): native.PatternLibrary([native.SampledPattern('circle','',[[0,0,0]])])
        with self.assertRaises(TypeError): p.sample(.5)
        with self.assertRaises(TypeError): p.sample(2**40)

    def test_lifetime(self):
        bank=self.pack.to_native()
        del self.pack
        self.assertEqual(bank.sample('triplet_steps',0).as_tuple(),(.8,-.25,0))

if __name__ == '__main__': unittest.main()
