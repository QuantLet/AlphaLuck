"""Offline cost, benchmark and sensitivity checks. No source data are changed.
Run with the AlphaLuck checkout as --root; outputs go beside this script.
"""
from pathlib import Path
import argparse, json, sys, hashlib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ap = argparse.ArgumentParser()
ap.add_argument('--root', type=Path, required=True)
args = ap.parse_args()
root = args.root.resolve()
out = root/'data/derived/additional_checks'
out.mkdir(parents=True, exist_ok=True)
der = root/'data/derived'
dest = out/'analysis'
dest.mkdir(exist_ok=True)
frl = out/'paper/frl'
frl.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root/'src'))
import organiser_hourly as oh
import funding_hourly_sensitivity as fh

def table(df, name, caption, label, fmt=None):
    df.to_csv(dest/(name+'.csv'), index=False)
    short={'Fees / capital (%)':'Fees (\\%)','Turnover (times)':'Turnover (x)',
           'Fee hurdle (bp)':'Fee (bp)','Net return (%)':'Return (\\%)',
           'Before-cost gap (pp)':'Gross gap','Fees retained (pp)':'Fees',
           'Funding gap retained (pp)':'Funding','Net gap (pp)':'Net gap',
           'Total P&L / C (%)':'Total (\\%)','Post-formation P&L / C (%)':'After day 1 (\\%)',
           'Accounts ahead of trading':'Ahead / 32'}
    def cell(x):
        if isinstance(x,(float,np.floating)): return f'{x:.2f}'
        return str(x).replace('&',r'\&').replace('%',r'\%').replace('_',r'\_')
    tex = ('\\begin{table}[htbp]\n\\centering\\small\n\\caption{'+caption+'}\n\\label{'+label+'}\n'
           '\\begin{tabular}{'+fmt+'}\n\\toprule\n'+' & '.join(short.get(c,cell(c)) for c in df.columns)+r' \\'+'\n\\midrule\n')
    tex += '\n'.join(' & '.join(cell(v) for v in row)+r' \\' for row in df.itertuples(index=False,name=None))
    tex += '\n\\bottomrule\n\\end{tabular}\n\\end{table}\n'
    (frl/(name+'.tex')).write_text(tex)

risk = pd.read_csv(der/'i6_vol_denominator.csv')
assert len(risk)==32 and risk.groupby('model').size().eq(4).all()
means = risk.groupby('model')[['vol_equity','vol_fixed','final_return']].mean()
rho = lambda g, x: float(spearmanr(g[x],g.final_return).statistic)
rows=[]
for name in ['None']+list(means.index):
    g=means if name=='None' else means.drop(name)
    a,b=rho(g,'vol_equity'),rho(g,'vol_fixed')
    rows.append({'Omitted model':name,'Current equity':a,'Initial capital':b,'Difference':b-a})
loo=pd.DataFrame(rows)
table(loo,'feedback_model_loo',r'Spearman volatility--return correlations across model means. Each omitted model removes all four accounts. Difference is initial-capital minus current-equity correlation. These are descriptive sensitivity checks.', 'tab:feedbackloo','lrrr')

m=oh.Market(root)
t0=m.lo+24*fh.HOUR
fills=m.fills[m.fills.time.between(m.lo,m.hi)].copy()
fills['notional']=fills.sz.abs()*fills.px
cost=fills.groupby('model').agg(fees=('fee','sum'),notional=('notional','sum'))
cost['capital']=40000.
cost['Fees / capital (%)']=100*cost.fees/cost.capital
cost['Turnover (times)']=cost.notional/cost.capital
cost['Fee hurdle (bp)']=10000*cost.fees/cost.notional
cost['Net return (%)']=means.final_return*100
cost['Return before fees (%)']=cost['Net return (%)']+cost['Fees / capital (%)']
cost=cost.sort_values('Net return (%)',ascending=False)
table(cost.reset_index().rename(columns={'model':'Model'})[['Model','Turnover (times)','Fees / capital (%)','Fee hurdle (bp)','Net return (%)']],
      'feedback_costs',r'Full-season turnover, recorded fees and daily-booked net returns by model. Turnover sums absolute traded notional, counting both entry and exit, and divides by the four accounts\textquotesingle{} combined initial capital of \$40,000. The fee hurdle is fees divided by traded notional, in basis points; it excludes spread, funding and market impact.', 'tab:feedbackcosts','lrrrr')
