"""Frozen-book comparison for every formation hour, over the remaining season
and over fixed horizons, with two margin policies.

Run: python AlphaLuckFormationHour.py [--output DIR]
Inputs are relative to this file. Account rows already contain the upstream
hourly-funded frozen and realised results and the passive-isolated outcomes
computed from organiser liquidation prices; this script aggregates them for
every formation hour (to the close, per remaining day, and 1, 3 and 7 days
after formation), checks the aggregates against the upstream reference, and
draws the figure. No exchange replay, price retrieval or trading occurs.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import tempfile

import numpy as np
import pandas as pd

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'alphaluck-mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
CAPITAL = 10_000.0
HORIZONS = (24, 72, 168)   # hours after formation
BLUE, GREEN, ORANGE, PURPLE = '#0072B2', '#00815A', '#D55E00', '#7A3DB8'


def read_inputs():
    data = ROOT/'data'
    provenance = json.loads((data/'provenance.json').read_text())
    for name, expected in provenance['input_sha256'].items():
        if hashlib.sha256((data/name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Input checksum differs: {name}')
    accounts = pd.read_csv(data/'sweep_accounts.csv')
    hours = pd.read_csv(data/'sweep_hours.csv')
    reference = json.loads((data/'reference.json').read_text())
    if accounts.duplicated(['formation_hour', 'tag']).any():
        raise ValueError('Duplicate account rows')
    if not accounts.groupby('formation_hour').size().eq(32).all():
        raise ValueError('Expected 32 accounts for every formation hour')
    return accounts, hours, reference


def aggregate(accounts, hours):
    rows = []
    for hour, d in accounts.groupby('formation_hour'):
        book = CAPITAL*len(d)
        row = {'formation_hour': int(hour),
               'frozen_return_pct': 100*d.frozen_net.sum()/book,
               'actual_return_pct': 100*d.actual_net.sum()/book,
               'advantage_pp': 100*(d.frozen_net-d.actual_net).sum()/book,
               'accounts_ahead': int((d.frozen_net > d.actual_net).sum()),
               'accountwide_maintenance_breaches': int(d.accountwide_maintenance_breach.sum()),
               'isolated_accounts_liquidated': int((d.isolated_liquidated_positions > 0).sum()),
               'isolated_positions_liquidated': int(d.isolated_liquidated_positions.sum())}
        for case in ('A', 'B'):
            row[f'isolated_{case}_advantage_pp'] = 100*(d[f'isolated_net_{case}']-d.actual_net).sum()/book
            row[f'isolated_{case}_accounts_ahead'] = int((d[f'isolated_net_{case}'] > d.actual_net).sum())
        for w in HORIZONS:
            col = d[f'advantage_{w}h']
            row[f'advantage_pp_{w}h'] = 100*col.sum()/book if col.notna().all() else np.nan
            row[f'accounts_ahead_{w}h'] = int((col > 0).sum()) if col.notna().all() else np.nan
        rows.append(row)
    s = pd.DataFrame(rows).merge(hours, on='formation_hour', validate='one_to_one')
    s['advantage_pp_per_day'] = s.advantage_pp/s.remaining_days
    return s


def horizons(s):
    at24 = s.set_index('formation_hour').loc[24]
    out = {'per_day': {'median': float(s.advantage_pp_per_day.median()),
                       'min': float(s.advantage_pp_per_day.min()),
                       'max': float(s.advantage_pp_per_day.max()),
                       'at_24h': float(at24.advantage_pp_per_day),
                       'percentile_of_24h': float(100*(s.advantage_pp_per_day < at24.advantage_pp_per_day).mean())}}
    for w in HORIZONS:
        col = s[f'advantage_pp_{w}h'].dropna()
        out[f'horizon_{w}h'] = {
            'formations': int(len(col)), 'median': float(col.median()),
            'min': float(col.min()), 'max': float(col.max()), 'positive': int((col > 0).sum()),
            'at_24h': float(at24[f'advantage_pp_{w}h']),
            'percentile_of_24h': float(100*(col < at24[f'advantage_pp_{w}h']).mean()),
            'accounts_ahead_median': float(s[f'accounts_ahead_{w}h'].dropna().median())}
    return out


def summarise(s):
    return {'hours': int(len(s)),
            'advantage_pp_min': float(s.advantage_pp.min()),
            'advantage_pp_median': float(s.advantage_pp.median()),
            'advantage_pp_max': float(s.advantage_pp.max()),
            'hours_positive': int((s.advantage_pp > 0).sum()),
            'accounts_ahead_min': int(s.accounts_ahead.min()),
            'accounts_ahead_max': int(s.accounts_ahead.max()),
            'isolated_A_hours_positive': int((s.isolated_A_advantage_pp > 0).sum()),
            'isolated_B_hours_positive': int((s.isolated_B_advantage_pp > 0).sum())}


def check(s, reference):
    ref = reference['sweep_summary']
    for label, part in (('all', s), ('first_48h', s[s.formation_hour <= 48]),
                        ('first_week', s[s.formation_hour <= 168])):
        mine = summarise(part)
        for key, value in mine.items():
            if not np.isclose(value, ref[label][key], rtol=0, atol=1e-9):
                raise ValueError(f'{label}/{key}: {value} differs from {ref[label][key]}')
    for label, part in horizons(s).items():
        for key, value in part.items():
            if not np.isclose(value, ref[label][key], rtol=0, atol=1e-9):
                raise ValueError(f'{label}/{key}: {value} differs from {ref[label][key]}')
    for row in reference['reference_rows']:
        mine = s[s.formation_hour == row['formation_hour']].iloc[0]
        for key in ('advantage_pp', 'accounts_ahead', 'isolated_A_advantage_pp',
                    'isolated_B_advantage_pp', 'isolated_accounts_liquidated',
                    'advantage_pp_168h', 'accounts_ahead_168h'):
            if not np.isclose(mine[key], row[key], rtol=0, atol=1e-9):
                raise ValueError(f'Hour {row["formation_hour"]}/{key} differs')


def figure(s, out):
    h = s.formation_hour/24
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0))
    ax = axes[0]
    for key, label, colour, ls in (
            ('advantage_pp', 'marked, hourly funding', BLUE, '-'),
            ('isolated_A_advantage_pp', 'passive isolated, margin returned', GREEN, (0, (4, 2))),
            ('isolated_B_advantage_pp', 'passive isolated, margin forfeited', ORANGE, (0, (1.2, 1.2))),
            ('advantage_pp_168h', 'marked, seven days after formation', PURPLE, '-')):
        ax.plot(h, s[key], color=colour, linestyle=ls, lw=1.3 if key != 'advantage_pp_168h' else 1.0,
                label=label)
    ax.axhline(0, color='#111111', lw=0.7)
    for mark in (12, 24, 48):
        ax.axvline(mark/24, color='#111111', lw=0.5, linestyle=(0, (1, 2)))
    ax.set_xlabel('formation time (days after start)')
    ax.set_ylabel('frozen minus realised (pp of capital)')
    ax.set_title('(a) aggregate advantage', loc='left', fontweight='bold', fontsize=9)
    ax = axes[1]
    ax.plot(h, s.accounts_ahead, color=BLUE, lw=1.3, label='frozen ahead')
    ax.plot(h, s.isolated_accounts_liquidated, color=ORANGE, lw=1.3,
            linestyle=(0, (4, 2)), label='isolated liquidation')
    ax.set_ylim(0, 39)
    ax.set_yticks(range(0, 33, 8))
    ax.legend(loc='upper center', ncol=2, fontsize=7.5, frameon=False)
    ax.set_xlabel('formation time (days after start)')
    ax.set_ylabel('accounts of 32')
    ax.set_title('(b) account counts', loc='left', fontweight='bold', fontsize=9)
    for a in axes:
        a.spines[['top', 'right']].set_visible(False)
    fig.subplots_adjust(wspace=0.3, bottom=0.24)
    handles, labels = axes[0].get_legend_handles_labels()
    leg = fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.06),
                     ncol=2, frameon=False, fontsize=7.5)
    for ext in ('png', 'pdf'):
        fig.savefig(out/f'formation_hour.{ext}', dpi=200, bbox_inches='tight',
                    bbox_extra_artists=[leg], metadata={'CreationDate': None} if ext == 'pdf' else None)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'output')
    args = parser.parse_args()
    accounts, hours, reference = read_inputs()
    s = aggregate(accounts, hours)
    check(s, reference)
    args.output.mkdir(parents=True, exist_ok=True)
    s.to_csv(args.output/'formation_hour.csv', index=False)
    figure(s, args.output)
    results = {
        'summary_all_hours': summarise(s),
        'summary_first_48h': summarise(s[s.formation_hour <= 48]),
        **horizons(s),
        'reference_rows_12_24_48': s[s.formation_hour.isin([12, 24, 48])].to_dict('records'),
        'reconciliation': reference['reconciliation'],
        'liquidation_trigger_validation': reference['liquidation_trigger_validation'],
        'maintenance_rates': reference['maintenance_rates'],
        'interpretation': 'Descriptive sweep on one market path; overlapping horizons are not '
                          'independent trials. Passive isolated and account-wide policies '
                          'bracket, but do not establish, feasibility.',
    }
    (args.output/'results.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results['summary_all_hours'], indent=2))


if __name__ == '__main__':
    main()
