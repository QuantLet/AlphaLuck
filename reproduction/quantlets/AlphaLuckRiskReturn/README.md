# AlphaLuckRiskReturn

Descriptive volatility-return associations at model and account levels in a short live competition. Volatility is scaled by initial capital; account ranks are formed separately within each observed arm.

Run from this folder:

```sh
python AlphaLuckRiskReturn.py
```

The `data/` files and local `style.py` are sufficient. Install the repository requirements first. The output is a PNG preview and a vector PDF. This is a descriptive reproduction of one observed competition, not a trading recommendation or a replicated skill test.

The included CSV files retain only the rows and columns used by this Quantlet. The risk-return correlation is recomputed from the supplied account data.
