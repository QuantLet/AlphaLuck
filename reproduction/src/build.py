"""Phase 2/3 derived layer: fills -> positions -> equity -> reconciliation.

Writes parquet to data/derived/:
  fills.parquet      every Hyperliquid fill for every arena wallet
  funding.parquet    funding payments
  ledger.parquet     deposits / withdrawals / transfers (from genesis)
  roundtrips.parquet flat -> non-flat -> flat cycles per (wallet, coin)
  panel.parquet      signed notional exposure per (wallet, coin) on a 5-min grid
  equity.parquet     reconstructed equity on the same 5-min grid
  recon.parquet      reconstructed vs organiser-published finals
"""
from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import prov
import wallets

RAW = prov.RAW
DER = os.path.join(prov.ROOT, "data", "derived")
GRID_MS = 5 * 60 * 1000


def _rows(pattern: str) -> list:
    out = []
    for p in sorted(glob.glob(os.path.join(RAW, pattern))):
        with open(p) as fh:
            out.extend(json.load(fh))
    return out


# ---------------------------------------------------------------- raw -> frames
def load_fills() -> pd.DataFrame:
    recs = []
    for row in wallets.registry():
        tag = wallets.tag(row)
        seen = set()
        for f in _rows(f"hl/userFillsByTime/{tag}.p*.json"):
            if f["tid"] in seen:
                continue
            seen.add(f["tid"])
            sz = float(f["sz"])
            recs.append(
                {
                    "season": row["season"],
                    "competition_id": row["competition_id"],
                    "model": row["model"],
                    "tag": tag,
                    "address": row["address"],
                    "time": f["time"],
                    "coin": f["coin"],
                    "px": float(f["px"]),
                    "sz": sz,
                    "signed_sz": sz if f["side"] == "B" else -sz,
                    "start_position": float(f["startPosition"]),
                    "dir": f["dir"],
                    "closed_pnl": float(f["closedPnl"]),
                    "fee": float(f["fee"]),
                    "oid": f["oid"],
                    "tid": f["tid"],
                }
            )
    df = pd.DataFrame(recs).sort_values(["tag", "time", "tid"]).reset_index(drop=True)
    return df


def load_funding() -> pd.DataFrame:
    """Retain funding provenance as well as booked cash amounts.

    A non-null n_samples denotes a daily aggregate for its labeled UTC day,
    not an event-level payment at the reported timestamp. Timestamp booking
    is retained only for the legacy baseline equity; the external hourly
    diagnostic evaluates the alternative cash timing explicitly. Aggregate
    interval metadata use [aggregation_start_ms, aggregation_end_ms), with
    the end exclusive; these boundaries do not allocate cash within the day.
    """
    recs = []
    for row in wallets.registry():
        tag = wallets.tag(row)
        seen = set()
        for f in _rows(f"hl/userFunding/{tag}.p*.json"):
            d = f["delta"]
            key = (f["time"], d["coin"], d["usdc"])
            if key in seen:
                continue
            seen.add(key)
            recs.append(
                {
                    "season": row["season"],
                    "competition_id": row["competition_id"],
                    "model": row["model"],
                    "tag": tag,
                    "time": f["time"],
                    "coin": d["coin"],
                    "usdc": float(d["usdc"]),
                    "funding_rate": float(d.get("fundingRate", 0) or 0),
                    "szi": float(d["szi"]) if d.get("szi") is not None else np.nan,
                    "n_samples": d.get("nSamples"),
                    "aggregation_start_ms": (
                        int(f["time"]) if d.get("nSamples") is not None else None
                    ),
                    "aggregation_end_ms": (
                        int(f["time"]) + 86_400_000
                        if d.get("nSamples") is not None else None
                    ),
                }
            )
    return pd.DataFrame(recs).sort_values(["tag", "time"]).reset_index(drop=True)


def load_ledger() -> pd.DataFrame:
    """Signed cash flows in/out of each wallet, from genesis."""
    recs = []
    for row in wallets.registry():
        tag = wallets.tag(row)
        addr = row["address"].lower()
        with open(os.path.join(RAW, f"hl/ledger_all/{tag}.json")) as fh:
            for e in json.load(fh):
                d = e["delta"]
                t = d["type"]
                amt = float(d.get("usdc") or d.get("amount") or 0)
                dest = str(d.get("destination", "")).lower()
                src = str(d.get("user", "")).lower()
                if t in ("subAccountTransfer", "internalTransfer", "send"):
                    signed = amt if dest == addr else (-amt if src == addr else 0.0)
                elif t in ("deposit",):
                    signed = amt
                elif t in ("withdraw",):
                    signed = -amt - float(d.get("fee", 0) or 0)
                elif t == "activateDexAbstraction":
                    signed = -amt  # a fee charged to the account
                else:
                    signed = 0.0
                recs.append(
                    {
                        "season": row["season"],
                        "competition_id": row["competition_id"],
                        "model": row["model"],
                        "tag": tag,
                        "time": e["time"],
                        "type": t,
                        "amount": amt,
                        "signed": signed,
                        "counterparty": src if dest == addr else dest,
                    }
                )
    return pd.DataFrame(recs).sort_values(["tag", "time"]).reset_index(drop=True)


