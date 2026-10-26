<div style="margin: 0; padding: 0; text-align: center; border: none;">
<a href="https://quantlet.com" target="_blank" style="text-decoration: none; border: none;">
<img src="https://github.com/StefanGam/test-repo/blob/main/quantlet_design.png?raw=true" alt="Header Image" width="100%" style="margin: 0; padding: 0; display: block; border: none;" />
</a>
</div>

```
Name of Quantlet: AlphaLuckFormationHour

Published in: Trading versus Holding in a Live Language-Model Competition (working paper; not yet published)

Description: Aggregates the Season 1.5 hourly-funded frozen-position accounting comparison for every formation

hour from 1 to 336, to the close and over fixed 1-, 3- and 7-day horizons, and under two margin policies: account-wide maintenance and passive isolated margin with organiser liquidation prices. Checks the aggregates against the upstream reference. It does not replay the exchange, simulate an executable strategy or redistribute organiser data.

Keywords: LLM, trading agents, performance evaluation, frozen positions, formation time, isolated margin, liquidation, sensitivity analysis, reproducibility

Author: Daniel Traian Pele, Diana Ioana Micu, Victor Rareș Curescu

Submitted: 2026-10-19

Datafile: data/sweep_accounts.csv, data/sweep_hours.csv, data/reference.json, data/provenance.json

Input: Derived account-level frozen and realised results for 32 accounts and 336 formation hours, with passive-isolated outcomes and screen flags. Python 3.10 or newer; see requirements.txt.

Output: output/results.json, output/formation_hour.csv, output/formation_hour.png, output/formation_hour.pdf

Example: python AlphaLuckFormationHour.py

```

<div align="center">
  <img src="https://raw.githubusercontent.com/QuantLet/AlphaLuck/main/reproduction/quantlets/AlphaLuckFormationHour/AlphaLuckFormationHour.png" alt="Image" width="600"/>
</div>

