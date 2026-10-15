"""Reproduce a conditional frozen-position accounting comparison, offline.

Run: python AlphaLuckFrozenBenchmark.py
Inputs are relative to this file; --output selects another output directory.
The supplied endpoints already include the upstream hourly-funding proxy.
This script aggregates those endpoints and recomputes every cost and price
stress from account-level quantities, rather than reading stored scenarios.
No execution, liquidation, funding-history retrieval or trading is performed.
"""
from pathlib import Path
from itertools import product
import argparse
import hashlib
import json
import os
import tempfile

import numpy as np
import pandas as pd

# Keep headless execution usable on systems without a writable home cache.
os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'alphaluck-mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
BLUE, ORANGE, PURPLE = '#0057B8', '#D14900', '#7024A8'


def read_inputs():
    data = ROOT/'data'
    provenance = json.loads((data/'provenance.json').read_text())
    for name, expected in provenance['input_sha256'].items():
        actual = hashlib.sha256((data/name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'Input checksum differs: {name}')
    accounts = pd.read_csv(data/'accounts.csv').set_index('tag')
    positions = pd.read_csv(data/'positions.csv')
    if len(accounts) != 32 or accounts.index.has_duplicates:
        raise ValueError('Expected 32 distinct account endpoints')
    if positions.duplicated(['tag','coin']).any() or len(positions) != 224:
        raise ValueError('Expected seven position rows per account')
    if set(positions.tag) != set(accounts.index):
        raise ValueError('Account and position keys differ')
    for d in (accounts, positions):
        if not np.isfinite(d.select_dtypes('number')).all().all():
            raise ValueError('Non-finite input')
    if (positions.terminal_price<=0).any() or (accounts.initial_capital<=0).any():
        raise ValueError('Prices and initial capital must be positive')
    if not positions.groupby('coin').terminal_price.nunique().eq(1).all():
        raise ValueError('A common market price is required for every instrument')
    positions['frozen_notional'] = positions.frozen_quantity*positions.terminal_price
    positions['actual_notional'] = positions.actual_terminal_quantity*positions.terminal_price
    positions['differential_notional'] = positions.frozen_notional-positions.actual_notional
    notionals = positions.groupby('tag').agg(
        frozen_gross=('frozen_notional',lambda x:x.abs().sum()),
        actual_gross=('actual_notional',lambda x:x.abs().sum()),
        separate_price_bound=('differential_notional',lambda x:x.abs().sum()))
    accounts = accounts.join(notionals,validate='one_to_one')
    accounts['gap'] = accounts.frozen_net-accounts.actual_net
    return accounts, positions, provenance


def calculate(accounts, positions):
    capital = float(accounts.initial_capital.sum())
    frozen = float(accounts.frozen_net.sum())
    actual = float(accounts.actual_net.sum())
    gap = frozen-actual
    z = positions.groupby('coin').differential_notional.sum()
    common_bound = float(z.abs().sum())
    fee_rows, price_rows = [], []
    for bps in (0,1,5,10,25,50,100,250,500,1000):
        c = bps/10000
        h = accounts.frozen_net-c*accounts.frozen_gross
        for convention in ('frozen_only','both_books'):
            r = accounts.actual_net-c*accounts.actual_gross if convention=='both_books' else accounts.actual_net
            fee_rows.append(dict(cost_bps=bps,convention=convention,
                frozen_return_pct=100*float(h.sum())/capital,
                actual_return_pct=100*float(r.sum())/capital,
                gap_pp=100*float((h-r).sum())/capital,
                accounts_ahead=int((h>r).sum())))
    # One direction for each asset, common to every account. Its sign is
    # chosen after observing aggregate differential exposure, purely as stress.
    direction = -np.sign(z)
    exposures = positions.pivot(index='tag',columns='coin',values='differential_notional').reindex(accounts.index)
    for pct in (0,.1,.5,1,2,3,4,5):
        delta=pct/100
        common_change=exposures.mul(direction,axis=1).sum(axis=1)*delta
        for convention,change in (
            ('common_market_adverse',common_change),
            ('separate_account_lower_bounds',-accounts.separate_price_bound*delta)):
            g = accounts.gap+change
            price_rows.append(dict(price_error_bound_pct=pct,convention=convention,
                gap_pp=100*float(g.sum())/capital,
                accounts_ahead=int((g>0).sum())))
    summary = dict(accounts=len(accounts),formation_hours=24,initial_capital=capital,
        frozen_net_dollars=frozen,actual_net_dollars=actual,
        frozen_return_pct=100*frozen/capital,actual_return_pct=100*actual/capital,
        gap_dollars=gap,gap_pp=100*gap/capital,
        accounts_ahead=int((accounts.gap>0).sum()),
        frozen_terminal_gross=float(accounts.frozen_gross.sum()),
        actual_terminal_gross=float(accounts.actual_gross.sum()),
        frozen_only_break_even_cost_bps=10000*gap/float(accounts.frozen_gross.sum()),
        common_endpoint_break_even_pct=100*gap/common_bound,
        separate_account_bound_break_even_pct=100*gap/float(accounts.separate_price_bound.sum()),
        common_endpoint_differential_exposure=common_bound)
    fees, price = pd.DataFrame(fee_rows),pd.DataFrame(price_rows)
    # Reference checks are assertions only; calculations above use inputs.
    assert np.isclose(summary['frozen_return_pct'],2.8198317322181525,atol=1e-9)
    assert np.isclose(summary['actual_return_pct'],-26.300479979963526,atol=1e-9)
    assert summary['accounts_ahead']==26
    assert np.isclose(summary['common_endpoint_break_even_pct'],4.2543526535079454,atol=1e-9)
    # Independently enumerate all 2^7 common-price error vertices to check
    # the sign and tightness of the closed-form worst-case exposure bound.
    vertices=[float(z.to_numpy()@np.asarray(s)) for s in product((-1,1),repeat=len(z))]
    assert np.isclose(min(vertices),-common_bound)
    assert np.isclose(gap+.01*summary['common_endpoint_break_even_pct']*min(vertices),0,atol=1e-7)
    h100=fees[fees.cost_bps.eq(100)&fees.convention.eq('frozen_only')].iloc[0]
    assert np.isclose(h100.gap_pp,25.677459285119176,atol=1e-8) and h100.accounts_ahead==26
    for row in fees.itertuples():
        cost_h=float(positions.frozen_notional.abs().sum())*row.cost_bps/10000
        cost_r=float(positions.actual_notional.abs().sum())*row.cost_bps/10000 if row.convention=='both_books' else 0
        assert np.isclose(row.gap_pp,100*(gap-cost_h+cost_r)/capital,atol=1e-10)
    bound_order=price.pivot(index='price_error_bound_pct',columns='convention',values='gap_pp')
    assert (bound_order.separate_account_lower_bounds<=bound_order.common_market_adverse+1e-10).all()
    return summary,fees,price


def plot(summary,fees,price,out):
    plt.rcParams.update({'font.size':10,'axes.titlesize':12,'axes.labelsize':10,
        'text.color':'black','axes.labelcolor':'black','xtick.color':'black',
        'ytick.color':'black','axes.edgecolor':'black','figure.facecolor':'white',
        'axes.facecolor':'white','savefig.facecolor':'white','pdf.fonttype':42,
        'ps.fonttype':42})
    fig,axes=plt.subplots(1,3,figsize=(14,5.3))
    fig.subplots_adjust(left=.06,right=.985,top=.79,bottom=.26,wspace=.36)
    fig.suptitle('Frozen positions: a conditional accounting comparison',x=.06,ha='left',fontsize=17,fontweight='bold',y=.97)
    fig.text(.06,.89,'Alpha Arena Season 1.5  |  32 accounts  |  Freeze after 24 hours',fontsize=11)
    ax=axes[0]
    vals=[summary['frozen_return_pct'],summary['actual_return_pct']]
    ax.bar(['Frozen book','Realised path'],vals,color=[BLUE,ORANGE],width=.57)
    for x,v in enumerate(vals):
        ax.text(x,v+(1 if v>=0 else -1),f'{v:+.2f}%',ha='center',va='bottom' if v>=0 else 'top',fontweight='bold')
    ax.set_ylim(-32,11)
    ax.set_ylabel('Return (% of initial capital)')
    ax.set_title('(a) Hourly funding; pooled prices',loc='left',pad=14)
    ax.text(.04,.10,'Frozen exceeds realised: 26 / 32',transform=ax.transAxes,fontsize=9)
    ax=axes[1]
    for conv,col,lab,marker in [('frozen_only',BLUE,'Frozen charged alone','o'),('both_books',ORANGE,'Both books charged','s')]:
        f=fees[fees.convention.eq(conv)]
        ax.plot(f.cost_bps,f.gap_pp,color=col,marker=marker,ms=4,lw=2,label=lab)
    ax.set_xlabel('Hypothetical closing friction (bps)')
    ax.set_ylabel('Frozen − realised (percentage points)')
    ax.set_title('(b) Costs on terminal notional',loc='left',pad=14)
    ax.legend(frameon=False,fontsize=8,loc='upper left')
    ax.set_xlim(-20,1020)
    ax=axes[2]
    p=price[price.convention.eq('common_market_adverse')]
    ax.plot(p.price_error_bound_pct,p.gap_pp,color=PURPLE,marker='D',ms=4,lw=2)
    crit=summary['common_endpoint_break_even_pct']
    ax.scatter([crit],[0],s=50,color=ORANGE,zorder=3)
    ax.annotate(f'Break-even: {crit:.2f}%',xy=(crit,0),xytext=(.5,-10),textcoords='data',
        arrowprops={'arrowstyle':'->','color':'black','lw':1},fontsize=9)
    ax.set_xlabel('Common per-asset price-error bound (%)')
    ax.set_ylabel('Frozen − realised (percentage points)')
    ax.set_title('(c) Adverse terminal-price stress',loc='left',pad=14)
    ax.set_ylim(-13,34)
    ax.set_xlim(-.1,5.1)
    for ax in axes:
        ax.axhline(0,color='black',linewidth=.8,zorder=0)
        ax.spines[['top','right']].set_visible(False)
        ax.grid(False)
    fig.text(.06,.115,'All stresses are hypothetical. Price perturbations revalue both terminal books with the same price for each asset.',fontsize=9)
    fig.text(.06,.065,'Hourly funding uses pooled-price proxies. No historical liquidation, order-book impact or executable-strategy simulation.',fontsize=9)
    fig.savefig(out/'frozen_benchmark.png',dpi=180)
    # QuantLet discovery expects a preview next to the executable script.
    fig.savefig(ROOT/'AlphaLuckFrozenBenchmark.png',dpi=180)
    fig.savefig(out/'frozen_benchmark.pdf',metadata={'Title':'AlphaLuck frozen-book accounting comparison','Author':'Daniel Traian Pele','CreationDate':None,'ModDate':None})
    plt.close(fig)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'output')
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    accounts,positions,provenance=read_inputs()
    summary,fees,price=calculate(accounts,positions)
    fees.to_csv(args.output/'closing_cost_sensitivity.csv',index=False)
    price.to_csv(args.output/'endpoint_price_sensitivity.csv',index=False)
    result={'summary':summary,'interpretation':'Conditional mark-to-market accounting comparison, not an executable trading strategy.',
        'reproduction_scope':provenance['reproduction_scope'],
        'verification':{'input_sha256':'passed','reference_aggregates':'passed','common_price_vertices_checked':128,'closing_cost_identity':'passed','bound_ordering':'passed'},
        'limitations':provenance['limitations']}
    (args.output/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    plot(summary,fees,price,args.output)
    print(json.dumps({'summary':summary,'verification':result['verification']},indent=2))


if __name__=='__main__':
    main()