baseline=json.loads((der/'a1_pnl_summary.json').read_text())['totals']['S15']
assert abs(cost.fees.sum()-baseline['fees'])<1e-7

d=pd.read_csv(der/'holding_vs_trading_accounts.csv').set_index('tag')
inherited=d.hold_net-d.hold_mtm-d.funding_hold
idx_ratio=float(m.price('xyz:XYZ100',np.array([m.hi]))[0]/m.price('xyz:XYZ100',np.array([t0]))[0])
sweep=pd.read_csv(der/'organiser_hourly_sweep_accounts.csv')
frozen=sweep[sweep.formation_hour.eq(24)].set_index('tag').reindex(d.index)
paths={'Realised trading':d.actual_net,'Frozen, isolated A':frozen.isolated_net_A,
       'Frozen, isolated B':frozen.isolated_net_B,'Frozen, shared collateral':d.hold_net,
       'Cash from formation':inherited,
       'Index price reference':inherited+(10000+inherited)*(idx_ratio-1)}
bench=pd.DataFrame([{'Path':k,'Total P&L / C (%)':100*v.mean()/10000,
                    'Post-formation P&L / C (%)':100*(v-inherited).mean()/10000,
                    'Accounts ahead of trading':int((v>d.actual_net).sum())} for k,v in paths.items()])
table(bench,'feedback_benchmarks',r'Common-formation comparisons. All paths inherit each account\textquotesingle{}s equity after 24 hours. Cash earns zero thereafter; its total return retains the first-day result. The index reference applies the XYZ100 perpetual price change to that equity without leverage, fees or funding and is a price reference, not an implementable Nasdaq investment. Closing the inherited book is assumed costless for cash and index references. C is initial capital.', 'tab:feedbackbench','lrrr')

deviations=pd.read_csv(der/'holding_vs_trading_deviations.csv')
later=m.hours>t0
parts=[]
for coin in m.coins:
    post=fills[fills.coin.eq(coin)&fills.time.gt(t0)]
    fees=float(post.fee.sum())
    f_actual=0.;f_frozen=0.
    for tag in m.tags:
        q0=float(m.quantity(tag,coin,np.array([t0]))[0])
        if (tag,coin) in m.positions:
            q=fh.position_path(m.positions[(tag,coin)],m.hours)[later]
            f_actual+=float(np.sum(np.where(q!=0,q*m.unit[coin][later],0.)))
        if q0: f_frozen+=float(np.sum(q0*m.unit[coin][later]))
    gross=float(deviations.loc[deviations.coin.eq(coin),'gap'].sum())
    parts.append({'coin':coin,'gross':gross,'fees':fees,'funding_difference':f_frozen-f_actual,
                  'contribution':gross+fees+f_frozen-f_actual})
parts=pd.DataFrame(parts)
total=float(d.advantage.sum()); residual=total-float(parts.contribution.sum())
assert abs(parts.fees.sum()-d.fees_after.sum())<1e-6
assert abs(parts.funding_difference.sum()-(d.funding_hold-d.funding_actual).sum())<1e-6
assert abs(residual)<4*32
drop=pd.DataFrame({'Omitted instrument':parts.coin.str.replace('xyz:','',regex=False),
                  'Before-cost gap (pp)':100*(deviations.gap.sum()-parts.gross)/320000,
                  'Fees retained (pp)':100*(parts.fees.sum()-parts.fees)/320000,
                  'Funding gap retained (pp)':100*(parts.funding_difference.sum()-parts.funding_difference)/320000,
                  'Net gap (pp)':100*(total-parts.contribution)/320000})
