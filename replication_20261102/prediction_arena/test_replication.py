import unittest
from calculate_replication import *

class ReplicationTests(unittest.TestCase):
    def setUp(self):
        self.r=read(OUT/'replication_results.json')['models'];self.m=read(OUT/'valuation_marks.json');self.g=read(OUT/'gas_valued.json')
    def test_complete_marks_and_no_future_data(self):
        self.assertEqual(len(self.m['formation']),6);self.assertEqual(len(self.m['endpoint']),93)
        for label,cut in [('formation',FREEZE),('endpoint',END)]:
            for mark in self.m[label].values():
                self.assertTrue(0<=D(mark['price'])<=1)
                self.assertLess(D(mark['evidence_time']),cut)
                if mark['method']=='last_transaction_VWAP':self.assertLessEqual(D(mark['age_seconds']),86400)
    def test_settlement_evidence_exists(self):
        proof={x['id']:x for x in read(RAW/'global_redemptions.json')+read(OLD/'results/redemptions_crosschecked.json')}
        for mark in self.m['endpoint'].values():
            if mark['method']=='contractual_payout':
                row=proof[mark['evidence_event_id']];self.assertEqual(row['condition'],mark['condition']);self.assertLess(D(row['timestamp']),END)
    def test_price_rows_unique_and_prior(self):
        for label in ['formation','endpoint','funding']:
            rows=read(RAW/(label+'_price_events.json'));coverage=read(RAW/('prices_'+label)/'coverage.json')
            self.assertEqual(len(rows),len({r['id'] for r in rows}))
            self.assertEqual(len(rows),coverage['events'])
            for row in rows:self.assertLess(D(row['timestamp']),D(str(coverage['cutoff_exclusive'])))
    def test_execution_marks_avoid_duplicate_summary(self):
        for label in ['formation','endpoint']:
            events={x['id']:x for x in read(RAW/(label+'_price_events.json'))}
            for m in self.m[label].values():
                if m['method']!='last_transaction_VWAP':continue
                selected=[events[i] for i in m['fill_event_ids']]
                if m['fill_selection']=='maker_components':self.assertTrue(all(x['taker'].lower() not in EXCHANGES for x in selected))
                else:self.assertTrue(all(x['taker'].lower() in EXCHANGES for x in selected))
                self.assertEqual(D(m['price']),D(m['cash_USDCE'])/D(m['quantity']))
    def test_gas_no_lookahead_and_no_duplicates(self):
        self.assertEqual(len(self.g),len({(x['model_id'],x['transaction_hash']) for x in self.g}))
        original={(x['model_id'],x['Transaction Hash']):x for x in read(OLD/'results/network_fees.json')}
        for g in self.g:
            self.assertTrue(original[g['model_id'],g['transaction_hash']]['paid_by_wallet'])
            self.assertLess(D(g['quote_close_time_us'])/10**6,D(g['timestamp']))
            self.assertEqual(D(g['gas_USDC']),D(g['fee_POL'])*D(g['POL_USDC_asof']))
    def test_same_cashflows_and_common_starting_wealth(self):
        ledger=read(OLD/'results/cash_ledger.json')
        for r in self.r:
            flow=sum((D(x['net_cash_raw'])/10**6 for x in ledger if x['model_id']==r['model_id'] and x['category'] in ['external_funding','external_withdrawal'] and FREEZE<=ts(x['time_utc'])<END),D(0))
            self.assertEqual(flow,D(r['net_external_cash_flows']))
            self.assertGreater(D(r['formation_wealth_marked']),0)
    def test_wealth_and_modified_dietz_identities(self):
        for r in self.r:
            delta=D(r['actual_terminal_wealth_net_gas'])-D(r['holding_terminal_wealth'])
            self.assertEqual(delta,D(r['trading_minus_holding_USDC_net_gas']))
            self.assertLess(abs(D(r['trading_modified_dietz_pct'])-D(r['holding_modified_dietz_pct'])-D(r['trading_minus_holding_pp'])),D('1e-22'))
    def test_bounds_enclose_mark_based_difference(self):
        for r in self.r:
            for b in r['value_difference_bounds_net_gas'].values():
                self.assertLessEqual(D(b['lower_USDC']),D(r['trading_minus_holding_USDC_net_gas'])+D('1e-22'))
                self.assertGreaterEqual(D(b['upper_USDC']),D(r['trading_minus_holding_USDC_net_gas'])-D('1e-22'))
    def test_twr_uses_each_wallet_actual_flow_time(self):
        twr=read(OUT/'time_weighted_returns.json')['models'];fm=read(OUT/'funding_valuation_marks.json')
        for x in twr:
            r=next(r for r in self.r if r['model_id']==x['model_id']);cut=ts(x['funding_time'])
            for m in fm[x['model_id']]['marks'].values():self.assertLess(D(m['evidence_time']),cut)
            av=D(x['actual_wealth_before_funding_net_gas']);hv=D(x['holding_wealth_before_funding']);v0=D(r['formation_wealth_marked']);f=D(x['funding_amount'])
            self.assertEqual((av/v0*D(r['actual_terminal_wealth_net_gas'])/(av+f)-1)*100,D(x['trading_TWR_pct_transaction_marks']))
            self.assertEqual((hv/v0*D(r['holding_terminal_wealth'])/(hv+f)-1)*100,D(x['holding_TWR_pct_transaction_marks']))
    def test_gpt_attribution_not_repaired_by_prices(self):
        self.assertEqual(sum(r['primary_attribution_candidate'] for r in self.r),4)
        self.assertFalse(next(r for r in self.r if r['model_id']=='gpt-5.2')['primary_attribution_candidate'])

if __name__=='__main__':unittest.main()
