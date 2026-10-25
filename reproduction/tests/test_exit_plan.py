"""Exit-plan adherence: episodes, crossings, classes, the plan-follow P&L and outputs."""
from pathlib import Path
import json
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import exit_plan_adherence as xp

MIN = 60_000


def fills(rows):
    out = []
    for i, (t, sz, px) in enumerate(rows):
        out.append({'tag': 'S15__c1__m', 'coin': 'xyz:A', 'time': t, 'tid': i, 'oid': i,
                    'px': px, 'sz': abs(sz), 'signed_sz': sz, 'fee': 0.001 * abs(sz) * px})
    return pd.DataFrame(out)


class EpisodeTest(unittest.TestCase):
    def setUp(self):
        # long 10, add 5, reverse to short 5 in one fill, cover, then open long at the end
        f = fills([(1 * MIN, 10, 100.0), (2 * MIN, 5, 101.0), (3 * MIN, -20, 102.0),
                   (4 * MIN, 5, 99.0), (5 * MIN, 2, 98.0)])
        self.e, self.legs = xp.build_episodes(f, 0, 10 * MIN, frozenset({3}), {'xyz:A': 97.0})

    def test_reversal_is_split(self):
        e = self.e
        self.assertEqual(len(e), 3)
        self.assertEqual(e.side.tolist(), [1, -1, 1])
        self.assertEqual(e.closed.tolist(), [True, True, False])
        self.assertEqual(e.t_close.iloc[0], e.t_open.iloc[1])
        split = self.legs[self.legs.tid == 2]
        self.assertEqual(sorted(split.sz.tolist()), [-15.0, -5.0])
        self.assertAlmostEqual(split.fee.sum(), 0.001 * 20 * 102.0, places=12)

    def test_gross_and_marking(self):
        e = self.e
        self.assertAlmostEqual(e.gross.iloc[0], -1000 - 505 + 15 * 102, places=9)
        self.assertAlmostEqual(e.gross.iloc[1], 5 * 102 - 5 * 99, places=9)
        self.assertAlmostEqual(e.gross.iloc[2], 2 * (97 - 98), places=9)
        self.assertTrue(e.liq_close.iloc[1])
        self.assertFalse(e.liq_close.iloc[0])


class CrossTest(unittest.TestCase):
    times = np.array([10, 20, 30, 40, 50], dtype='int64')

    def test_observed_backfill_entry(self):
        prices = np.array([94.0, 99.0, 101.0, 96.0, 108.0])
        u = np.array([15, 35], dtype='int64')
        sl, tp = np.array([95.0, 97.0]), np.array([110.0, 107.0])
        obs = xp.first_cross(self.times, prices, 0, 60, False, 1, u, sl, tp)
        self.assertEqual(obs[:2], (40, 'sl'))       # revised stop 97 applies from 35
        self.assertTrue(obs[4])
        back = xp.first_cross(self.times, prices, 0, 60, False, 1, u, sl, tp, variant='backfill')
        self.assertEqual(back[:2], (10, 'sl'))
        self.assertFalse(back[4])                   # already beyond on the first price
        # the entry plan (95, 110) is never reached after the first snapshot
        self.assertIsNone(xp.first_cross(self.times, prices, 0, 60, False, 1, u, sl, tp,
                                         variant='entry'))

    def test_short_side_and_buffer(self):
        prices = np.array([100.0, 102.05, 103.0, 90.0, 90.0])
        u = np.array([0], dtype='int64')
        sl, tp = np.array([102.0]), np.array([91.0])
        self.assertEqual(xp.first_cross(self.times, prices, 0, 60, False, -1, u, sl, tp)[:2],
                         (20, 'sl'))
        self.assertEqual(xp.first_cross(self.times, prices, 0, 60, False, -1, u, sl, tp,
                                        buffer=0.001)[:2], (30, 'sl'))
        # the closing time is excluded unless the episode is open at the end
        self.assertIsNone(xp.first_cross(self.times, prices, 0, 20, False, -1, u, sl, tp))
        self.assertEqual(xp.first_cross(self.times, prices, 0, 20, True, -1, u, sl, tp)[0], 20)

    def test_undeclared_level_never_crosses(self):
        prices = np.array([50.0, 150.0, 50.0, 150.0, 50.0])
        u = np.array([0], dtype='int64')
        self.assertIsNone(xp.first_cross(self.times, prices, 0, 60, False, 1, u,
                                         np.array([np.nan]), np.array([np.nan])))


class ClassifyTest(unittest.TestCase):
    steps = (np.array([0], dtype='int64'), np.array([95.0]), np.array([110.0]))

    def ep(self, **kw):
        base = {'closed': True, 'liq_close': False, 't_close': 100 * MIN, 't_end': 100 * MIN,
                'p_close': 100.0}
        return base | kw

    def test_classes(self):
        c = lambda ep, cross, st=self.steps: xp.classify(ep, cross, st, 0.0025, 15, 0)
        self.assertEqual(c(self.ep(), None, None), 'no_plan')
        self.assertEqual(c(self.ep(liq_close=True), (10 * MIN, 'sl', 94, 95, True)), 'liquidation')
        self.assertEqual(c(self.ep(), (10 * MIN, 'sl', 94, 95, True)), 'missed_sl')
        self.assertEqual(c(self.ep(), (90 * MIN, 'tp', 111, 110, True)), 'tp')
        self.assertEqual(c(self.ep(p_close=95.2), None), 'sl')          # near, not touched
        self.assertEqual(c(self.ep(p_close=109.9), None), 'tp')
        self.assertEqual(c(self.ep(), None), 'discretionary')
        self.assertEqual(c(self.ep(closed=False), None), 'open_no_cross')
        self.assertEqual(c(self.ep(closed=False), (10 * MIN, 'tp', 111, 110, True)), 'missed_tp')
        self.assertEqual(c(self.ep(closed=False), (95 * MIN, 'tp', 111, 110, True)),
                         'open_no_cross')