table(drop,'feedback_instrument_loo',r'Instrument-deletion accounting sensitivity, shared collateral and 24-hour formation. Each deletion removes that instrument\textquotesingle{}s trading contribution, post-formation fees and funding difference from both books. Initial capital stays fixed. A small common valuation residual is retained. This does not rerun agent decisions or reallocate capital.', 'tab:feedbackinstrument','lrrrr')
parts.to_csv(dest/'instrument_contributions.csv',index=False)

# Revalue only terminal positions at the archived organiser endpoint prices.
org=json.loads((der/'organiser_hourly.json').read_text())
correction={tag:0. for tag in m.tags}
for coin in m.coins:
    dp=org['organiser_close_prices'][coin]-float(m.price(coin,np.array([m.hi]))[0])
    for tag in m.tags:
        q0,qT=m.quantity(tag,coin,np.array([t0,m.hi]))
        correction[tag]+=(q0-qT)*dp
org_gap=d.advantage+pd.Series(correction)
expected=pd.read_csv(der/'organiser_hourly_sweep.csv').set_index('formation_hour').loc[24,'advantage_pp_organiser_close_prices']
assert abs(org_gap.mean()/100-expected)<1e-7

# Read original liquidation flags rather than inferring the route from prices.
liqfills, events=oh.liquidation_events(root)
events=events[events.time.between(m.lo,m.hi)]
events.to_csv(dest/'liquidation_methods.csv',index=False)
trig=pd.read_csv(der/'organiser_hourly_trigger_validation.csv')
u=trig[trig.in_season & trig.position_unchanged_since_snapshot]
assert len(events)==17 and len(u)==14

coverage=sweep.groupby('formation_hour').positions_open.agg(
    open_positions='sum',active_accounts=lambda x:int(x.gt(0).sum()),minimum='min')
week=sweep[sweep.advantage_168h.notna()].copy()
window=[]
for cutoff in [1,12,24,26,48]:
    x=week[week.formation_hour.ge(cutoff)]
    g=x.groupby('formation_hour')[['advantage_168h','isolated_A_advantage_168h','isolated_B_advantage_168h']].sum()/3200
    window.append({'First hour':cutoff,'Windows':len(g),'Shared ahead':int(g.advantage_168h.gt(0).sum()),
                   'A ahead':int(g.isolated_A_advantage_168h.gt(0).sum()),'B ahead':int(g.isolated_B_advantage_168h.gt(0).sum())})
table(pd.DataFrame(window),'feedback_early_windows',r'Seven-day formation sweeps after excluding early formation hours. Counts refer to overlapping windows on one market path.', 'tab:feedbackearly','rrrrr')
coverage.to_csv(dest/'formation_position_coverage.csv')
summary={
 'rho_full':rows[0], 'rho_loo_ranges':{c:[float(loo[c][1:].min()),float(loo[c][1:].max())] for c in loo.columns[1:]},
 'fees_pct_initial':float(cost.fees.sum()/3200),
 'fees_share_loss_pct':float(100*cost.fees.sum()/abs(baseline['net_pnl'])),
 'fee_hurdle_bp':float(10000*cost.fees.sum()/cost.notional.sum()),
 'turnover_times':float(cost.notional.sum()/320000),
 'fees_return_spearman':float(spearmanr(cost['Fees / capital (%)'],cost['Net return (%)']).statistic),
 'cash_formation_total_pct':float(inherited.mean()/100),
 'index_price_return_pct':100*(idx_ratio-1),
 'drop_instrument_net_min':float(drop['Net gap (pp)'].min()),
 'drop_instrument_net_max':float(drop['Net gap (pp)'].max()),
 'drop_pltr_net':float(drop.loc[drop['Omitted instrument'].eq('PLTR'),'Net gap (pp)'].iloc[0]),
 'decomposition_residual_pp':residual/3200,
 'organiser_close_ahead':int(org_gap.gt(0).sum()),
 'liquidation_methods':events.method.value_counts().to_dict(),
 'liquidations_detected':int(u.pooled_prints_crossed.sum()),'liquidations_evaluable':len(u),
 'liquidations_not_evaluable':len(events)-len(u),
 'first_hour_coverage':coverage.loc[1].to_dict(),
 'first_all_active_hour':int(coverage[coverage.active_accounts.eq(32)].index.min()) if coverage.active_accounts.eq(32).any() else None,
 'window_duration_hours':(m.hi-m.lo)/fh.HOUR,
 'week_first_last':[float(week.formation_hour.min()),float(week.formation_hour.max())],
 'validation':'All identity, fee, funding, endpoint and panel checks passed.'}
