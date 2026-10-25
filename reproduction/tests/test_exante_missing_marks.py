"""Frozen-book regression: absent marks must not erase an account silently."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import exante_benchmark


class FrozenBookMissingMarkTest(unittest.TestCase):
    def frames(self, held_missing_mark=False, missing_equity=False):
        grid = [0, 3_600_000, 7_200_000]
        rows = []
        for coin, quantity, prices in (
            ('BTC', 1.0, [100.0, 100.0, 105.0]),
            ('@DUST', float(held_missing_mark), [np.nan, np.nan, 10.0]),
        ):
            rows.extend(dict(season='S1', tag='test-account', model='test-model',
                             competition_id=1, coin=coin, t=t,
                             signed_size=quantity, px=px)
                        for t, px in zip(grid, prices))
        equity = pd.DataFrame(dict(tag=['test-account'] * 3, t=grid,
                                   equity=[10_000.0, np.nan if missing_equity
                                           else 10_000.0, 10_005.0]))
        if missing_equity:
            equity['equity'] = np.nan
        return {'fills': pd.DataFrame(), 'panel': pd.DataFrame(rows),
                'equity': equity,
                'funding': pd.DataFrame(columns=['tag', 'time', 'usdc'])}

    def run_case(self, **kwargs):
        data = self.frames(**kwargs)
        with patch.object(exante_benchmark.pd, 'read_parquet',
                          side_effect=lambda path: data[Path(path).stem]), \
             patch.object(exante_benchmark.analyse, 'common_window',
                          return_value=(0, 7_200_000)):
            return exante_benchmark.run('S1', form_hours=1, mmr=0.05)

    def test_unheld_unpriced_instrument_does_not_erase_held_book(self):
        result = self.run_case()
        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, 'instruments_held'], 1)
        self.assertAlmostEqual(result.loc[0, 'hold_net'], 5.0)
        self.assertTrue(np.isfinite(result.loc[0, 'min_margin_ratio']))

    def test_held_instrument_with_missing_formation_mark_fails(self):
        with self.assertRaisesRegex(ValueError, 'Non-finite frozen position or mark'):
            self.run_case(held_missing_mark=True)

    def test_missing_equity_fails_instead_of_entering_sum_as_nan(self):
        with self.assertRaisesRegex(ValueError, 'Non-finite frozen valuation path'):
            self.run_case(missing_equity=True)


if __name__ == '__main__':
    unittest.main()
