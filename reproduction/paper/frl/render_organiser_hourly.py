"""Render organiser-hourly macros and the appendix table for the letter.

Run after src/organiser_hourly.py, src/organiser_conversations.py and
src/exposure_mechanics.py:
    python paper/frl/render_organiser_hourly.py
Writes paper/frl/organiser_numbers.tex, organiser_table.tex,
organiser_horizon_table.tex and exposure_table.tex.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DER = HERE.parents[1] / 'data' / 'derived'


def f(x, d=2):
    return f'{x:,.{d}f}'.replace(',', '{,}')


def main():
    r = json.loads((DER / 'organiser_hourly.json').read_text())
    c = json.loads((DER / 'conversations_6dec.json').read_text())
    xm = json.loads((DER / 'exposure_mechanics.json').read_text())
    published = json.loads((DER / 'i6_vol_denominator.json').read_text())
    for k in ('leverage_equity', 'leverage_fixed'):   # same p as the letter's Table 2
        xm[k]['assoc_p_two_sided'] = published[k]['assoc_p_two_sided']
    rec, cov = r['reconciliation'], r['coverage']
    ins = rec['equity']['in_season']
    sw = r['sweep_summary']
    prim = {row['formation_hour']: row for row in r['sweep_primary']}
    p24 = prim[24]
    b = {x['label']: x for x in r['boundaries']}
    trig, fit = r['liquidation_trigger_validation'], r['isolated_margin_fit']
    ls = r['liquidation_stress']
    st = {x['scenario']: x for x in ls['at_24h']}
    joint = [st['joint, earlier trigger'], st['joint, later trigger']]
    wk = min((ls['joint_earlier_all_hours'], ls['joint_later_all_hours']),
             key=lambda x: x['B_168h_median'])
    close_rel = max(abs(v['relative_pct']) for v in b['close']['prices_within_15min'].values())
    macros = {
        'OrgSnapshots': f(cov['snapshots'], 0), 'OrgPossible': f(cov['possible'], 0),
        'OrgMarkerTwentyFour': str(cov['marker_24_accounts']),
        'OrgOffsetMedian': f(cov['snapshot_offset_from_nominal_hour_minutes']['0.5'], 0),
        'OrgPosCells': f(rec['position_cells_held'], 0),
        'OrgPosExact': f(rec['position_cells_exact'], 0),
        'OrgSeasonSnapshots': f(ins['snapshots'], 0),
        'OrgEqMedPool': f(ins['pooled']['abs_pct']['0.5'], 3),
        'OrgEqMedOrg': f(ins['organiser_prices']['abs_pct']['0.5'], 3),
        'OrgEqNinetyNineOrg': f(ins['organiser_prices']['abs_pct']['0.99'], 2),
        'OrgEqShareOne': f(100 * ins['organiser_prices']['share_within_1pct'], 1),
        'OrgEqMaxOrg': f(ins['organiser_prices']['abs_pct']['1.0'], 2),
        'OrgEqMaxLater': f(rec['equity']['in_season_after_marker0_organiser_prices_abs_pct']['1.0'], 2),
        'OrgFreezeWithin': str(b['freeze_24h']['accounts_with_snapshot_within_15min']),
        'OrgFreezeFills': str(b['freeze_24h']['accounts_with_fills_between_snapshot_and_boundary']),
        'OrgFreezeCells': str(b['freeze_24h']['nearest_position_cells']),
        'OrgCloseMinutes': f(b['close']['nearest_minutes_abs_max'], 1),
        'OrgCloseCells': str(b['close']['nearest_position_cells']),
        'OrgClosePriceMax': f(close_rel, 2),
        'OrgCloseAdv': f(p24['advantage_pp_organiser_close_prices'], 1),
        'OrgSweepHours': str(sw['all']['hours']),
        'OrgSweepPositive': str(sw['all']['hours_positive']),
        'OrgSweepMin': f(sw['all']['advantage_pp_min'], 1),
        'OrgSweepMinDay': f(sw['all']['hour_at_min'] / 24, 1),
        'OrgSweepMax': f(sw['all']['advantage_pp_max'], 1),
        'OrgSweepMedian': f(sw['all']['advantage_pp_median'], 1),
        'OrgSweepAheadMin': str(sw['all']['accounts_ahead_min']),
        'OrgSweepAheadMax': str(sw['all']['accounts_ahead_max']),
        'OrgSweepFirstMin': f(sw['first_48h']['advantage_pp_min'], 1),
        'OrgSweepBreakMedian': f(sw['all']['endpoint_break_even_pct_median'], 2),
        'OrgSweepIsoBPositive': str(sw['all']['isolated_B_hours_positive']),
        'OrgSweepIsoAPositive': str(sw['all']['isolated_A_hours_positive']),
        'OrgLiqEvents': str(trig['events_in_season']),
        'OrgLiqAccounts': str(trig['accounts_in_season']),
        'OrgLiqUnchanged': str(trig['events_with_unchanged_position']),
        'OrgLiqMarkGap': f(trig['mark_minus_threshold_abs_pct_max_unchanged'], 2),
        'OrgLiqPrintsCrossed': str(trig['pooled_prints_crossed_unchanged']),
        'OrgLiqIntervals': f(trig['fill_free_same_quantity_intervals'], 0),
        'OrgLiqFalse': str(trig['print_crossings_without_fill']),
        'OrgFitRows': f(fit['rows'], 0),
        'OrgFitMedian': f(fit['abs_pct_error_all']['0.5'], 3),
        'OrgFitNinetyNine': f(fit['abs_pct_error_all']['0.99'], 2),
        'OrgIsoAccounts': str(p24['isolated_accounts_liquidated']),
        'OrgIsoPositions': str(p24['isolated_positions_liquidated']),
        'OrgIsoUnscreened': str(p24['isolated_positions_unscreened']),
        'OrgIsoAdvA': f(p24['isolated_A_advantage_pp'], 1),
        'OrgIsoAdvB': f(p24['isolated_B_advantage_pp'], 1),
        # frozen-book return under each isolated-margin convention
        'OrgIsoHoldA': f(p24['actual_return_pct'] + p24['isolated_A_advantage_pp'], 1),
        'OrgIsoHoldB': f(p24['actual_return_pct'] + p24['isolated_B_advantage_pp'], 1),
        'OrgIsoAheadA': str(p24['isolated_A_accounts_ahead']),
        'OrgIsoAheadB': str(p24['isolated_B_accounts_ahead']),
        # bridge: shared-collateral advantage minus the liquidation effect
        'OrgLiqSlipMedian': f(trig['fill_beyond_threshold_pct']['0.5'], 2),
        'OrgLiqSlipMax': f(trig['fill_beyond_threshold_pct']['1.0'], 1),
        'OrgLiqEffectA': f(p24['advantage_pp'] - p24['isolated_A_advantage_pp'], 1),
        'OrgLiqEffectB': f(p24['advantage_pp'] - p24['isolated_B_advantage_pp'], 1),
        **{f'OrgStressJoint{c}': f(min(x[f'advantage_pp_{c}'] for x in joint), 1) for c in 'AB'},
        **{f'OrgStressJointAhead{c}': str(min(x[f'accounts_ahead_{c}'] for x in joint)) for c in 'AB'},
        'OrgStressSlipB': f(st['slippage 1.3%']['advantage_pp_B'], 1),
        **{f'OrgStressWeek{c}Median': f(wk[f'{c}_168h_median'], 1) for c in 'AB'},
        **{f'OrgStressWeek{c}Positive': str(wk[f'{c}_168h_positive']) for c in 'AB'},
        'OrgStressWeekHours': str(wk['formations_168h']),
        **{f'ExpAfter{o}{b}{k}': f(xm[f'leverage_{bb}_day1__after_day1_{oo}'][kk], n)
           for o, oo in (('Fix', 'fixed'), ('Eq', 'equity'))
           for b, bb in (('Fix', 'fixed'), ('Eq', 'equity'))
           for k, kk, n in (('Rho', 'assoc_rho', 2), ('ProfP', 'profile_p', 3))},
        'OrgAccountwideBreaches': str(p24['accountwide_maintenance_breaches']),
        'OrgSweepPctTwentyFour': f(sw['all']['percentile_of_24h'], 0),
        'OrgPerDayMedian': f(sw['per_day']['median'], 2),
        'OrgPerDayTwentyFour': f(sw['per_day']['at_24h'], 2),
        'OrgFirstTwoDaysMedian': f(sw['first_48h']['advantage_pp_median'], 1),
        **{f'OrgH{name}{k}': v for w, name in ((24, 'Day'), (72, 'Three'), (168, 'Week'))
           for k, v in (('Formations', str(sw[f'horizon_{w}h']['formations'])),
                        ('Positive', str(sw[f'horizon_{w}h']['positive'])),
                        ('Median', f(sw[f'horizon_{w}h']['median'], 1)),
                        ('Min', f(sw[f'horizon_{w}h']['min'], 1)),
                        ('Max', f(sw[f'horizon_{w}h']['max'], 1)),
                        ('TwentyFour', f(sw[f'horizon_{w}h']['at_24h'], 1)),
                        ('Pct', f(sw[f'horizon_{w}h']['percentile_of_24h'], 0)),
                        *((f'Iso{c}Median', f(sw[f'horizon_{w}h'][f'isolated_{c}_median'], 1))
                          for c in 'AB'),
                        *((f'Iso{c}Positive', str(sw[f'horizon_{w}h'][f'isolated_{c}_positive']))
                          for c in 'AB'),
                        *((f'Iso{c}TwentyFour', f(sw[f'horizon_{w}h'][f'isolated_{c}_at_24h'], 1))
                          for c in 'AB'))},
        'ExpWealthRho': f(xm['wealth_factor']['assoc_rho'], 2),
        'ExpPrevRho': f(xm['leverage_prev_dayend']['assoc_rho'], 2),
        'ExpDayOneEqRho': f(xm['leverage_equity_day1']['assoc_rho'], 2),
        'ExpDayOneEqP': f(xm['leverage_equity_day1']['assoc_p_two_sided'], 3),
        'ExpDayOneFixRho': f(xm['leverage_fixed_day1']['assoc_rho'], 2),
        'ExpDayOneFixP': f(xm['leverage_fixed_day1']['assoc_p_two_sided'], 3),
        'ExpDayOneEqProfP': f(xm['leverage_equity_day1']['profile_p'], 3),
        'ExpDayOneFixProfP': f(xm['leverage_fixed_day1']['profile_p'], 3),
        'ConvRecords': str(c['records']), 'ConvDecisions': str(c['instrument_decisions']),
        'ConvHold': str(c['signals'].get('hold', 0)),
        'ConvHoldShare': f(100 * c['hold_share'], 0),
        'ConvInterval': f(c['decision_interval_minutes']['median'], 1),
    }
    lines = ['% Generated by render_organiser_hourly.py']
    lines += [f'\\newcommand{{\\al{k}}}{{{v.replace("-", "\\ensuremath{-}", 1) if v.startswith("-") else v}}}'
              for k, v in macros.items()]
    (HERE / 'organiser_numbers.tex').write_text('\n'.join(lines) + '\n')

    rows = []
    for h in (12, 24, 48):
        x = prim[h]
        rows.append(f"{h} & ${f(x['advantage_pp'])}$ & {x['accounts_ahead']}/32 & "
                    f"${f(x['advantage_pp_organiser_close_prices'])}$ & "
                    f"{x['accountwide_maintenance_breaches']} & "
                    f"{x['isolated_accounts_liquidated']} ({x['isolated_positions_liquidated']}) & "
                    f"${f(x['isolated_A_advantage_pp'])}$ & ${f(x['isolated_B_advantage_pp'])}$ \\\\")
    a = sw['all']
    rows.append(f"1--{a['hours']} & ${f(a['advantage_pp_min'], 1)}$ to ${f(a['advantage_pp_max'], 1)}$ & "
                f"{a['accounts_ahead_min']}--{a['accounts_ahead_max']} & & & & "
                f"{a['isolated_A_hours_positive']}/{a['hours']} $>0$ & "
                f"{a['isolated_B_hours_positive']}/{a['hours']} $>0$ \\\\")
    table = r"""\begin{table}[ht]