nonoverlap=week[week.formation_hour.isin([1,169])].groupby('formation_hour')[['advantage_168h','isolated_A_advantage_168h','isolated_B_advantage_168h']].sum()/3200
nonoverlap.to_csv(dest/'nonoverlapping_windows.csv')
summary['nonoverlapping_windows']=nonoverlap.to_dict(orient='index')
all_active=week[week.formation_hour.isin(coverage[coverage.active_accounts.eq(32)].index)]
aa=all_active.groupby('formation_hour')[['advantage_168h','isolated_A_advantage_168h','isolated_B_advantage_168h']].sum()/3200
summary['all_active_windows']={'windows':len(aa),'positive':{c:int(aa[c].gt(0).sum()) for c in aa.columns}}
(dest/'fees_by_model_full.csv').write_text(cost.to_csv())
macros={'FeedbackFeePct':summary['fees_pct_initial'],'FeedbackFeeShare':summary['fees_share_loss_pct'],
        'FeedbackFeeBp':summary['fee_hurdle_bp'],'FeedbackTurnover':summary['turnover_times'],
        'FeedbackCash':summary['cash_formation_total_pct'],'FeedbackPltr':summary['drop_pltr_net'],
        'FeedbackDropMin':summary['drop_instrument_net_min'],'FeedbackDropMax':summary['drop_instrument_net_max'],
        'FeedbackIndexTotal':float(bench.iloc[-1]['Total P&L / C (%)']),
        'FeedbackHoldPost':float(bench.iloc[3]['Post-formation P&L / C (%)'])}
for row in org['liquidation_stress']['at_24h']:
    if row['scenario'].startswith('joint,'):
        direction='Early' if row['buffer']>0 else 'Late'
        for case in ['A','B']:
            macros[f'Feedback{direction}{case}Return']=row['actual_return_pct']+row['advantage_pp_'+case]
            macros[f'Feedback{direction}{case}Gap']=row['advantage_pp_'+case]
            macros[f'Feedback{direction}{case}Ahead']=row['accounts_ahead_'+case]
(frl/'feedback_numbers.tex').write_text('% Generated by analyse_feedback.py\n'+''.join(
    '\\newcommand{\\al'+k+'}{'+(str(int(v)) if k.endswith('Ahead') else f'{v:.2f}')+'}\n' for k,v in macros.items()))
(dest/'feedback_results.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
print(bench.to_string(index=False)); print(drop.to_string(index=False)); print(loo.to_string(index=False))
inputs=['i6_vol_denominator.csv','fills.parquet','panel.parquet','equity.parquet','accounts.parquet','funding.parquet',
        'holding_vs_trading_accounts.csv','holding_vs_trading_deviations.csv','organiser_hourly.json',
        'organiser_hourly_trigger_validation.csv','organiser_hourly_sweep.csv','organiser_hourly_sweep_accounts.csv']
(dest/'input_hashes.json').write_text(json.dumps({n:hashlib.sha256((der/n).read_bytes()).hexdigest() for n in inputs},indent=2)+'\n')
