"""Organiser-hourly checks: the isolated formula and agreement with published rows."""
from pathlib import Path
import json
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import organiser_hourly as oh


class IsolatedFormulaTest(unittest.TestCase):
    def test_recovers_maintenance_fraction(self):
        rows = []
        for symbol, l in (('xyz:A', 0.05), ('xyz:B', 0.025)):
            for q, P, M in ((10.0, 100.0, 120.0), (-4.0, 250.0, 90.0), (2.5, 80.0, 30.0)):
                s = np.sign(q)
                L = P - s * (M - l * abs(q) * P) / abs(q) / (1 - l * s)
                rows.append({'symbol': symbol, 'quantity': q, 'current_price': P,
                             'margin': M, 'liquidation_price': L})
        rates, fit = oh.isolated_fit(pd.DataFrame(rows))
        self.assertAlmostEqual(rates['xyz:A'], 0.05, places=12)
        self.assertAlmostEqual(rates['xyz:B'], 0.025, places=12)
        self.assertLess(fit['abs_pct_error_all']['1.0'], 1e-9)


class PublishedRowsTest(unittest.TestCase):
    def test_sweep_matches_hourly_funding_rows(self):
        report = json.loads((ROOT / 'data/derived/organiser_hourly.json').read_text())
        published = json.loads(
            (ROOT / 'data/derived/hourly_funding_benchmark_sensitivity.json').read_text())
        self.assertLess(report['sweep_reproduces_published_rows_max_abs_usd'], 1e-6)
        rows = {r['formation_hour']: r for r in report['sweep_primary']}
        for item in published['results']:
            row = rows[item['freeze_h']]
            self.assertAlmostEqual(row['advantage_pp'],
                                   100 * item['advantage'] / 320_000, places=8)
            self.assertEqual(row['accounts_ahead'], item['better'])

    def test_macros_match_report(self):
        report = json.loads((ROOT / 'data/derived/organiser_hourly.json').read_text())
        tex = (ROOT / 'paper/frl/organiser_numbers.tex').read_text()
        p24 = {r['formation_hour']: r for r in report['sweep_primary']}[24]
        self.assertIn(f"\\alOrgIsoAccounts}}{{{p24['isolated_accounts_liquidated']}}}", tex)
        self.assertIn(f"\\alOrgSweepPositive}}{{{report['sweep_summary']['all']['hours_positive']}}}", tex)


class HorizonTest(unittest.TestCase):
    def test_fixed_horizons_are_consistent(self):
        s = pd.read_csv(ROOT / 'data/derived/organiser_hourly_sweep.csv')
        a = pd.read_csv(ROOT / 'data/derived/organiser_hourly_sweep_accounts.csv')
        for w in oh.HORIZONS:
            # a horizon exists exactly when it ends by the close
            has = s[f'advantage_pp_{w}h'].notna()
            self.assertTrue((has == (s.remaining_days * 24 >= w - 1e-9)).all())
            agg = a.groupby('formation_hour')[f'advantage_{w}h'].sum() / 320_000 * 100
            got = s.set_index('formation_hour')[f'advantage_pp_{w}h'].dropna()
            self.assertLess((agg.loc[got.index] - got).abs().max(), 1e-9)
        per_day = s.advantage_pp / s.remaining_days
        self.assertLess((per_day - s.advantage_pp_per_day).abs().max(), 1e-12)


class StressTest(unittest.TestCase):
    def test_unstressed_row_is_the_primary_result(self):
        r = json.loads((ROOT / 'data/derived/organiser_hourly.json').read_text())
        p24 = next(x for x in r['sweep_primary'] if x['formation_hour'] == 24)
        base = r['liquidation_stress']['at_24h'][0]
        self.assertEqual(base['scenario'], 'none')
        for c in 'AB':
            self.assertAlmostEqual(base[f'advantage_pp_{c}'], p24[f'isolated_{c}_advantage_pp'], places=9)
            self.assertAlmostEqual(base[f'advantage_pp_168h_{c}'],
                                   p24[f'isolated_{c}_advantage_pp_168h'], places=9)

    def test_costs_only_lower_the_advantage(self):
        rows = {x['scenario']: x for x in json.loads(
            (ROOT / 'data/derived/organiser_hourly.json').read_text())['liquidation_stress']['at_24h']}
        for name in ('slippage 0.25%', 'slippage 1.3%', 'charge 10 bp', 'unscreened at worst mark'):
            for c in 'AB':
                self.assertLessEqual(rows[name][f'advantage_pp_{c}'], rows['none'][f'advantage_pp_{c}'] + 1e-12)
        self.assertLessEqual(rows['slippage 1.3%']['advantage_pp_B'], rows['slippage 0.25%']['advantage_pp_B'])


class ExposureTest(unittest.TestCase):
    def test_reproduces_published_exposure(self):
        x = json.loads((ROOT / 'data/derived/exposure_mechanics.json').read_text())
        pub = json.loads((ROOT / 'data/derived/i6_vol_denominator.json').read_text())
        self.assertLess(x['reproduces_published_max_abs'], 1e-9)
        for key in ('leverage_equity', 'leverage_fixed'):
            self.assertAlmostEqual(x[key]['assoc_rho'], pub[key]['assoc_rho'], places=12)


if __name__ == '__main__':
    unittest.main()
