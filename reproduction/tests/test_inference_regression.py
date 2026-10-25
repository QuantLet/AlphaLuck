"""Regression checks for exact rank comparisons and permutation provenance."""
import itertools
import json
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import inference_audit as ia
import vol_fixed_denominator as vd
import check_risk_trait as cr

class InferenceRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w = pd.read_csv(ROOT / 'data/derived/c4_wallet_risk.csv').merge(
            pd.read_csv(ROOT / 'data/derived/i6_vol_denominator.csv')
            [['tag', 'vol_fixed', 'leverage_fixed', 'turnover_fixed']], on='tag')

    def test_fixed_profile_fixture_includes_equal_statistics(self):
        fixture = json.loads((ROOT / 'tests/fixtures/profile_rank_ties.json').read_text())
        x, y = np.array(fixture['risk_ranks']), np.array(fixture['return_ranks'])
        frame = pd.DataFrame([{'model': i, 'arm': a, 'risk': x[i, a],
                               'final_return_pct': y[i, a]}
                              for i in range(8) for a in range(4)])
        result = ia.profile_permutation(frame, 'risk')
        self.assertEqual(result['p_profile'], fixture['extreme_count'] / fixture['n_permutations'])

    def test_current_profiles_match_independent_rank_distance_oracle(self):
        # Spearman's rank-distance formula provides a separate exact oracle;
        # these counts are computed from current data, never stale constants.
        permutations = np.array(list(itertools.permutations(range(8))))
        y = self.w.pivot(index='model', columns='arm', values='final_return_pct').to_numpy()
        yr = stats.rankdata(y, axis=0).astype(int)
        for metric in ['vol_fixed', 'leverage_fixed', 'turnover_fixed']:
            x = self.w.pivot(index='model', columns='arm', values=metric).to_numpy()
            self.assertTrue(all(len(np.unique(x[:, a])) == 8 for a in range(4)))
            xr = stats.rankdata(x, axis=0).astype(int)
            distances = ((xr[permutations] - yr)**2).sum(axis=(1, 2))
            observed = ((xr - yr)**2).sum()
            # Mean rho = 1 - 6*total squared rank distance / (4*8*(8**2-1)).
            scale = 4*8*(8**2-1)
            expected = np.mean(np.abs(scale-6*distances) >= abs(scale-6*observed))
            with self.subTest(metric=metric):
                self.assertEqual(ia.profile_permutation(self.w, metric)['p_profile'], expected)

    def test_profile_ties_match_spearman_and_include_boundary(self):
        x = np.array([[1, 1], [1, 2], [3, 2], [4, 4]])
        y = np.array([[4, 1], [3, 4], [2, 3], [1, 2]])
        data = pd.DataFrame([
            {'model': i, 'arm': a, 'risk': x[i, a], 'final_return_pct': y[i, a]}
            for i in range(4) for a in range(2)])
        observed = np.mean([stats.spearmanr(x[:, a], y[:, a]).statistic
                            for a in range(2)])
        null = np.array([np.mean([
            stats.spearmanr(x[list(p), a], y[:, a]).statistic
            for a in range(2)]) for p in itertools.permutations(range(4))])
        expected = np.mean((np.abs(null) > abs(observed)) |
                           np.isclose(np.abs(null), abs(observed), atol=1e-14, rtol=0))
        out = ia.profile_permutation(data, 'risk')
        self.assertAlmostEqual(out['obs'], observed, places=14)
        self.assertEqual(out['p_profile'], expected)

    def test_permutation_rng_isolated_and_matches_direct_sums_of_squares(self):
        grid = self.w.pivot(index='model', columns='arm', values='share_in_market').to_numpy()
        def f(y):
            ss_m = y.shape[1] * np.sum((y.mean(1) - y.mean())**2)
            resid = y - y.mean(1)[:, None] - y.mean(0)[None, :] + y.mean()
            return (ss_m / (y.shape[0]-1)) / (
                np.sum(resid**2) / ((y.shape[0]-1)*(y.shape[1]-1)))
        observed = f(grid)
        old_n, before = vd.NPERM, repr(vd.RNG.bit_generator.state)
        try:
            vd.NPERM = 500
            actual = vd.perm_F(grid, observed, rng=np.random.default_rng(20261009))
            independent = np.random.default_rng(20261009)
            tails = sum(f(np.column_stack([
                independent.permutation(grid[:, a]) for a in range(grid.shape[1])
            ])) >= observed for _ in range(500))
            self.assertEqual(actual, (tails + 1) / 501)
            self.assertEqual(before, repr(vd.RNG.bit_generator.state))
        finally:
            vd.NPERM = old_n

    def test_regenerated_artifact_has_permutation_p_and_consistent_holm(self):
        out = json.loads((ROOT / 'data/derived/i4_inference.json').read_text())
        grid = self.w.pivot(index='model', columns='arm', values='share_in_market').to_numpy()
        expected = vd.perm_F(grid, vd.anova_icc(grid)['F_model'],
                             rng=np.random.default_rng(20261009))
        self.assertEqual(out['holm']['raw']['F:share_in_market'], expected)
        adjusted = ia.holm(out['holm']['raw'])
        self.assertEqual(out['holm']['adjusted'], adjusted)
        self.assertEqual(out['holm']['n_survive'], sum(p < .05 for p in adjusted.values()))

class KendallRegression(unittest.TestCase):
    def test_tie_correction_and_permutation_ordering(self):
        y = np.array([[1, 1], [1, 2], [3, 2], [4, 4]], dtype=float)
        out = cr.kendall_w(y)
        expected = stats.friedmanchisquare(*y).statistic / (2 * 3)
        self.assertAlmostEqual(out['kendall_W'], expected, places=14)
        ranks = out['ranks']
        n, m = ranks.shape
        obs_s = np.sum((ranks.sum(1) - m*(n+1)/2)**2)
        obs_w = out['kendall_W']
        for p in itertools.permutations(range(n)):
            draw = np.column_stack([ranks[list(p), 0], ranks[:, 1]])
            s = np.sum((draw.sum(1) - m*(n+1)/2)**2)
            self.assertEqual(s >= obs_s, cr.kendall_w(draw)['kendall_W'] >= obs_w)
        # Independent module must implement the same tie correction.
        old = vd.NPERM
        try:
            vd.NPERM = 0
            self.assertAlmostEqual(vd.kendall_w(y)['W'], expected, places=14)
        finally:
            vd.NPERM = old

    def test_null_preserves_ties_and_rng_sequence(self):
        y = np.array([[1, 1], [1, 2], [3, 2], [4, 4]], dtype=float)
        ranks = stats.rankdata(y, axis=0)
        obs = np.sum((ranks.sum(1) - 5)**2)
        base = np.sort(ranks, axis=0)
        rng = np.random.default_rng(51)
        tails = 0
        for _ in range(500):
            draw = np.column_stack([rng.permutation(base[:, a]) for a in range(2)])
            self.assertEqual(sorted(draw[:, 0]), sorted(ranks[:, 0]))
            self.assertEqual(sorted(draw[:, 1]), sorted(ranks[:, 1]))
            tails += np.sum((draw.sum(1)-5)**2) >= obs
        self.assertEqual(cr.perm_p_w(y, nperm=500, rng=np.random.default_rng(51)),
                         (tails + 1)/501)

if __name__ == '__main__':
    unittest.main()
