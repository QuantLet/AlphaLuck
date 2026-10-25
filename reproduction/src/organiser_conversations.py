"""Descriptive summary of the organiser's conversations feed (6 December 2025).

Run: python src/organiser_conversations.py [--archive PATH] [--output PATH]

Input: data/raw/nof1_hourly/conversations_6dec.zip (conversations_raw.json),
the 100 records returned by https://www.alphaarena.ai/api/conversations. The
endpoint ignores paging parameters and returns only decisions from about
13:31-13:51 UTC on 6 December 2025, three days after the official close, so
the records describe the continuation and not the season. Nothing here is
used as evidence on in-season rules, information sets or behaviour; the
summary documents what was retrievable and how often a decision changed a
position in that window.

Writes data/derived/conversations_6dec.json.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path,
                        default=ROOT / 'data/raw/nof1_hourly/conversations_6dec.zip')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/derived')
    args = parser.parse_args()
    with zipfile.ZipFile(args.archive) as z:
        name = next(n for n in z.namelist() if n.endswith('conversations_raw.json'))
        payload = json.loads(z.read(name))
    records = payload['conversations'] if isinstance(payload, dict) else payload
    r = pd.DataFrame(records)
    r['t'] = r['timestamp'].astype(float)
    signals = []
    for x in records:
        response = x['llm_response']
        if isinstance(response, str):
            response = ast.literal_eval(response)
        signals.extend(v.get('signal') for v in response.values())
    signals = pd.Series(signals)
    gaps = r.sort_values('t').groupby('run_id').t.diff().dropna() / 60
    later = pd.Timestamp('2025-12-03 22:00', tz='UTC')
    report = {
        'archive_sha256': hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        'records': int(len(r)), 'accounts': int(r.run_id.nunique()),
        'first_utc': str(pd.to_datetime(r.t.min(), unit='s')),
        'last_utc': str(pd.to_datetime(r.t.max(), unit='s')),
        'days_after_official_close': float(
            (pd.to_datetime(r.t.min(), unit='s', utc=True) - later).total_seconds() / 86_400),
        'records_by_competition': {str(k): int(v) for k, v in
                                   r.competition_id.astype(int).value_counts().sort_index().items()},
        'instrument_decisions': int(len(signals)),
        'signals': {str(k): int(v) for k, v in signals.value_counts().items()},
        'hold_share': float((signals == 'hold').mean()),
        'decision_interval_minutes': {
            'intervals': int(len(gaps)), 'median': float(gaps.median()),
            'min': float(gaps.min()), 'max': float(gaps.max())},
        'median_prompt_characters': float(np.median(r.user_prompt.str.len())),
        'interpretation': 'Post-season continuation records only; not evidence on '
                          'in-season prompts, information sets or causal effects of '
                          'competition design.',
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'conversations_6dec.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