# ------------------------------------------------------------------ round trips
def round_trips(fills: pd.DataFrame) -> pd.DataFrame:
    """A round trip is a flat -> non-flat -> flat cycle in one coin."""
    out = []
    for (tag, coin), g in fills.groupby(["tag", "coin"], sort=False):
        g = g.sort_values(["time", "tid"])
        pos = 0.0
        cur = None
        for r in g.itertuples():
            if abs(pos) < 1e-12:
                cur = {
                    "tag": tag,
                    "season": r.season,
                    "competition_id": r.competition_id,
                    "model": r.model,
                    "coin": coin,
                    "entry_time": r.time,
                    "entry_px": r.px,
                    "side": 1 if r.signed_sz > 0 else -1,
                    "fills": 0,
                    "pnl": 0.0,
                    "fee": 0.0,
                    "max_abs_sz": 0.0,
                    "notional": 0.0,
                }
            pos += r.signed_sz
            cur["fills"] += 1
            cur["pnl"] += r.closed_pnl
            cur["fee"] += r.fee
            cur["max_abs_sz"] = max(cur["max_abs_sz"], abs(pos))
            cur["notional"] = max(cur["notional"], abs(pos) * r.px)
            if abs(pos) < 1e-9:
                pos = 0.0
                cur["exit_time"] = r.time
                cur["exit_px"] = r.px
                cur["hold_ms"] = cur["exit_time"] - cur["entry_time"]
                cur["closed"] = True
                out.append(cur)
                cur = None
        if cur is not None:  # still open at the end of the window
            cur["exit_time"] = int(g["time"].iloc[-1])
            cur["exit_px"] = float(g["px"].iloc[-1])
            cur["hold_ms"] = cur["exit_time"] - cur["entry_time"]
            cur["closed"] = False
            out.append(cur)
    return pd.DataFrame(out)


# ------------------------------------------------------------- 5-minute panel
def price_series(fills: pd.DataFrame, grid: np.ndarray) -> pd.DataFrame:
    """Last-trade price per coin on the grid.

    Hyperliquid will not serve 5m or 1h candles this far back (see
    data/derived/candle_probe.json), so marks come from the pooled fill prints
    of all 38 arena wallets and are forward-filled. This is the last observed
    print among these accounts, not the venue-wide last price or an oracle
    mark; stale prints and counterfactual endpoint uncertainty remain.
    """
    cols = {}
    for coin, g in fills.groupby("coin"):
        # Deterministic same-millisecond convention: highest trade id, then
        # price. Multiple accounts can record the same trade, and sorting
        # only by time leaves the selected pooled print implementation-dependent.
        # Equal time/id/price rows imply the same mark and may be collapsed.
        g = (g.sort_values(["time", "tid", "px"], kind="mergesort")
             .drop_duplicates(subset=["time"], keep="last"))
        idx = np.searchsorted(g["time"].to_numpy(), grid, side="right") - 1
        px = np.where(idx >= 0, g["px"].to_numpy()[np.clip(idx, 0, None)], np.nan)
        cols[coin] = px
    return pd.DataFrame(cols, index=grid)


