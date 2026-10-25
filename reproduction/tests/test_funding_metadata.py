"""Preserve daily-aggregate provenance without altering baseline cash booking."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build


class FundingMetadataTest(unittest.TestCase):
    def test_aggregate_interval_and_hourly_event_are_distinct(self):
        start = 1_763_596_800_000
        account = {'season': 'S15', 'competition_id': 1, 'model': 'test'}
        daily = {'time': start, 'delta': {
            'coin': 'xyz:TEST', 'usdc': '-2.0', 'szi': '3.5',
            'fundingRate': '0.0001', 'nSamples': 24}}
        hourly = {'time': start + 3_600_017, 'delta': {
            'coin': 'xyz:TEST', 'usdc': '0.25', 'szi': '-1.0',
            'fundingRate': '0.0002', 'nSamples': None}}
        with patch.object(build.wallets, 'registry', return_value=[account]), \
             patch.object(build.wallets, 'tag', return_value='test-account'), \
             patch.object(build, '_rows', return_value=[daily, hourly, daily]):
            frame = build.load_funding()
        self.assertEqual(len(frame), 2)  # inclusive-page duplicate retained once
        first, second = frame.iloc[0], frame.iloc[1]
        self.assertEqual(first['szi'], 3.5)
        self.assertEqual(first['n_samples'], 24)
        self.assertEqual(first['aggregation_start_ms'], start)
        self.assertEqual(first['aggregation_end_ms'], start + 86_400_000)
        self.assertTrue(pd.isna(second['n_samples']))
        self.assertTrue(pd.isna(second['aggregation_start_ms']))
        self.assertTrue(pd.isna(second['aggregation_end_ms']))
        self.assertEqual(frame['time'].tolist(), [start, start + 3_600_017])
        self.assertEqual(frame['usdc'].tolist(), [-2.0, 0.25])


if __name__ == '__main__':
    unittest.main()
