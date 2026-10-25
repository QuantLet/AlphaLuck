"""Holding versus trading: hedge charge, gross scaling, rank resampling, outputs."""
from pathlib import Path
import json
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import holding_vs_trading as hv


class HedgeTest(unittest.TestCase):
    def test_constant_net_sums_per_step_returns(self):
        index = np.array([100.0, 110.0, 99.0])
        net = np.array([1_000.0, 1_000.0, 1_000.0])
        self.assertAlmostEqual(hv.hedge_charge(net, index), 1_000 * (0.1 - 0.1))

    def test_frozen_book_in_index_is_fully_hedged(self):
        index = np.array([100.0, 104.0, 98.0, 107.0])
        q = 3.0
        mtm = q * (index[-1] - index[0])
        self.assertAlmostEqual(mtm - hv.hedge_charge(q * index, index), 0.0)

    def test_last_point_carries_no_charge(self):
        self.assertEqual(hv.hedge_charge([0.0, 5e6], [100.0, 50.0]), 0.0)


class ScaleTest(unittest.TestCase):
    def test_ratio_of_means(self):
        self.assertAlmostEqual(hv.gross_scale([4.0, 8.0], [2.0, 2.0]), 3.0)

    def test_flat_book_keeps_unit_scale(self):
        self.assertEqual(hv.gross_scale([4.0, 8.0], [0.0, 0.0]), 1.0)


class DeviationTest(unittest.TestCase):
    def test_parts_add_to_the_deviation(self):
        q = np.array([5.0, 3.0, 0.0, -2.0, 7.0, 5.0])
        for q0 in (5.0, -5.0, 0.0):
            for x in (q, -q):
                parts = hv.split_deviation(x, q0)
                np.testing.assert_allclose(sum(parts.values()), x - q0)

    def test_long_book_classification(self):
        p = hv.split_deviation([3.0, 8.0, -2.0], 5.0)
        np.testing.assert_allclose(p['reduce'], [-2.0, 0.0, -5.0])
        np.testing.assert_allclose(p['add'], [0.0, 3.0, 0.0])
        np.testing.assert_allclose(p['reverse'], [0.0, 0.0, -2.0])

    def test_flat_book_is_new(self):
        p = hv.split_deviation([0.0, 2.0, -1.0], 0.0)
        np.testing.assert_allclose(p['new'], [0.0, 2.0, -1.0])
        self.assertEqual(float(np.abs(p['reduce']).sum()), 0.0)


class RankTest(unittest.TestCase):
    def test_ranks_are_one_for_highest(self):
        total = np.array([[0.1, -0.2, 0.3], [-1.0, 0.0, 1.0]])
        np.testing.assert_array_equal(hv.model_ranks(total), [[2, 3, 1], [3, 2, 1]])

    def test_totals_average_arms_and_add_opening(self):
        pnl = np.ones((14, 2, 4)) * 0.01
        opening = np.zeros((2, 4))
        opening[1] = 0.02
        np.testing.assert_allclose(hv.model_totals(pnl, opening), [0.14, 0.16])

    def test_blocks_are_contiguous_and_truncated(self):
        ids = hv.moving_blocks(14, 3, 50, np.random.default_rng(0))
        self.assertEqual(ids.shape, (50, 14))
        self.assertTrue(((ids >= 0) & (ids < 14)).all())
        for row in ids:
            for b in range(0, 12, 3):
                np.testing.assert_array_equal(np.diff(row[b:b + 3]), [1, 1])


class OutputsTest(unittest.TestCase):
    path = ROOT / 'data/derived/holding_vs_trading.json'

    @unittest.skipUnless(path.exists(), 'run src/holding_vs_trading.py first')
    def test_published_numbers(self):
        r = json.loads(self.path.read_text())
        b = r['benchmark']
        self.assertEqual(b['accounts'], 32)
        self.assertAlmostEqual(b['hold_pct'] - b['actual_pct'], b['advantage_pp'], places=9)
        self.assertAlmostEqual(b['advantage_before_costs_pp'] + b['fees_after_pp']
                               + b['funding_diff_pp'], b['advantage_pp'], places=9)
        ref = json.loads((ROOT / 'data/derived/funding_hourly_sensitivity.json').read_text())
        s24 = next(s for s in ref['scenarios'] if s['freeze_hours'] == 24)['proxy']
        self.assertAlmostEqual(b['advantage_pp'], s24['advantage_pp'], places=9)
        self.assertEqual(b['ahead'], s24['accounts_ahead'])
        d = pd.read_csv(ROOT / 'data/derived/holding_vs_trading_accounts.csv')
        self.assertTrue((d['fees_after'] >= 0).all())
        rk = pd.read_csv(ROOT / 'data/derived/holding_vs_trading_ranks.csv')
        self.assertEqual(len(rk), 3 * 8)
        self.assertTrue((rk['rank_lo'] <= rk['rank']).all() and (rk['rank'] <= rk['rank_hi']).all())
        dv = r['deviations']
        parts = sum(dv[f'{k}_pp'] for k in hv.DEV_PARTS)
        self.assertAlmostEqual(parts, dv['total_pp'], places=6)
        self.assertAlmostEqual(dv['total_pp'], b['advantage_before_costs_pp'], delta=0.05)
        tex = (ROOT / 'paper/frl/holding_numbers.tex').read_text()
        self.assertIn('\\newcommand{\\alHvtBeforeCosts}', tex)
        # coarser grids move terms into the residual but keep the total
        for grid in r['robustness']['deviation_grids_pp'].values():
            self.assertAlmostEqual(sum(grid.values()), dv['total_pp'], places=6)
        loo = pd.read_csv(ROOT / 'data/derived/holding_vs_trading_leave_one_out.csv')
        drop = loo[loo['drop'] == 'instrument'].set_index('name')['before_costs']
        for coin, v in dv['by_coin_pp'].items():
            self.assertAlmostEqual(drop[coin], dv['total_pp'] - v, places=6)
        models = loo[loo['drop'] == 'model']
        self.assertEqual(len(models), 8)
        # each account is left out once, by its model
        self.assertAlmostEqual((models['advantage'] * models['accounts']).sum(),
                               7 * 32 * b['advantage_pp'], places=6)
        beats = pd.read_csv(ROOT / 'data/derived/holding_vs_trading_rank_pairs.csv', index_col=0)
        np.testing.assert_allclose(beats.to_numpy() + beats.to_numpy().T, 1 - np.eye(8), atol=1e-12)


if __name__ == '__main__':
    unittest.main()
