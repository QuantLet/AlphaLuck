"""External replication of the frozen-book comparison on AI-Trader position logs.

Run: python src/aitrader_replication.py   (after src/download_aitrader.py)

AI-Trader (HKUDS/AI-Trader, MIT, commit pinned in src/download_aitrader.py)
logged, for 26 language-model accounts in four markets, the holdings and cash
after every step:

    us        Nasdaq-100 stocks, hourly, 6 accounts, $10,000 each
    astock    SSE-50 stocks, daily, 7 accounts, 100,000 CNY each
    astock_h  SSE-50 stocks, hourly, 7 accounts, 100,000 CNY each
    crypto    ten cryptocurrencies, daily, 6 accounts, 50,000 USDT each

The runs are historical replays, long-only, without leverage or fees. Orders
fill at the step's "buy price" (its open; src: agent_tools/tool_trade.py), so
every book here is marked at that price: equity at a step is
cash + sum_i q_i p_i(step) after the step's trades, and trading at the mark
leaves equity unchanged at that instant. A symbol without a price at a step
takes its latest earlier one. With no fees, every comparison is before costs:
it corresponds to the letter's before-cost component, not its net figure.

Design, as in the letter (Section 3.1):

* formation k: the last step of the first trading date, the first date on
  which any account in the market buys or sells (the logs open with a cash
  row and, for US stocks, a day of holds); the book (q_k, cash_k) is then
  held to the last step T. Advantage = (cash_k + sum q_k p_T - E_T) / C;
* sweep: every step from the first trading step to T - 1 as formation, to the
  close and over seven calendar days (end = last step <= t_k + 7 days, only
  where that fits inside the run);
* market: an equal-weighted index of the market's universe built from the
  same price files (mean step return over symbols priced at both steps).
  Each book is charged sum_s N_s (M_{s+1} / M_s - 1), N_s its stock value;
  this removes a unit-beta exposure to the universe, not an estimated factor
  model. The universe's own return over the window is reported alongside.

Aggregates are dollar sums over accounts divided by summed initial capital,
within a market (currencies differ, so markets are not pooled in money);
account counts are pooled.

Writes data/derived/aitrader_{accounts,sweep}.csv,
data/derived/aitrader_replication.json and paper/frl/aitrader_numbers.tex.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/aitrader/data'

MARKETS = {
    'us': ('agent_data', 'merged.jsonl'),
    'astock': ('agent_data_astock', 'A_stock/merged.jsonl'),
    'astock_h': ('agent_data_astock_hour', 'A_stock/merged_hourly.jsonl'),
    'crypto': ('agent_data_crypto', 'crypto/crypto_merged.jsonl'),
}
LABEL = {'us': 'Nasdaq-100, hourly', 'astock': 'SSE-50, daily',
         'astock_h': 'SSE-50, hourly', 'crypto': 'crypto, daily'}
HORIZON = timedelta(days=7)
EPS = 1e-6


def parse_time(s):
    return datetime.fromisoformat(s) if ' ' in s else datetime.fromisoformat(s + ' 00:00:00')


def load_prices(path):
    """symbol -> Series of buy (open) prices indexed by timestamp."""
    out = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        sym = d['Meta Data']['2. Symbol']
        series = next(v for k, v in d.items() if k.startswith('Time Series'))
        s = pd.Series({parse_time(t): float(v['1. buy price'])
                       for t, v in series.items() if '1. buy price' in v})
        out[sym] = s.sort_index()
    return out


def load_book(path):
    """Holdings after the last record of each step (step x symbol), cash, and
    the date of the first buy or sell."""
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    trades = [parse_time(r['date']) for r in rows
              if (r.get('this_action') or {}).get('action', 'no_trade') != 'no_trade']
    last = {}
    for r in rows:
        last[parse_time(r['date'])] = r['positions']
    book = pd.DataFrame.from_dict(last, orient='index').sort_index().fillna(0.0)
    cash = book.pop('CASH').astype(float)
    book = book.astype(float)
    if (book < -EPS).any().any():
        raise ValueError(f'Negative holding in {path}')
    if (cash < -EPS).any():
        raise ValueError(f'Negative cash in {path}')
    return book, cash, min(trades).date()


def price_matrix(prices, steps, symbols):
    """Latest price at or before each step; NaN before a symbol's first price."""
    cols = {}
    for s in symbols:
        if s not in prices:
            cols[s] = pd.Series(np.nan, index=steps)
            continue
        p = prices[s]
        cols[s] = p.reindex(p.index.union(steps)).ffill().reindex(steps)
    return pd.DataFrame(cols, index=steps)


def market_index(prices, steps):
    """Equal-weighted universe index on the steps, 1 at the first priced step."""
    px = price_matrix(prices, steps, sorted(prices))
    ratio = px / px.shift(1)
    step_ret = ratio.where(np.isfinite(ratio)).mean(axis=1).fillna(1.0)
    return step_ret.cumprod()


def hedge_charge(stock_value, index):
    """sum_s N_s (M_{s+1} / M_s - 1)."""
    n, m = np.asarray(stock_value, float), np.asarray(index, float)
    return float(np.sum(n[:-1] * (m[1:] / m[:-1] - 1)))


