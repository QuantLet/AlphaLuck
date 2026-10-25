"""Export the inputs of the AlphaLuckFormationHour Quantlet.

Run after src/organiser_hourly.py:
    python src/export_formation_quantlet.py
Writes quantlets/AlphaLuckFormationHour/data/{sweep_accounts.csv,
sweep_hours.csv, reference.json, provenance.json}. Organiser values are not
exported: account rows carry only derived frozen and realised results, flags
and counts. Fails if columns already published change value.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DER = ROOT / 'data' / 'derived'
OUT = ROOT / 'quantlets' / 'AlphaLuckFormationHour' / 'data'
HORIZONS = (24, 72, 168)
ACCOUNT_COLUMNS = ['formation_hour', 'tag', 'frozen_net', 'actual_net', 'positions_open',
                   'min_equity_to_gross', 'accountwide_maintenance_breach',
                   'isolated_liquidated_positions', 'isolated_unscreened_positions',
                   'isolated_net_A', 'isolated_net_B'] + [f'advantage_{w}h' for w in HORIZONS]
HOUR_COLUMNS = ['formation_hour', 'remaining_days', 'endpoint_common_break_even_pct',
                'advantage_pp_organiser_close_prices']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = json.loads((DER / 'organiser_hourly.json').read_text())
    accounts = pd.read_csv(DER / 'organiser_hourly_sweep_accounts.csv')[ACCOUNT_COLUMNS]
    hours = pd.read_csv(DER / 'organiser_hourly_sweep.csv')[HOUR_COLUMNS]

    old = pd.read_csv(OUT / 'sweep_accounts.csv')
    joined = old.merge(accounts, on=['formation_hour', 'tag'], suffixes=('_old', ''),
                       validate='one_to_one')
    if len(joined) != len(old) or len(old) != len(accounts):
        raise ValueError('Account rows differ from the published Quantlet')
    for col in old.columns.drop(['formation_hour', 'tag']):
        a, b = joined[f'{col}_old'], joined[col]
        same = (np.isclose(a, b, rtol=0, atol=1e-6, equal_nan=True) if a.dtype.kind == 'f'
                else a.astype(str).eq(b.astype(str)))
        if not np.all(same):
            raise ValueError(f'Published column changed: {col}')

    accounts.to_csv(OUT / 'sweep_accounts.csv', index=False)
    hours.to_csv(OUT / 'sweep_hours.csv', index=False)
    reference = json.loads((OUT / 'reference.json').read_text())
    reference['sweep_summary'] = report['sweep_summary']
    rows = pd.DataFrame(report['sweep_primary'])
    keep = ['formation_hour', 'advantage_pp', 'accounts_ahead', 'isolated_A_advantage_pp',
            'isolated_B_advantage_pp', 'isolated_accounts_liquidated'] + \
           [f'advantage_pp_{w}h' for w in HORIZONS] + [f'accounts_ahead_{w}h' for w in HORIZONS]
    reference['reference_rows'] = json.loads(rows[keep].to_json(orient='records'))
    (OUT / 'reference.json').write_text(json.dumps(reference, indent=2) + '\n')

    provenance = json.loads((OUT / 'provenance.json').read_text())
    provenance['input_sha256'] = {name: sha(OUT / name) for name in
                                  ('sweep_accounts.csv', 'sweep_hours.csv', 'reference.json')}
    (OUT / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps(provenance['input_sha256'], indent=2))


if __name__ == '__main__':
    main()