\centering\small
\caption{Frozen-book comparison by formation hour with organiser margin data,
Season~1.5. Advantages are percentage points of initial capital, frozen minus
realised, with hourly funding. ``Organiser close'' revalues both terminal
books at the organiser's prices within 15 minutes of the close. Account-wide
counts accounts whose frozen equity falls below summed asset maintenance
margins on the five-minute grid. Passive isolated keeps each position's
formation isolated margin, uses the organiser's liquidation price for the
same position and triggers on pooled trade prints; liquidation returns (A)
or forfeits (B) the remaining maintenance margin. Neither convention is an
exchange replay. The last row summarises all formation hours.}
\label{tab:orghourly}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{rrrrrrrr}
\toprule
 & \multicolumn{2}{c}{Marked} & Organiser & Account- & Isolated & \multicolumn{2}{c}{Isolated advantage} \\
Hour & Adv. & Ahead & close & wide & accts (pos.) & A & B \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
"""
    (HERE / 'organiser_table.tex').write_text(table)

    rows = []
    for w, label in ((24, 'One day'), (72, 'Three days'), (168, 'Seven days')):
        h = sw[f'horizon_{w}h']
        rows.append(f"{label} & {h['formations']} & {h['positive']} & ${f(h['median'], 1)}$ & "
                    f"${f(h['min'], 1)}$ & ${f(h['max'], 1)}$ & ${f(h['at_24h'], 1)}$ & "
                    f"{f(h['percentile_of_24h'], 0)} \\\\")
    pd_ = sw['per_day']
    rows.append(f"To the close, per remaining day & {sw['all']['hours']} & {sw['all']['hours_positive']} & "
                f"${f(pd_['median'], 2)}$ & ${f(pd_['min'], 2)}$ & ${f(pd_['max'], 2)}$ & "
                f"${f(pd_['at_24h'], 2)}$ & {f(pd_['percentile_of_24h'], 0)} \\\\")
    rows.append(r"\midrule")
    rows.append(r"\multicolumn{8}{l}{\emph{Passive isolated margin, remaining margin returned (A) or forfeited (B)}} \\")
    for w, label in ((24, 'One day'), (72, 'Three days'), (168, 'Seven days')):
        h = sw[f'horizon_{w}h']
        for c in 'AB':
            rows.append(f"{label}, {c} & {h['formations']} & {h[f'isolated_{c}_positive']} & "
                        f"${f(h[f'isolated_{c}_median'], 1)}$ & & & "
                        f"${f(h[f'isolated_{c}_at_24h'], 1)}$ & \\\\")
    (HERE / 'organiser_horizon_table.tex').write_text(r"""\begin{table}[ht]
