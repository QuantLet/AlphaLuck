import unittest
from analyze_history import *

class HistoryTests(unittest.TestCase):
    def read(self,name):return json.loads((OUT/name).read_text())
    def test_archive_coverage(self):
        d=self.read('history_summary.json');self.assertEqual(len(d['archive_complete_files']),13)
        self.assertTrue(all(d['archive_complete_files'].values()))
    def test_exact_order_linkage(self):
        o=self.read('order_linkage.json');self.assertEqual(len(o),473)
        self.assertEqual(sum(x['wallet_token_side_match'] for x in o),468)
        for x in o:
            if x['wallet_token_side_match']:self.assertTrue(x['unique_internal_link'])
    def test_position_transfers_exhaustive(self):
        p=self.read('positions_reconciliation.json')
        self.assertEqual(sum(x['position_transfer_rows_before_endpoint'] for x in p),506)
        self.assertEqual(sum(x['trade_transaction_groups'] for x in p),474)
        self.assertEqual(sum(x['redemption_transaction_groups'] for x in p),32)
        self.assertTrue(all(x['position_ledger_reconciled'] for x in p))
    def test_cash_reconciles(self):
        c=self.read('cash_reconciliation.json')
        self.assertEqual(sum(x['transaction_contract_groups'] for x in c),536)
        for x in c:
            self.assertEqual(x['unresolved_groups'],0)
            self.assertEqual(x['negative_partial_balance_transactions'],0)
            self.assertEqual(x['cross_source_cash_mismatches'],0)
    def test_zero_payout_is_not_income(self):
        r=self.read('redemptions_crosschecked.json')
        self.assertEqual(len(r),202);self.assertEqual(sum(int(x['payout'])>0 for x in r),21)
        self.assertEqual(sum(int(x['payout']) for x in r),284782866)
    def test_gas_charged_only_to_sender_and_once(self):
        a=self.read('network_fees.json');keys=[(x['model_id'],x['Transaction Hash'].lower()) for x in a]
        self.assertEqual(len(keys),len(set(keys)))
        for x in a:self.assertEqual(x['paid_by_wallet'],x['From'].lower()==WALLETS[x['model_id']])
    def test_rounding_refund_units(self):
        self.assertEqual(display_number('0.0₅1'),D('.000001'))
        self.assertEqual(display_number('1,000.000001'),D('1000.000001'))
        l=self.read('cash_ledger.json');self.assertTrue(any(x['observed_rounding_refund_raw']==1 for x in l))
    def test_no_future_settlement_values(self):
        f=self.read('replication_feasibility.json')
        for x in f['resolved_token_values_with_pre_endpoint_evidence'].values():
            self.assertLess(x['resolution_known_no_later_than'],timestamp(END))
            self.assertTrue(0<=D(x['value'])<=1)
    def test_attribution_not_assumed(self):
        f=self.read('replication_feasibility.json')['models']
        g=next(x for x in f if x['model_id']=='gpt-5.2')
        self.assertEqual(g['unlinked_orders_before_formation'],5)
        self.assertEqual(g['unlinked_orders_after_formation'],1)
        self.assertFalse(g['attribution_candidate_for_primary_replication'])
    def test_bounds_are_not_point_returns(self):
        f=self.read('replication_feasibility.json')['models']
        for x in f:
            b=x['trading_minus_holding_value_bounds_before_POL_gas']
            self.assertLessEqual(D(b['lower_USD_at_stablecoin_parity']),D(b['upper_USD_at_stablecoin_parity']))
            self.assertIsNone(x['trading_return']);self.assertIsNone(x['holding_return'])

if __name__=='__main__':unittest.main()
