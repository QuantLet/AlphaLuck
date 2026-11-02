"""Formation-threshold timing audit using the saved, derived snapshot cells.

Offline: python src/formation_timing_audit.py. No raw snapshot archive needed.
The prior-only scenarios do not assume that missing thresholds are observed.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import organiser_hourly as oh

ROOT = Path(__file__).resolve().parents[1]

def main():
    der = ROOT / 'data/derived'
    m = oh.Market(ROOT)
    cells = pd.read_csv(der / 'organiser_hourly/position_cells.csv')
    rates = json.loads((der / 'organiser_hourly.json').read_text())['maintenance_rates']
    nearest = oh.Sweep(m, cells, rates)
    prior = oh.Sweep(m, cells, rates, threshold_policy='prior')
    legacy = oh.Sweep(m, cells, rates, align_funding=False)
    details, results = [], []
    for hour in (12, 24, 48):
        t0 = m.lo + hour * oh.fh.HOUR
        i = np.searchsorted(nearest.grid, t0)
        for (tag, coin), quantities in nearest.q.items():
            q = quantities[i]
            if q == 0:
                continue
            n = nearest.threshold(tag, coin, q, t0)
            p = prior.threshold(tag, coin, q, t0)
            details.append({'formation_hour': hour, 'tag': tag, 'coin': coin,
                            'quantity': q, 'nearest_minutes': None if n is None else (n[0]-t0)/60000,
                            'nearest_L_at_formation': None if n is None else n[1],
                            'prior_minutes': None if p is None else (p[0]-t0)/60000,
                            'prior_L_at_formation': None if p is None else p[1]})
        scenarios = [
            ('Nearest, unaligned funding (previous version)', legacy, None),
            ('Nearest, funding aligned', nearest, None),
            ('Prior only, missing marked', prior, None),
            ('Prior only, missing at worst observed value', prior, {'worst_unscreened': True}),
            ('Prior only, joint earlier-trigger stress', prior, {**oh.HARSH, 'buffer': .01}),
            ('Prior only, joint later-trigger stress', prior, oh.HARSH),
        ]
        for label, sweep, stress in scenarios:
            _, row = sweep.run(hour, stress=stress)
            results.append({'scenario': label, **row})
    detail = pd.DataFrame(details)
    detail.to_csv(der / 'formation_timing_positions.csv', index=False)
    report = {'assumption': 'Thresholds are estimates conditional on unchanged isolated collateral between snapshot and formation; quantities alone cannot establish that assumption.',
              'missing_threshold_stress': 'Minimum observed post-formation P&L of each missing-threshold position; sensitivity scenario, not an executable strategy or a formal lower bound.',
              'results': results, 'coverage': []}
    for hour, g in detail.groupby('formation_hour'):
        report['coverage'].append({'formation_hour': int(hour), 'open_positions': len(g),
            'nearest_after_formation': int(g.nearest_minutes.gt(0).sum()),
            'nearest_before_or_at_formation': int(g.nearest_minutes.le(0).sum()),
            'nearest_missing': int(g.nearest_minutes.isna().sum()),
            'prior_missing': int(g.prior_minutes.isna().sum()),
            'prior_max_age_minutes': float(-g.prior_minutes.min())})
    (der / 'formation_timing_audit.json').write_text(json.dumps(report, indent=2, allow_nan=False))
    rows = [r for r in results if r['formation_hour']==24]
    tex = [r'\begin{table}[ht]', r'\centering\small',
        r'\caption{Threshold timing at formation after 24 hours. Gaps are holding minus trading, in percentage points of initial capital. Missing counts positions without an eligible threshold. All revised scenarios align funding with formation. Prior-only scenarios assume no unobserved margin transfers after the preceding snapshot. Worst observed values and joint stresses are sensitivity calculations, not formal bounds.}',
        r'\label{tab:thresholdtiming}', r'\begin{tabular}{lrrrrr}', r'\toprule',
        r'Scenario & Missing & Gap A & Gap B & Ahead A & Ahead B \\', r'\midrule']
    names=['Previous calculation','Nearest, funding aligned','Prior, missing marked','Prior, missing at worst value','Prior, joint earlier trigger','Prior, joint later trigger']
    for name, r in zip(names,rows):
        tex.append(f"{name} & {r['isolated_positions_unscreened']} & {r['isolated_A_advantage_pp']:.2f} & {r['isolated_B_advantage_pp']:.2f} & {r['isolated_A_accounts_ahead']} & {r['isolated_B_accounts_ahead']}"+r' \\')
    tex += [r'\bottomrule',r'\end{tabular}',r'\end{table}']
    (ROOT/'paper/frl/formation_timing_table.tex').write_text('\n'.join(tex)+'\n')
    print(json.dumps({'coverage':report['coverage'],'at_24h':[{k:r[k] for k in ['scenario','isolated_A_advantage_pp','isolated_B_advantage_pp']} for r in rows]},indent=2))

if __name__ == '__main__':
    main()