\centering\small
\caption{Frozen minus realised over a fixed horizon after each formation hour,
Season~1.5, percentage points of initial capital with hourly funding at
pooled trade prices. Each row uses the formation hours whose horizon ends by
the close; the last row divides the advantage to the close by the remaining
days. The 24-hour columns give the value for the letter's formation hour and
the share of formation hours with a smaller value. In the lower panel a
frozen position liquidated before the horizon contributes its liquidation
result there.}
\label{tab:orghorizon}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{lrrrrrrr}
\toprule
Horizon & Hours & $>0$ & Median & Min & Max & 24\,h & Pctile \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")

    labels = (('leverage_equity', 'Whole window, current equity'),
              ('leverage_fixed', 'Whole window, initial capital'),
              ('leverage_prev_dayend', 'Whole window, previous date-end equity'),
              ('wealth_factor', 'Wealth factor $C/E_t$ alone'),
              ('leverage_equity_day1', 'First 24 hours, current equity'),
              ('leverage_fixed_day1', 'First 24 hours, initial capital'))
    pval = lambda v: '$<0.001$' if v < 0.001 else f(v, 3)
    rows = [f"{lab} & ${f(xm[k]['assoc_rho'], 2)}$ & {pval(xm[k]['assoc_p_two_sided'])} & "
            f"{pval(xm[k]['profile_p'])} \\\\" for k, lab in labels]
    rows.append(r"\multicolumn{4}{l}{\emph{First 24 hours against the return after the first day}} \\")
    for k, lab in (('leverage_equity_day1__after_day1_fixed', 'Current equity; $(E_T-E_{24})/C$'),
                   ('leverage_fixed_day1__after_day1_fixed', 'Initial capital; $(E_T-E_{24})/C$'),
                   ('leverage_equity_day1__after_day1_equity', 'Current equity; $E_T/E_{24}-1$'),
                   ('leverage_fixed_day1__after_day1_equity', 'Initial capital; $E_T/E_{24}-1$')):
        rows.append(f"{lab} & ${f(xm[k]['assoc_rho'], 2)}$ & {pval(xm[k]['assoc_p_two_sided'])} & "
                    f"{pval(xm[k]['profile_p'])} \\\\")
    (HERE / 'exposure_table.tex').write_text(r"""\begin{table}[ht]
\centering\small
\caption{Gross exposure and the final return, Season~1.5: mean within-arm
Spearman correlation, two-sided permutation $p$ over accounts within arm
(20{,}000 draws) and the exact profile test that re-pairs the eight models'
four-arm profiles (40{,}320 permutations). Exposure on current equity
factors as exposure on initial capital times $C/E_t$, which rises with
losses.}
\label{tab:expmech}
\begin{tabular}{lrrr}
\toprule
Gross exposure measure & $\rho$ & $p$ & Profile $p$ \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")
    rows = []
    for x in ls['at_24h']:
        name = (x['scenario'][0].upper() + x['scenario'][1:]).replace('%', r'\%')
        rows.append(f"{name} & {x['isolated_positions_liquidated']} & "
                    f"${f(x['advantage_pp_A'], 1)}$ & {x['accounts_ahead_A']} & "
                    f"${f(x['advantage_pp_B'], 1)}$ & {x['accounts_ahead_B']} & "
                    f"${f(x['advantage_pp_168h_A'], 1)}$ & ${f(x['advantage_pp_168h_B'], 1)}$ \\\\")
    rows.append(r"\midrule")
    rows.append(r"All formation hours, seven days & & \multicolumn{2}{c}{A: median, $>0$} & "
                r"\multicolumn{2}{c}{B: median, $>0$} & & \\")
    rows.append(r"\midrule")
    for label, key in (('Joint, earlier', 'joint_earlier_all_hours'),
                       ('Joint, later', 'joint_later_all_hours')):
        y = ls[key]
        rows.append(f"{label} trigger & & ${f(y['A_168h_median'], 1)}$ & "
                    f"{y['A_168h_positive']}/{y['formations_168h']} & ${f(y['B_168h_median'], 1)}$ & "
                    f"{y['B_168h_positive']}/{y['formations_168h']} & & \\\\")
    (HERE / 'organiser_stress_table.tex').write_text(r"""\begin{table}[ht]
\centering\small
\caption{Liquidation stress under passive isolated margin, Season~1.5,
formation at 24 hours: advantage in percentage points of initial capital and
accounts ahead of 32, to the close and over seven days. The trigger moves 1\%
of price towards (earlier) or away from (later) the formation price;
slippage executes the liquidation beyond the trigger, 1.3\% being the
largest gap between an actual liquidation fill and the organiser threshold
in the archive; the charge is levied on the liquidated notional, above the
largest recorded fee rate; the two unscreened positions are closed at their
worst grid mark. The joint rows combine 1\% trigger shift, 1.3\% slippage,
a 10\,bp charge and worst marks. The last two rows give the median
seven-day advantage and the number of formation hours with holding ahead,
of all formation hours.}
\label{tab:stress}
\setlength{\tabcolsep}{3.5pt}
\begin{tabular}{lrrrrrrr}
\toprule
 & Liq. & \multicolumn{2}{c}{A to close} & \multicolumn{2}{c}{B to close} & \multicolumn{2}{c}{Seven days} \\
Scenario & pos. & Adv. & Ahead & Adv. & Ahead & A & B \\
\midrule
""" + '\n'.join(rows) + r"""
\bottomrule
\end{tabular}
\end{table}
""")
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
