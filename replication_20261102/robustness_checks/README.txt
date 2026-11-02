AlphaLuck robustness checks

Run with Python 3.11 or newer, without packages, credentials or downloads:
  python replay_checks.py
  python cash_formation_sensitivity.py

The first command reproduces arm deletions, model-block sign-flip reference
fractions and cash-closing costs at 24-hour formation. The second recomputes
the cash formation sweep on the same 169 seven-day windows as the frozen
books, and over all 336 formation hours to the common close. Its input uses
recorded equity minus daily-booked funding plus hourly-proxy funding.

To reconstruct the inputs from the full reproduction project (numpy, pandas,
scipy and pyarrow required):
  python analyse_revision.py --root ../../reproduction --out OUTPUT
  python cash_formation_sensitivity.py --root ../../reproduction
The second command replaces its derived input file with the reconstruction.

Gaps are benchmark minus trading, in percentage points of initial capital.
Arm deletion uses retained capital. Model means keep all four arms together.
All 256 model-block sign assignments are enumerated. The sign-flip fractions
require joint sign symmetry, which common market shocks may violate. These
are conditional reference calculations, not evidence from independent markets.

Without closing costs or interest, cash minus trading is simply the negative
of post-formation realised P&L. The cash gap is positive in 124/169 seven-day
windows, and in 123/116 windows with closing charges of 10/100 basis points.
Closing charges are hypothetical costs on formation gross notional.
The windows overlap and their counts do not establish statistical significance.
