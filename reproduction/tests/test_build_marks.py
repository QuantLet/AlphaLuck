"""Pooled marks must not depend on input row order or sorting implementation."""
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build

class StablePooledMarks(unittest.TestCase):
    def test_same_millisecond_marks_are_shuffle_invariant(self):
        fills = pd.DataFrame([
            {'coin': 'A', 'time': 1000, 'tid': 10, 'px': 100.0},
            {'coin': 'A', 'time': 1000, 'tid': 11, 'px': 102.0},
            {'coin': 'A', 'time': 1000, 'tid': 11, 'px': 103.0},
            {'coin': 'A', 'time': 1000, 'tid': 11, 'px': 103.0},
            {'coin': 'A', 'time': 2000, 'tid': 12, 'px': 99.0},
            {'coin': 'B', 'time': 1500, 'tid': 20, 'px': 50.0},
        ])
        grid = np.array([500, 1000, 1500, 2000, 2500])
        expected = pd.DataFrame({'A': [np.nan,103,103,99,99],
                                 'B': [np.nan,np.nan,50,50,50]}, index=grid)
        for seed in range(12):
            pd.testing.assert_frame_equal(build.price_series(fills.sample(frac=1,random_state=seed), grid),expected)

    def test_no_future_print_and_duplicate_prints_do_not_change_marks(self):
        fills = pd.DataFrame({'coin':['A','A'], 'time':[1000,2000],
                              'tid':[5,6], 'px':[80.0,90.0]})
        grid = np.array([999,1000,1999,2000])
        result = build.price_series(fills,grid)
        np.testing.assert_allclose(result.A,[np.nan,80,80,90],equal_nan=True)
        pd.testing.assert_frame_equal(result,build.price_series(pd.concat([fills,fills]),grid))

if __name__ == '__main__':
    unittest.main()
