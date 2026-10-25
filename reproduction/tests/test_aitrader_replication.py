"""AI-Trader replication: book loading, pricing, frozen advantage, hedge, outputs."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import aitrader_replication as ar


def log(rows):
    f = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
    f.write('\n'.join(json.dumps(r) for r in rows) + '\n')
    f.close()
    return Path(f.name)


class BookTest(unittest.TestCase):
    rows = [
        {'date': '2025-10-01 10:00:00', 'id': 0, 'positions': {'A': 0, 'CASH': 100.0}},
        {'date': '2025-10-01 11:00:00', 'id': 1, 'this_action': {'action': 'no_trade'},
         'positions': {'A': 0, 'CASH': 100.0}},
        {'date': '2025-10-02 10:00:00', 'id': 2, 'this_action': {'action': 'buy'},
         'positions': {'A': 1, 'CASH': 90.0}},
        {'date': '2025-10-02 10:00:00', 'id': 3, 'this_action': {'action': 'buy'},
         'positions': {'A': 2, 'CASH': 80.0}},
    ]

    def test_last_record_per_step_and_first_trade_date(self):
        q, cash, first = ar.load_book(log(self.rows))
        self.assertEqual(len(q), 3)
        self.assertEqual(q['A'].iloc[-1], 2)
        self.assertEqual(cash.iloc[-1], 80.0)
        self.assertEqual(str(first), '2025-10-02')

    def test_negative_cash_is_rejected(self):
        bad = self.rows + [{'date': '2025-10-03 10:00:00', 'id': 4,
                            'this_action': {'action': 'buy'},
                            'positions': {'A': 3, 'CASH': -5.0}}]
        with self.assertRaises(ValueError):
            ar.load_book(log(bad))


class PricingTest(unittest.TestCase):
    def test_latest_earlier_price_and_nan_before_first(self):
        t = pd.to_datetime(['2025-10-01 10:00', '2025-10-01 12:00', '2025-10-01 13:00'])
        prices = {'A': pd.Series([5.0], index=pd.to_datetime(['2025-10-01 11:00']))}
        px = ar.price_matrix(prices, t, ['A'])
        self.assertTrue(np.isnan(px['A'].iloc[0]))
        self.assertEqual(px['A'].iloc[2], 5.0)

    def test_frozen_advantage(self):
        q = pd.DataFrame({'A': [0.0, 2.0, 0.0]})
        cash = pd.Series([100.0, 80.0, 110.0])
        px = pd.DataFrame({'A': [10.0, 10.0, 20.0]})
        # frozen: 80 + 2 x 20 = 120; actual: 110
        self.assertAlmostEqual(ar.frozen_advantage(q, cash, px, 1, 2), 10.0)

    def test_hedge_of_index_holding_is_its_gain(self):
        m = np.array([1.0, 1.1, 0.99])
        n = 100 * m
        self.assertAlmostEqual(ar.hedge_charge(n, m), n[-1] - n[0])


class OutputsTest(unittest.TestCase):
    path = ROOT / 'data/derived/aitrader_replication.json'

    @unittest.skipUnless(path.exists(), 'run src/aitrader_replication.py first')
    def test_published_numbers(self):
        r = json.loads(self.path.read_text())
        self.assertEqual(r['all']['accounts'], 26)
        self.assertEqual({k: r[k]['accounts'] for k in ar.MARKETS},
                         {'us': 6, 'astock': 7, 'astock_h': 7, 'crypto': 6})
        for k in ar.MARKETS:
            v = r[k]
            self.assertAlmostEqual(v['frozen_pct'] - v['actual_pct'], v['advantage_pp'], places=6)
        acc = pd.read_csv(ROOT / 'data/derived/aitrader_accounts.csv')
        np.testing.assert_allclose(acc['frozen_close'] - acc['equity_close'],
                                   acc['advantage'], atol=1e-6)
        tex = (ROOT / 'paper/frl/aitrader_numbers.tex').read_text()
        self.assertIn('\\newcommand{\\alAitAhead}', tex)


if __name__ == '__main__':
    unittest.main()