def frozen_advantage(q, cash, px, k, end):
    """Frozen-minus-realised result at step `end`, book frozen after step k."""
    frozen = cash.iloc[k] + float(np.nansum(q.iloc[k].to_numpy() * px.iloc[end].to_numpy()))
    actual = cash.iloc[end] + float(np.nansum(q.iloc[end].to_numpy() * px.iloc[end].to_numpy()))
    return frozen - actual


def check_priced(q, px, tag):
    held = q.to_numpy() > EPS
    if np.isnan(px.to_numpy()[held]).any():
        raise ValueError(f'Held symbol without a price: {tag}')


def account(market, model, q, cash, prices, index, first_date):
    steps = q.index
    px = price_matrix(prices, steps, q.columns)
    check_priced(q, px, (market, model))
    stock = (q * px.fillna(0.0)).sum(axis=1)
    equity = cash + stock
    capital = float(equity.iloc[0])
    on_first = np.flatnonzero(steps.date == first_date)
    k = int(on_first[-1])
    T = len(steps) - 1
    adv = frozen_advantage(q, cash, px, k, T)
    frozen_stock = (q.iloc[k].to_numpy() * px.fillna(0.0).to_numpy()).sum(axis=1)
    m = index.reindex(steps).to_numpy()
    hedge_frozen = hedge_charge(frozen_stock[k:], m[k:])
    hedge_actual = hedge_charge(stock.to_numpy()[k:], m[k:])
    trades = int((q.diff().abs().sum(axis=1) > EPS).iloc[k + 1:].sum())
    row = {
        'market': market, 'model': model, 'capital': capital,
        'formation': steps[k].isoformat(sep=' '), 'close': steps[T].isoformat(sep=' '),
        'steps_after': T - k, 'trading_steps_after': trades,
        'equity_formation': float(equity.iloc[k]), 'equity_close': float(equity.iloc[T]),
        'frozen_close': float(equity.iloc[k] + adv + equity.iloc[T] - equity.iloc[k]),
        'advantage': adv, 'advantage_hedged': adv - hedge_frozen + hedge_actual,
        'invested_share_frozen': float(frozen_stock[k] / equity.iloc[k]),
        'invested_share_actual': float((stock / equity).iloc[k:].mean()),
    }
    sweep = []
    for j in range(int(on_first[0]), T):
        end7 = int(np.flatnonzero(steps <= steps[j] + HORIZON)[-1])
        sweep.append({
            'market': market, 'model': model, 'formation_step': j,
            'formation': steps[j], 'advantage_close': frozen_advantage(q, cash, px, j, T),
            'advantage_7d': (frozen_advantage(q, cash, px, j, end7)
                             if steps[j] + HORIZON <= steps[T] else np.nan),
        })
    return row, pd.DataFrame(sweep)


def summarise(acc, sweep, index_close):
    out = {}
    for market, a in acc.groupby('market', sort=False):
        cap = a['capital'].sum()
        s = sweep[sweep['market'] == market]
        agg = s.groupby('formation')[['advantage_close', 'advantage_7d']].sum(min_count=1) / cap
        first = a['formation'].iloc[0]
        close = agg['advantage_close']
        week = agg['advantage_7d'].dropna()
        out[market] = {
            'label': LABEL[market], 'accounts': len(a),
            'first': a['formation'].min(), 'close': a['close'].max(),
            'actual_pct': 100 * (a['equity_close'].sum() / cap - 1),
            'frozen_pct': 100 * (a['frozen_close'].sum() / cap - 1),
            'advantage_pp': 100 * a['advantage'].sum() / cap,
            'ahead': int((a['advantage'] > 0).sum()),
            'advantage_hedged_pp': 100 * a['advantage_hedged'].sum() / cap,
            'ahead_hedged': int((a['advantage_hedged'] > 0).sum()),
            'universe_return_pct': 100 * index_close[market],
            'formations': len(close), 'positive_close': int((close > 0).sum()),
            'formations_7d': len(week), 'positive_7d': int((week > 0).sum()),
            'median_7d_pp': 100 * float(week.median()) if len(week) else None,
            'first_day_pct_close': float(100 * (close < close.loc[pd.Timestamp(first)]).mean()),
            'trading_steps_after': int(a['trading_steps_after'].sum()),
        }
    out['all'] = {
        'accounts': len(acc), 'ahead': int((acc['advantage'] > 0).sum()),
        'ahead_hedged': int((acc['advantage_hedged'] > 0).sum()),
        'markets_positive': int(sum(v['advantage_pp'] > 0 for v in out.values())),
        'formations': sum(v['formations'] for v in out.values()),
        'positive_close': sum(v['positive_close'] for v in out.values()),
        'formations_7d': sum(v['formations_7d'] for v in out.values()),
        'positive_7d': sum(v['positive_7d'] for v in out.values()),
    }
    return out


def fmt(x, d=1):
    s = f'{x:,.{d}f}'.replace(',', '{,}')
    return r'\ensuremath{-}' + s[1:] if s.startswith('-') else s


