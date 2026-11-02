import unittest
from formation_sensitivity import *

class FormationSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=sum((evaluate(h) for h in [12,24,48]),[])

    def test_reconciled_24h_positions_are_recovered(self):
        original={p['model_id']:p for p in read(OLD/'results/positions_reconciliation.json')}
        for r in self.rows:
            if r['formation_hour']==24:
                self.assertEqual(r['formation_positions_raw'],original[r['model_id']]['formation_positions_raw'])

    def test_24h_wealth_comparison_reproduces_original(self):
        original={p['model_id']:p for p in read(OUT/'replication_results.json')['models']}
        for r in self.rows:
            if r['formation_hour']==24:
                self.assertLess(abs(r['trading_minus_holding']-D(original[r['model_id']]['trading_minus_holding_USDC_net_gas'])),D('1e-20'))

    def test_bounds_cover_estimate_and_fresh_marks_narrow_them(self):
        for r in self.rows:
            wide=r['bounds']['settlement_only'];narrow=r['bounds']['max_trade_age_1h']
            self.assertLessEqual(wide['lower'],narrow['lower']+D('1e-20'))
            self.assertLessEqual(narrow['upper'],wide['upper']+D('1e-20'))
            self.assertLessEqual(narrow['lower'],r['trading_minus_holding']+D('1e-20'))
            self.assertGreaterEqual(narrow['upper'],r['trading_minus_holding']-D('1e-20'))

    def test_formation_is_exclusive_of_later_events(self):
        row={'model_id':'x','time_utc':'2026-02-10T00:00:00Z','changes':[{'token_id':'a','quantity_raw':1000000}]}
        cut=ts(row['time_utc'])
        self.assertEqual(positions_at([row],'x',cut),{})
        self.assertEqual(positions_at([row],'x',cut+1),{'a':D(1)})

    def test_cash_only_and_unattributed_accounts_remain_explicit(self):
        for r in self.rows:
            if r['model_id']=='mystery-model-alpha':self.assertTrue(r['cash_only'])
            if r['model_id']=='gpt-5.2':self.assertFalse(r['eligible'])

if __name__=='__main__':unittest.main()
