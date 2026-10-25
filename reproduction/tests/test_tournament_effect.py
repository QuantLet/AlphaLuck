"""Tournament-effect test: standings, permutation sets, prompt parsing, outputs."""
from pathlib import Path
import json
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import tournament_effect as te


class StandingTest(unittest.TestCase):
    def test_behind_is_zero_for_leader_one_for_last(self):
        eq = np.array([[12_000.0], [9_000.0], [10_000.0]])
        np.testing.assert_allclose(te.behind_score(eq)[:, 0], [0.0, 1.0, 0.5])


class LabelTestTest(unittest.TestCase):
    def frame(self, rho3):
        rng = np.random.default_rng(0)
        r = pd.DataFrame(rng.normal(0, .01, (8, 4)), columns=[1, 2, 3, 4],
                         index=[f'm{i}' for i in range(8)])
        r[3] += rho3
        return r

    def test_enumerates_all_assignments_and_is_exact(self):
        out = te.label_test(self.frame(0.5), (1, 2, 4))
        self.assertEqual(out['n_assignments'], 4 ** 8)
        self.assertAlmostEqual(out['p_one_sided_greater'], 1 / 4 ** 8)
        self.assertAlmostEqual(out['obs'], te.did(self.frame(0.5)), places=12)
        no4 = te.label_test(self.frame(0.5), (1, 2))
        self.assertEqual(no4['n_assignments'], 3 ** 8)

    def test_identity_contrast_is_symmetric(self):
        r = self.frame(0.0)
        r[:] = 0.3
        out = te.label_test(r, (1, 2, 4))
        self.assertAlmostEqual(out['obs'], 0.0)
        self.assertEqual(out['p_two_sided'], 1.0)

    def test_drops_models_with_undefined_rho(self):
        r = self.frame(0.5)
        r.loc['m0', 3] = np.nan
        out = te.label_test(r, (1, 2, 4))
        self.assertEqual(out['n_models'], 7)
        self.assertEqual(out['n_assignments'], 4 ** 7)


class ShiftTestTest(unittest.TestCase):
    def test_detects_aligned_relation(self):
        rng = np.random.default_rng(1)
        b = np.cumsum(rng.normal(size=(4, 200)), axis=1)
        out = te.shift_test(b, b + rng.normal(0, .1, b.shape), 10)
        self.assertGreater(out['obs'], 0.9)
        self.assertEqual(out['n_shifts'], 200 - 2 * 10 + 1)


class PromptParseTest(unittest.TestCase):
    def test_parses_standings_block(self):
        prompt = ("x\n# CURRENT STATE OF COMPETITION\nThe current standings ...\n\n"
                  "1. mystery-model - Total Account Value: 16158.52, Return (%): 61.585\n"
                  "2. **YOU** - Total Account Value: 9211.23, Return (%): -7.888\n"
                  "# CURRENT AVAILABLE CAPITAL\n1.0\n")
        self.assertEqual(te.parse_standings(prompt),
                         [(1, 'mystery-model', 16158.52), (2, '**YOU**', 9211.23)])
        self.assertIsNone(te.parse_standings('no block'))


class OutputsTest(unittest.TestCase):
    path = ROOT / 'data/derived/tournament_effect.json'

    @unittest.skipUnless(path.exists(), 'run src/tournament_effect.py first')
    def test_published_numbers(self):
        r = json.loads(self.path.read_text())
        p = r['H24_behind_d_gross_eqk']
        self.assertEqual(p['vs124']['n_assignments'], 65_536)
        self.assertEqual(p['vs124']['n_models'], 8)
        self.assertTrue(0 < p['vs124']['p_two_sided'] <= 1)
        c = r['conversations']
        self.assertEqual(c['prompts_with_standings_by_arm'], {'1': 0, '2': 0, '3': 25, '4': 0})
        self.assertEqual(c['all_ranks_match_organiser'], c['arm3_prompts'])
        self.assertGreater(r['organiser_rank_agreement']['rank_identical_share'], 0.9)
        tex = (ROOT / 'paper/frl/tournament_numbers.tex').read_text()
        self.assertIn('\\newcommand{\\alTourDiD}', tex)


if __name__ == '__main__':
    unittest.main()