def write_tex(root, r):
    names = {'us': 'Us', 'astock': 'Ad', 'astock_h': 'Ah', 'crypto': 'Cr'}
    m = {}
    for market, key in names.items():
        v = r[market]
        m.update({
            f'Ait{key}N': str(v['accounts']), f'Ait{key}Adv': fmt(v['advantage_pp']),
            f'Ait{key}Ahead': str(v['ahead']), f'Ait{key}Hedged': fmt(v['advantage_hedged_pp']),
            f'Ait{key}AheadHedged': str(v['ahead_hedged']),
            f'Ait{key}Actual': fmt(v['actual_pct']), f'Ait{key}Frozen': fmt(v['frozen_pct']),
            f'Ait{key}Universe': fmt(v['universe_return_pct']),
            f'Ait{key}Formations': str(v['formations']),
            f'Ait{key}PositiveClose': str(v['positive_close']),
            f'Ait{key}FormationsWeek': str(v['formations_7d']),
            f'Ait{key}PositiveWeek': str(v['positive_7d']),
            f'Ait{key}FirstPct': fmt(v['first_day_pct_close'], 0),
        })
    a = r['all']
    m.update({'AitN': str(a['accounts']), 'AitAhead': str(a['ahead']),
              'AitAheadHedged': str(a['ahead_hedged']),
              'AitMarketsPositive': str(a['markets_positive']),
              'AitFormations': f"{a['formations']:,}".replace(',', '{,}'),
              'AitPositiveClose': f"{a['positive_close']:,}".replace(',', '{,}'),
              'AitFormationsWeek': f"{a['formations_7d']:,}".replace(',', '{,}'),
              'AitPositiveWeek': f"{a['positive_7d']:,}".replace(',', '{,}')})
    lines = ['% Generated by src/aitrader_replication.py']
    lines += [rf'\newcommand{{\al{k}}}{{{v}}}' for k, v in m.items()]
    (root / 'paper/frl/aitrader_numbers.tex').write_text('\n'.join(lines) + '\n')
    body = ''.join(
        f"{v['label']} & {v['accounts']} & ${fmt(v['actual_pct'])}$ & ${fmt(v['frozen_pct'])}$ & "
        f"${fmt(v['advantage_pp'])}$ & {v['ahead']} & ${fmt(v['advantage_hedged_pp'])}$ & "
        f"{v['positive_close']}/{v['formations']} & {v['positive_7d']}/{v['formations_7d']} \\\\\n"
        for k, v in r.items() if k != 'all')
    (root / 'paper/frl/aitrader_table.tex').write_text(
        '% Generated by src/aitrader_replication.py\n'
        '\\begin{table}[ht]\n\\centering\\footnotesize\n'
        '\\caption{Frozen book against realised trading in AI-Trader. Returns in per cent and '
        'advantages in points of initial capital, aggregated within each market; frozen after the '
        'first trading day. Market-adjusted charges each book its stock value times the '
        'equal-weighted universe return. The last two columns count formation steps with a positive '
        'aggregate advantage, to the close and over seven days.}\n'
        '\\label{tab:aitrader}\n\\setlength{\\tabcolsep}{3pt}\n'
        '\\begin{tabular}{lrrrrrrrr}\n\\toprule\n'
        'Market & $N$ & Realised & Frozen & Advantage & Ahead & Adjusted & To close & 7 days \\\\\n'
        '\\midrule\n' + body + '\\bottomrule\n\\end{tabular}\n\\end{table}\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=ROOT)
    root = ap.parse_args().root.resolve()
    raw = root / 'data/raw/aitrader/data'
    rows, sweeps, index_close = [], [], {}
    for market, (folder, price_file) in MARKETS.items():
        prices = load_prices(raw / price_file)
        books = {p.parent.parent.name: load_book(p)
                 for p in sorted((raw / folder).glob('*/position/position.jsonl'))}
        steps = sorted(set().union(*(b[0].index for b in books.values())))
        index = market_index(prices, pd.DatetimeIndex(steps))
        first_date = min(b[2] for b in books.values())
        for model, (q, cash, _) in books.items():
            row, sw = account(market, model, q, cash, prices, index, first_date)
            rows.append(row)
            sweeps.append(sw)
        first = pd.Timestamp(min(r['formation'] for r in rows if r['market'] == market))
        index_close[market] = float(index.iloc[-1] / index.loc[first] - 1)
    acc, sweep = pd.DataFrame(rows), pd.concat(sweeps, ignore_index=True)
    result = summarise(acc, sweep, index_close)
    der = root / 'data/derived'
    acc.to_csv(der / 'aitrader_accounts.csv', index=False)
    sweep.to_csv(der / 'aitrader_sweep.csv', index=False)
    (der / 'aitrader_replication.json').write_text(json.dumps(result, indent=1, default=str) + '\n')
    write_tex(root, result)
    print(json.dumps(result, indent=1, default=str))
    print(acc[['market', 'model', 'equity_formation', 'equity_close', 'frozen_close',
               'advantage', 'advantage_hedged', 'trading_steps_after']].round(0).to_string(index=False))


if __name__ == '__main__':
    main()