def panel(fills: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Signed size and signed notional per (tag, coin) on a 5-minute grid."""
    frames = []
    for season, sf in fills.groupby("season"):
        lo = int(sf["time"].min()) // GRID_MS * GRID_MS
        hi = int(sf["time"].max()) // GRID_MS * GRID_MS + GRID_MS
        grid = np.arange(lo, hi + GRID_MS, GRID_MS, dtype=np.int64)
        px = price_series(sf, grid)
        for (tag, coin), g in sf.groupby(["tag", "coin"], sort=False):
            g = g.sort_values(["time", "tid"])
            cum = g["signed_sz"].cumsum().to_numpy()
            t = g["time"].to_numpy()
            idx = np.searchsorted(t, grid, side="right") - 1
            size = np.where(idx >= 0, cum[np.clip(idx, 0, None)], 0.0)
            size = np.where(np.abs(size) < 1e-12, 0.0, size)
            meta = g.iloc[0]
            frames.append(
                pd.DataFrame(
                    {
                        "season": season,
                        "competition_id": meta["competition_id"],
                        "model": meta["model"],
                        "tag": tag,
                        "coin": coin,
                        "t": grid,
                        "signed_size": size,
                        "px": px[coin].to_numpy(),
                    }
                )
            )
    pan = pd.concat(frames, ignore_index=True)
    pan["signed_notional"] = pan["signed_size"] * pan["px"]
    return pan, pan


# ----------------------------------------------------------------- equity curve
def equity(fills: pd.DataFrame, funding: pd.DataFrame, pan: pd.DataFrame) -> pd.DataFrame:
    """equity = start capital + realised pnl - fees + funding + mark-to-market.

    Start capital is the organiser-stated $10,000 per run (nav_since_inception),
    not a ledger-derived figure, so the curve is comparable to the published one.
    Public tips and end-of-season sweeps are excluded by construction.
    Funding retains the recorded timestamp-booking convention, including
    historical daily aggregates at their labeled timestamps. This baseline
    is not exact intraday cash equity; funding_hourly_sensitivity.py separately
    replaces that booking with an explicitly labeled hourly oracle proxy.
    """
    out = []
    for (season, tag), g in fills.groupby(["season", "tag"], sort=False):
        sub = pan[pan["tag"] == tag]
        grid = np.sort(sub["t"].unique())
        g = g.sort_values(["time", "tid"])
        t = g["time"].to_numpy()
        idx = np.searchsorted(t, grid, side="right") - 1

        def cum(col):
            c = g[col].cumsum().to_numpy()
            return np.where(idx >= 0, c[np.clip(idx, 0, None)], 0.0)

        realised = cum("closed_pnl")
        fees = cum("fee")

        fu = funding[funding["tag"] == tag].sort_values("time")
        if len(fu):
            ft = fu["time"].to_numpy()
            fc = fu["usdc"].cumsum().to_numpy()
            fi = np.searchsorted(ft, grid, side="right") - 1
            fund = np.where(fi >= 0, fc[np.clip(fi, 0, None)], 0.0)
        else:
            fund = np.zeros(len(grid))

        # mark-to-market of open positions: sum over coins of size*(px - vwap_open)
        mtm = np.zeros(len(grid))
        for coin, cg in sub.groupby("coin"):
            cg = cg.sort_values("t")
            fg = g[g["coin"] == coin].sort_values(["time", "tid"])
            # running average entry price of the open position
            pos, avg, avgs = 0.0, 0.0, []
            for r in fg.itertuples():
                new = pos + r.signed_sz
                if pos == 0 or (pos > 0) != (new > 0) and new != 0:
                    avg = r.px
                elif abs(new) > abs(pos):  # adding
                    avg = (avg * abs(pos) + r.px * abs(r.signed_sz)) / abs(new)
                pos = 0.0 if abs(new) < 1e-12 else new
                avgs.append(avg)
            fg = fg.assign(avg_px=avgs)
            ii = np.searchsorted(fg["time"].to_numpy(), grid, side="right") - 1
            a = np.where(ii >= 0, fg["avg_px"].to_numpy()[np.clip(ii, 0, None)], np.nan)
            sz = cg["signed_size"].to_numpy()
            p = cg["px"].to_numpy()
            mtm += np.nan_to_num(sz * (p - a))

        eq = 10000.0 + realised - fees + fund + mtm
        meta = g.iloc[0]
        out.append(
            pd.DataFrame(
                {
                    "season": season,
                    "competition_id": meta["competition_id"],
                    "model": meta["model"],
                    "tag": tag,
                    "t": grid,
                    "realised": realised,
                    "fees": fees,
                    "funding": fund,
                    "mtm": mtm,
                    "equity": eq,
                }
            )
        )
    return pd.concat(out, ignore_index=True)


def main() -> None:
    os.makedirs(DER, exist_ok=True)
    print("loading fills ...", flush=True)
    fills = load_fills()
    print(f"  {len(fills):,} fills, {fills['tag'].nunique()} wallets")
    funding = load_funding()
    print(f"  {len(funding):,} funding rows")
    ledger = load_ledger()
    print(f"  {len(ledger):,} ledger rows")

    rt = round_trips(fills)
    print(f"  {len(rt):,} round trips")
    pan, _ = panel(fills)
    print(f"  panel {len(pan):,} rows")
    eq = equity(fills, funding, pan)
    print(f"  equity {len(eq):,} rows")

    for name, df in [
        ("fills", fills),
        ("funding", funding),
        ("ledger", ledger),
        ("roundtrips", rt),
        ("panel", pan),
        ("equity", eq),
    ]:
        df.to_parquet(os.path.join(DER, f"{name}.parquet"), index=False)
        print(f"  wrote {name}.parquet {len(df):,}")


if __name__ == "__main__":
    main()
