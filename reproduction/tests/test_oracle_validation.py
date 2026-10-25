"""Funding-implied oracle prices: the identity, and the stored validation results."""
from pathlib import Path
import json
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import oracle_validation as ov

RESULT = ROOT / 'data' / 'derived' / 'oracle_validation.json'


class ImpliedOracleTest(unittest.TestCase):
    def test_recovers_oracle_and_skips_small_payments(self):
        H = ov.HOUR
        rows = []
        for tag, szi in (('a', 12.0), ('b', -40.0), ('c', 1e-4)):
            rate = 1.25e-5
            usdc = round(-szi * 180.5 * rate, 6)
            rows.append({'tag': tag, 'coin': 'xyz:NVDA', 'hour': 5 * H, 'szi': szi,
                         'funding_rate': rate, 'usdc': usdc})
        o = ov.implied_oracle(pd.DataFrame(rows))
        self.assertEqual(len(o), 1)
        self.assertEqual(int(o.n_accounts.iloc[0]), 2)  # 'c' fails the rounding screen
        self.assertAlmostEqual(o.oracle_px.iloc[0], 180.5, delta=180.5 * ov.MAX_REL_ROUNDING)


@unittest.skipUnless(RESULT.exists(), 'run src/oracle_validation.py first')
class StoredResultTest(unittest.TestCase):
    def setUp(self):
        self.r = json.loads(RESULT.read_text())

    def test_refetch_identical(self):
        f = self.r['funding_refetch_vs_stored']
        self.assertEqual(f['stored_rows'], f['matched_rows'])
        self.assertEqual(f['stored_rows'], f['rate_exact_equal'])

    def test_account_rates_equal_public_rates(self):
        u = self.r['user_vs_public_funding_rate']
        self.assertEqual(u['user_funding_rows'], u['matched_to_public_hour'])
        self.assertEqual(u['rate_rel_diff_gt_1e-6'], 0)

    def test_implied_oracle_consistent_across_accounts(self):
        self.assertLess(self.r['implied_oracle']['dispersion_bps_max'], 5.0)


if __name__ == '__main__':
    unittest.main()
