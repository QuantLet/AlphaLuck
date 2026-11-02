import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from organiser_hourly import Sweep

class ThresholdTimingTest(unittest.TestCase):
    def setup_sweep(self, snapshots, q=10., policy='nearest', fills=()):
        s=Sweep.__new__(Sweep)
        s.threshold_policy=policy; s.align_funding=True
        s.org={('a','x'):np.array(snapshots,dtype=float)}
        s.fill_times={('a','x'):np.array(fills,dtype=float)}
        s.rates={'x':.05}
        # Positive unit means funding received, negative means funding paid.
        s.m=SimpleNamespace(hours=np.array([10.,20.,30.]),unit={'x':np.array([-.2,-.3,-.4])})
        return s

    def test_prior_never_uses_closer_future_observation(self):
        s=self.setup_sweep([[10,10,90],[21,10,95]],policy='prior')
        time,L=s.threshold('a','x',10,20)
        self.assertEqual(time,10)
        self.assertAlmostEqual(L,90+3/9.5)

    def test_future_threshold_removes_funding_after_formation(self):
        s=self.setup_sweep([[30,10,90]])
        self.assertAlmostEqual(s.threshold('a','x',10,20)[1],90-4/9.5)

    def test_short_threshold_moves_in_opposite_direction(self):
        s=self.setup_sweep([[10,-10,110]])
        self.assertAlmostEqual(s.threshold('a','x',-10,20)[1],110+(-3)/(-10.5))

    def test_no_prior_snapshot_remains_missing(self):
        s=self.setup_sweep([[21,10,90]],policy='prior')
        self.assertIsNone(s.threshold('a','x',10,20))

    def test_unchanged_quantity_does_not_override_intervening_fill(self):
        s=self.setup_sweep([[10,10,90]],fills=[15])
        self.assertIsNone(s.threshold('a','x',10,20))

    def test_funding_at_snapshot_is_not_counted_twice(self):
        s=self.setup_sweep([[20,10,90]])
        self.assertEqual(s.threshold('a','x',10,20),(20,90))

if __name__=='__main__':unittest.main()