class PlanFollowTest(unittest.TestCase):
    def test_exit_at_crossing(self):
        legs = pd.DataFrame({'time': [0, 50, 200], 'sz': [10.0, 5.0, -15.0],
                             'px': [100.0, 98.0, 90.0], 'fee': [1.0, 0.5, 1.35]})
        legs['cash'] = -legs.sz * legs.px
        g, f = xp.plan_follow(legs, (100, 'sl', 94.0, 95.0, True), 0.001)
        self.assertAlmostEqual(g, -1000 - 490 + 15 * 94.0)
        self.assertAlmostEqual(f, 1.5 + 0.001 * 15 * 94.0)
        g, _ = xp.plan_follow(legs, (100, 'sl', 94.0, 95.0, True), 0.001, at='level')
        self.assertAlmostEqual(g, -1000 - 490 + 15 * 95.0)
        g, _ = xp.plan_follow(legs, (100, 'sl', 94.0, 95.0, False), 0.001, at='level')
        self.assertAlmostEqual(g, -1000 - 490 + 15 * 94.0)   # stale: no fill at the level


class PermutationTest(unittest.TestCase):
    def test_within_arm(self):
        rng = np.random.default_rng(0)
        arm = np.repeat([1, 2, 3, 4], 8)
        x = rng.normal(size=32)
        y = x + 0.1 * rng.normal(size=32)
        r = xp.perm_within_arm(x, y, arm, n=500)
        self.assertAlmostEqual(r['rho'], xp.within_arm_rho(x, y, arm))
        self.assertLess(r['p_two_sided'], 0.01)
        r = xp.perm_within_arm(x, rng.normal(size=32), arm, n=500)
        self.assertGreater(r['p_two_sided'], 0.0)
        self.assertLessEqual(r['p_two_sided'], 1.0)


OUT = ROOT / 'data/derived/exit_plan_adherence.json'


@unittest.skipUnless(OUT.exists(), 'run src/exit_plan_adherence.py first')
class OutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = json.loads(OUT.read_text())
        cls.acct = pd.read_csv(ROOT / 'data/derived/exit_plan_accounts.csv')
        # Per-episode rows reproduce organiser values and are not distributed
        # (DATA.md); without them the episode-level checks are skipped.
        episodes = ROOT / 'data/derived/organiser_hourly/exit_plan_episodes.csv'
        cls.ep = pd.read_csv(episodes) if episodes.exists() else None

    def need_episodes(self):
        if self.ep is None:
            self.skipTest('organiser-derived episode rows not present')

    def test_identity_and_counts(self):
        r = self.r
        self.assertLess(r['identity_episode_gross_vs_decomposition_max_abs_usd'], 5.0)
        self.assertEqual(sum(r['class_counts_primary'].values()), r['coverage']['planned'])
        self.assertAlmostEqual(sum(v for k, v in r['classes_primary'].items() if k != 'n'), 1.0)
        self.assertEqual(len(self.acct), 32)
        self.need_episodes()
        self.assertEqual(len(self.ep), r['coverage']['episodes'])
        self.assertEqual(int(self.ep.planned.sum()), r['coverage']['planned'])

    def test_pnl_totals(self):
        r = self.r
        self.assertAlmostEqual(self.acct.delta_gross_pp.sum() / 32,
                               r['explain_timing']['plan_minus_actual_gross_pp_total'], places=9)
        self.assertAlmostEqual(self.acct.timing_exec_pp.sum() / 32,
                               r['explain_timing']['timing_exec_pp_total'], places=9)
        self.need_episodes()
        unplanned = self.ep[~self.ep.planned]
        self.assertTrue((unplanned.delta_gross.abs() < 1e-9).all())

    def test_linked_plans_are_consistent(self):
        pc = self.r['plan_coverage']
        self.assertLess(pc['wrong_side_share_linked'], 0.01)
        self.assertGreater(pc['wrong_side_share_unlinked'], 0.1)

    def test_macros_match_report(self):
        tex = (ROOT / 'paper/frl/exitplan_numbers.tex').read_text()
        r = self.r
        self.assertIn(f"\\alExitPlanned}}{{{r['coverage']['planned']:,}}}".replace(',', '{,}'), tex)
        self.assertIn(f"\\alExitMissed}}{{{100 * (r['classes_primary']['missed_sl'] + r['classes_primary']['missed_tp']):.1f}}}", tex)
        self.assertIn(f"\\alExitPlanGross}}{{{r['explain_timing']['plan_minus_actual_gross_pp_total']:.2f}}}", tex)
        self.assertIn('\\label{tab:exitplan}', (ROOT / 'paper/frl/exitplan_table.tex').read_text())


if __name__ == '__main__':
    unittest.main()
