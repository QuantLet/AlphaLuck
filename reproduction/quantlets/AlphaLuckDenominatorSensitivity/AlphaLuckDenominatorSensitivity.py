"""Standalone descriptive Quantlet: risk denominators and common-date sensitivity.

Run: python AlphaLuckDenominatorSensitivity.py
No network, credentials, parent repository or absolute data paths are used.
The resampling ranges are sensitivity summaries, not confidence intervals.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import scipy
from scipy.stats import rankdata, spearmanr
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
SEED = 20261015

def descriptive_statistics(x: np.ndarray, outcome: np.ndarray) -> dict[str, np.ndarray]:
    """x has axes (draw, model, arm); outcome has axes (model, arm).

    F is an additive sums-of-squares ratio ONLY. No reference distribution is
    used. W is rank concordance across arms, corrected for tied ranks.
    """
    x = np.asarray(x, float)
    if x.ndim == 2:
        x = x[None, :, :]
    b, m, a = x.shape
    grand = x.mean(axis=(1, 2))
    ssm = a * ((x.mean(axis=2) - grand[:, None]) ** 2).sum(axis=1)
    ssa = m * ((x.mean(axis=1) - grand[:, None]) ** 2).sum(axis=1)
    sst = ((x - grand[:, None, None]) ** 2).sum(axis=(1, 2))
    sse = np.maximum(sst - ssm - ssa, 0)
    F = (ssm / (m - 1)) / (sse / ((m - 1) * (a - 1)))
    ranks = rankdata(x, axis=1)
    rank_sums = ranks.sum(axis=2)
    S = ((rank_sums - a * (m + 1) / 2) ** 2).sum(axis=1)
    # For each tied group of size t, summing t^2-1 over its members gives t^3-t.
    tie_counts = (ranks[:, :, None, :] == ranks[:, None, :, :]).sum(axis=2)
    tie_sum = (tie_counts ** 2 - 1).sum(axis=(1, 2))
    W = 12 * S / (a * a * (m ** 3 - m) - a * tie_sum)
    xr = ranks - ranks.mean(axis=1, keepdims=True)
    yr = rankdata(outcome, axis=0)
    yr -= yr.mean(axis=0, keepdims=True)
    rho = ((xr * yr[None, :, :]).sum(axis=1) /
           np.sqrt((xr ** 2).sum(axis=1) * (yr ** 2).sum(axis=0))).mean(axis=1)
    # Relative model sum of squares after removing the arm component; a
    # descriptive partial eta-squared, not a causal variance fraction.
    partial_ss = ssm / (ssm + sse)
    return {'F': F, 'W': W, 'rho': rho, 'partial_model_ss': partial_ss}

def evaluate(pnl: np.ndarray, ret: np.ndarray, outcome: np.ndarray) -> dict:
    """Arrays: draw x day x model x arm (or day x model x arm)."""
    if pnl.ndim == 3:
        pnl, ret = pnl[None], ret[None]
    fixed = descriptive_statistics(pnl.std(axis=1, ddof=1), outcome)
    equity = descriptive_statistics(ret.std(axis=1, ddof=1), outcome)
    out = {f'{den}_{k}': v for den, d in [('fixed', fixed), ('equity', equity)]
           for k, v in d.items()}
    out.update({f'delta_{k}': fixed[k] - equity[k] for k in fixed})
    return out

def moving_blocks(n: int, length: int, draws: int, rng: np.random.Generator):
    """Ordinary overlapping non-circular moving blocks, truncated to n dates."""
    count = (n + length - 1) // length
    starts = rng.integers(0, n - length + 1, size=(draws, count))
    return (starts[..., None] + np.arange(length)).reshape(draws, -1)[:, :n]

def scalar(d):
    return {k: float(np.asarray(v).item()) for k, v in d.items()}

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def checks():
    """Independent scalar checks for the vectorised statistical summaries."""
    x = np.array([[1., 2., 1.], [1., 3., 2.], [3., 1., 3.], [4., 4., 4.]])
    y = np.array([[4., 2., 1.], [3., 3., 2.], [2., 1., 3.], [1., 4., 4.]])
    got = scalar(descriptive_statistics(x, y))
    want_rho = np.mean([spearmanr(x[:,a],y[:,a]).statistic for a in range(3)])
    np.testing.assert_allclose(got['rho'],want_rho,atol=1e-14)
    m,a=x.shape
    ms_model = a*np.sum((np.mean(x,axis=1)-np.mean(x))**2)/(m-1)
    residual = x-x.mean(axis=1)[:,None]-x.mean(axis=0)[None,:]+x.mean()
    ms_error = np.sum(residual**2)/((m-1)*(a-1))
    np.testing.assert_allclose(got['F'],ms_model/ms_error,atol=1e-13)
    ranks=np.column_stack([rankdata(x[:,j]) for j in range(a)])
    ties=sum(sum(c**3-c for c in np.unique(ranks[:,j],return_counts=True)[1]) for j in range(a))
    want_w=12*np.sum((ranks.sum(axis=1)-a*(m+1)/2)**2)/(a*a*(m**3-m)-a*ties)
    np.testing.assert_allclose(got['W'],want_w,atol=1e-14)
    vals=np.random.default_rng(SEED).normal(size=(14,4,3))
    for k,v in evaluate(vals,vals.copy(),y).items():
        if k.startswith('delta_'):np.testing.assert_array_equal(v,0)
    for length in [1,2,3]:
        ids=moving_blocks(14,length,5,np.random.default_rng(SEED))
        assert ids.shape==(5,14) and ids.min()>=0 and ids.max()<14
        for j in range(0,14,length):
            assert np.all(np.diff(ids[:,j:min(j+length,14)],axis=1)==1)


def preview(comparison, summary, destination):
    navy,orange,green,ink,magenta = '#0057B8','#D64D00','#008C6A','#101820','#A00070'
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
                        'text.color':ink,'axes.labelcolor':ink,
                        'xtick.color':ink,'ytick.color':ink,
                        'axes.edgecolor':ink,'figure.facecolor':'white',
                        'axes.facecolor':'white','savefig.facecolor':'white',
                        'pdf.fonttype':42,'ps.fonttype':42})
    fig,axs=plt.subplots(2,2,figsize=(12,7.9))
    metrics=['vol','leverage','turnover']; names=['Volatility','Gross exposure','Turnover']
    xlims={'F':(0,14.5),'W':(0,1),'rho':(-.68,.43)}
    titles={'F':'(a) Additive mean-square ratio','W':'(b) Rank agreement across arms',
            'rho':'(c) Association with realised final return'}
    xlabels={'F':'F (descriptive)','W':"Kendall's W",'rho':'Mean within-arm Spearman correlation'}
    for ax,stat in zip(axs.ravel()[:3],['F','W','rho']):
        for j,metric in enumerate(metrics):
            r=comparison.loc[metric]
            left,right=r['equity_'+stat],r['fixed_'+stat]
            ax.plot([left,right],[j,j],color=green,lw=2.3,zorder=2)
            ax.scatter([left],[j],s=72,color=navy,marker='o',edgecolor='white',linewidth=.5,zorder=3)
            ax.scatter([right],[j],s=72,color=orange,marker='D',edgecolor='white',linewidth=.5,zorder=4)
            for value,colour,dy in [(left,navy,12),(right,orange,-17)]:
                ax.annotate(f'{value:.2f}',(value,j),xytext=(0,dy),textcoords='offset points',
                            color=colour,ha='center',va='center',fontsize=9,fontweight='bold')
        ax.set_ylim(2.55,-.6);ax.set_yticks(range(3),names)
        ax.set_xlim(*xlims[stat]);ax.set_xlabel(xlabels[stat]);ax.set_title(titles[stat],loc='left',pad=14,fontweight='bold',fontsize=11)
        if stat=='rho':ax.axvline(0,color=ink,ls=':',lw=1,zorder=0)
        ax.spines[['right','top']].set_visible(False)
        ax.tick_params(axis='y',length=0,pad=8)
    ax=axs[1,1]
    d=summary.query("statistic == 'delta_rho'").sort_values('block_days')
    for j,r in enumerate(d.itertuples()):
        ax.plot([r.q025,r.q975],[j,j],color=green,lw=3.0,solid_capstyle='round')
        ax.scatter(r.median,j,s=52,color=green,marker='s',zorder=4)
        ax.annotate(f'[{r.q025:.3f}, {r.q975:.3f}]',(r.q975,j),xytext=(6,0),
                    textcoords='offset points',ha='left',va='center',fontsize=9,color=ink)
    observed=comparison.loc['vol','delta_rho']
    ax.axvline(observed,color=magenta,lw=1.7,ls='--')
    ax.set_title('(d) Reweighting common observed dates',loc='left',pad=14,fontweight='bold',fontsize=11)
    ax.set_yticks(range(3),['1-day blocks','2-day blocks','3-day blocks'])
    ax.set_ylim(2.55,-.6);ax.set_xlim(-.03,.93)
    ax.set_xlabel('Volatility correlation difference: initial - current')
    ax.spines[['right','top']].set_visible(False);ax.tick_params(axis='y',length=0,pad=8)
    ax.text(.98,.97,f'Observed difference: {observed:.3f}',transform=ax.transAxes,ha='right',va='top',fontsize=9,color=magenta)
    fig.suptitle('Risk denominator choices change the summaries',x=.07,y=.985,ha='left',fontsize=17,fontweight='bold',color=ink)
    fig.text(.07,.945,'Alpha Arena Season 1.5 | 32 accounts | 14 daily observations',ha='left',fontsize=11,color=ink)
    handles=[Line2D([0],[0],marker='o',lw=0,color=navy,markersize=8,label='Current equity'),
             Line2D([0],[0],marker='D',lw=0,color=orange,markersize=8,label='Initial capital')]
    fig.legend(handles=handles,loc='upper right',bbox_to_anchor=(.97,.963),frameon=False,ncol=2,fontsize=10)
    fig.subplots_adjust(left=.13,right=.95,top=.85,bottom=.14,hspace=.52,wspace=.45)
    fig.text(.07,.06,f'Panel (d): central 95% reweighting ranges, with medians; {int(summary.draws.iloc[0]):,} draws per block length.',fontsize=10,color=ink)
    fig.text(.07,.032,'Final returns stay fixed. These ranges are not confidence intervals or tests of model skill.',fontsize=10,color=ink,fontweight='bold')
    fig.savefig(destination/'AlphaLuckDenominatorSensitivity.png',dpi=170)
    fig.savefig(destination/'AlphaLuckDenominatorSensitivity.pdf',metadata={'Title':'AlphaLuck denominator sensitivity','Author':'Daniel Traian Pele','CreationDate':None,'ModDate':None})
    plt.close(fig)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--draws',type=int,default=20000)
    ap.add_argument('--out',type=Path,default=HERE/'outputs')
    args=ap.parse_args()
    if args.draws<1000:raise ValueError('Use at least 1000 draws per block length')
    checks()
    provenance=json.loads((HERE/'data/PROVENANCE.json').read_text())
    for name,want in provenance['input_sha256'].items():
        if sha256(HERE/'data'/name)!=want:raise ValueError(f'Input checksum mismatch: {name}')
    account=pd.read_csv(HERE/'data/account_measures.csv').sort_values(['model','arm']).reset_index(drop=True)
    daily=pd.read_csv(HERE/'data/paired_daily_inputs.csv')
    if account[['tag','model','arm']].isna().any().any() or daily.isna().any().any():raise ValueError('Missing data')
    assert len(account)==32 and account.model.nunique()==8 and account.arm.nunique()==4
    assert not account.duplicated(['model','arm']).any()
    assert account.tag.nunique()==32 and not daily.duplicated(['date','tag']).any()
    assert account.n_days.eq(14).all()
    tags=account.tag.to_list();dates=sorted(daily.date.unique())
    assert len(dates)==14 and len(daily)==448
    def cube(col):
        return daily.pivot(index='date',columns='tag',values=col).loc[dates,tags].to_numpy().reshape(14,8,4)
    pnl,ret=cube('pnl_initial_capital'),cube('return_current_equity')
    assert np.isfinite(pnl).all() and np.isfinite(ret).all()
    outcome=account.final_return.to_numpy().reshape(8,4)
    pairs={'vol':{'equity':ret.std(axis=0,ddof=1),'fixed':pnl.std(axis=0,ddof=1)}}
    for metric in ['leverage','turnover']:
        pairs[metric]={den:account[metric+'_'+den].to_numpy().reshape(8,4) for den in ['equity','fixed']}
    rows=[]
    for metric,byden in pairs.items():
        values={den:scalar(descriptive_statistics(x,outcome)) for den,x in byden.items()}
        rows.append({'metric':metric,**{den+'_'+k:v for den,d in values.items() for k,v in d.items()},
                     **{'delta_'+k:values['fixed'][k]-values['equity'][k] for k in values['fixed']}})
    comparison=pd.DataFrame(rows).set_index('metric')
    expected=json.loads((HERE/'expected_statistics.json').read_text())
    for metric,row in comparison.iterrows():
        for key,value in row.items():np.testing.assert_allclose(value,expected[metric][key],rtol=1e-10,atol=1e-12)
    observed=scalar(evaluate(pnl,ret,outcome)); summaries=[]
    for length in [1,2,3]:
        ids=moving_blocks(14,length,args.draws,np.random.default_rng(SEED+length))
        chunks=[]
        for first in range(0,args.draws,512):
            ix=ids[first:first+512]
            chunks.append(pd.DataFrame(evaluate(pnl[ix],ret[ix],outcome)))
        values=pd.concat(chunks,ignore_index=True)
        assert np.isfinite(values.to_numpy()).all()
        for stat in values:
            q=values[stat].quantile([.025,.5,.975])
            summaries.append({'block_days':length,'statistic':stat,'observed':observed[stat],
                              'q025':float(q.loc[.025]),'median':float(q.loc[.5]),'q975':float(q.loc[.975]),'draws':args.draws})
    summary=pd.DataFrame(summaries)
    deletions=[]
    for unit,labels in [('date',dates),('model',sorted(account.model.unique())),('arm',sorted(account.arm.unique()))]:
        for i,label in enumerate(labels):
            keep=np.arange(len(labels))!=i
            if unit=='date':values=evaluate(pnl[keep],ret[keep],outcome)
            elif unit=='model':values=evaluate(pnl[:,keep],ret[:,keep],outcome[keep])
            else:values=evaluate(pnl[:,:,keep],ret[:,:,keep],outcome[:,keep])
            deletions.append({'unit':unit,'omitted':str(label),**scalar(values)})
    args.out.mkdir(parents=True,exist_ok=True)
    comparison.to_csv(args.out/'denominator_comparison.csv')
    summary.to_csv(args.out/'joint_block_summary.csv',index=False)
    pd.DataFrame(deletions).to_csv(args.out/'paired_leave_one_out.csv',index=False)
    report={'analysis':'Descriptive risk-denominator contrasts and common-date reweighting',
            'n_accounts':32,'n_daily_changes':14,'draws_per_block':args.draws,'block_lengths':[1,2,3],
            'seed_base':SEED,'scheme':'Overlapping non-circular blocks, concatenated and truncated at 14 dates',
            'fixed':'Season-final returns, account/model/arm labels',
            'interpretation':'Central 95% resampling ranges, not confidence intervals or significance tests',
            'limitations':['No independent model runs are generated.','Dependence beyond block length is not retained.',
                           'Only fourteen observed dates; no validated stationarity, block selection or coverage.',
                           'Reweighted observations are not dynamically consistent trading or wealth paths.',
                           'Initial and current equity are economically distinct legitimate estimands.',
                           'Inputs are derived data; raw transaction reconstruction is outside this compact Quantlet.'],
            'versions':{'python':sys.version.split()[0],'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'matplotlib':matplotlib.__version__},
            'input_sha256':provenance['input_sha256'],
            'checks_passed':['input hashes','balanced complete panel','independent scalar F/W/rho checks with ties',
                             'common contiguous blocks','zero contrast for identical inputs','historical numerical regression checks'],
            'observed_volatility':observed}
    (args.out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    preview(comparison,summary,HERE)
    print(comparison[['equity_F','fixed_F','equity_W','fixed_W','equity_rho','fixed_rho']].round(6).to_string())
    print(f'Completed {3*args.draws:,} common-date sensitivity draws; all checks passed.')

if __name__=='__main__':main()
