from calculate_replication import *
SHORT={'glm-4.7':'GLM','claude-opus-4-5-20251101':'Claude','gemini-3-pro-preview':'Gemini','gpt-5.2':'GPT','mystery-model-alpha':'Mystery'}
def f(x):return f'{D(x):.2f}'
def main():
    result=read(OUT/'replication_results.json')['models'];twr=read(OUT/'time_weighted_returns.json')['models'];marks=read(OUT/'valuation_marks.json');gasrows=read(OUT/'gas_valued.json')
    table=[];summary=[]
    for r in result:
        t=next(x for x in twr if x['model_id']==r['model_id']);b=r['value_difference_bounds_net_gas']['max_trade_age_1h']
        table.append(f"{SHORT[r['model_id']]} | {f(r['actual_terminal_wealth_net_gas'])} | {f(r['holding_terminal_wealth'])} | {f(r['trading_minus_holding_USDC_net_gas'])} | {f(t['trading_TWR_pct_transaction_marks'])}% | {f(t['holding_TWR_pct_transaction_marks'])}%")
        summary.append({'model':SHORT[r['model_id']],'model_id':r['model_id'],'primary_sample':r['primary_attribution_candidate'],'trading_terminal_wealth_USD_net_gas':r['actual_terminal_wealth_net_gas'],'holding_terminal_wealth_USD':r['holding_terminal_wealth'],'trading_minus_holding_USD':r['trading_minus_holding_USDC_net_gas'],'trading_TWR_pct_estimated':t['trading_TWR_pct_transaction_marks'],'holding_TWR_pct_estimated':t['holding_TWR_pct_transaction_marks'],'post_formation_gas_USD':r['post_formation_gas_USDC'],'difference_lower_if_marks_over_1h_unknown_USD':b['lower_USDC'],'difference_upper_if_marks_over_1h_unknown_USD':b['upper_USDC']})
    with (OUT/'comparison.csv').open('w') as file:
        w=csv.DictWriter(file,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    bounds='\n'.join(f"{SHORT[r['model_id']]} | [{f(r['value_difference_bounds_net_gas']['settlement_only']['lower_USDC'])}; {f(r['value_difference_bounds_net_gas']['settlement_only']['upper_USDC'])}] | [{f(r['value_difference_bounds_net_gas']['max_trade_age_1h']['lower_USDC'])}; {f(r['value_difference_bounds_net_gas']['max_trade_age_1h']['upper_USDC'])}]" for r in result)
    ages='\n'.join(f"{SHORT[r['model_id']]} | {D(r['formation_price_max_age_seconds'])/3600:.2f} | {D(next(t for t in twr if t['model_id']==r['model_id'])['funding_mark_max_age_seconds'])/3600:.2f} | {D(r['endpoint_price_max_age_seconds'])/3600:.2f}" for r in result)
    md='\n'.join(f"{SHORT[r['model_id']]} | {f(r['trading_modified_dietz_pct'])}% | {f(r['holding_modified_dietz_pct'])}%" for r in result)
    report=f'''PREDICTION ARENA — COMPARAȚIA TRADING VERSUS HOLDING
Rezultate și verificări, 2 noiembrie 2026

Concluzie
Datele permit acum o replicare descriptivă a comparației, folosind istoricul independent al conturilor și prețuri din tranzacții. Pentru cele patru conturi cu execuțiile atribuibile jurnalelor disponibile, trading aduce mai multă avere finală decât holding numai în cazul GLM. Claude, Gemini și mystery-model-alpha încheie cu mai puțin. Randamentele calculate separat înainte și după alimentare păstrează aceeași ordine. GPT este raportat separat: recuperarea prețurilor nu rezolvă lipsa unei decizii pentru ordinul său suplimentar de după formare.
Rezultatele sunt condiționate de evaluarea la prețuri de tranzacție, de paritatea stablecoinurilor și de definiția perioadei. Nu reprezintă prețuri garantate de lichidare ori dovada unui avantaj general al holdingului.

Rezultatul principal
Portofoliile sunt fixate la 10 februarie 2026, 03:45:09.366855 UTC, după primele 24 de ore ale ferestrei comune observate. Închiderea este la 10 martie 2026, 00:00 UTC, exclusiv. Fiecare portofoliu holding păstrează pozițiile și numerarul de la formare și primește exact aceeași alimentare ulterioară, la aceeași dată. Alimentarea rămâne numerar; nu se cumpără poziții suplimentare.
Valorile finale includ numerarul și pozițiile încă deținute. Contractele decontate sunt evaluate la plata contractuală, chiar dacă titlul nu a fost încă răscumpărat. Pentru celelalte folosim ultima tranzacție anterioară închiderii. Costul conversiilor USDC/USDC.e este deja în numerarul efectiv. Taxele POL plătite de wallet după formare sunt deduse separat, o singură dată.

Model | Avere finală trading, USD | Avere finală holding, USD | Trading minus holding, USD | TWR trading estimat | TWR holding estimat
{chr(10).join(table)}

GPT nu intră în grupul principal. Mystery păstrează eticheta din arhiva deciziilor. Toate sumele în dolari presupun USDC = USDC.e = 1 USD. Acestea sunt valorile segmentului de portofoliu format din numerar stabil și contracte de predicție, după costurile de rețea; nu includ câștigul sau pierderea din deținerea POL ca activ.

Cum sunt tratate depunerile
Fiecare wallet a primit aproximativ 297,42 USDC pe 14 februarie, mult peste capitalul de la formare. O variație procentuală simplă a soldului ar atribui depunerea tranzacționării. Am evaluat separat portofoliul imediat înaintea alimentării fiecărui cont și am legat geometric randamentele celor două subperioade:
R = (V înainte de alimentare / V la formare) × (V final / (V înainte de alimentare + alimentare)) − 1.
TWR în tabel înseamnă acest randament ponderat în timp, estimat pe baza prețurilor de tranzacție. Datele exacte ale celor cinci alimentări diferă; fiecare calcul folosește data walletului respectiv. Valoarea holding este evaluată la aceeași dată. Taxele de rețea sunt tratate ca o cheltuială cumulată a segmentului analizat. Nu este presupusă vânzarea efectivă de USDC pentru a plăti POL.
Diferența de avere finală măsoară rezultatul în bani al celor două politici cu aceleași alimentări. TWR acordă aceeași importanță unei unități de capital în fiecare subperioadă. De aceea un TWR pozitiv poate coexista cu un rezultat monetar total negativ: de exemplu, GLM a avut rezultate diferite înainte și după creșterea capitalului. Nu comparăm direct nivelul TWR cu profitul raportat la totalul sumelor depuse.
Ca verificare separată am păstrat și Modified Dietz, care aproximează tratarea fluxurilor folosind durata lor în portofoliu. Nu este măsura principală aici, deoarece alimentarea este mare:
Model | Modified Dietz trading | Modified Dietz holding
{md}

Ce date noi au fost recuperate
— Toate cele șase tokenuri distincte deținute la formare au un preț observat anterior formării.
— Toate cele 93 de tokenuri distincte din reuniunea portofoliilor de la formare și închidere pot fi evaluate: 48 prin decontări demonstrate înainte de închidere și 45 prin tranzacții anterioare.
— Scanarea decontărilor pentru contractele relevante a identificat 48.376 de evenimente, provenite de la toate adresele, pentru 44 de condiții. Acestea sunt dovezi privind momentul rezolvării, nu încasări ale celor cinci agenți.
— Pentru evaluări au fost extrase 17.764 de evenimente de execuție din fereastra formării, 19.817 din fereastra alimentării și 15.182 din fereastra închiderii. Sunt evenimente de piață, nu numere de ordine LLM. Pot include reprezentarea individuală și agregată a aceleiași execuții; evaluarea elimină această dublare.
— Seriile POL/USDC la un minut pentru februarie și martie permit evaluarea tuturor taxelor relevante. Se folosește închiderea ultimului minut complet anterior tranzacției, fără prețuri din viitor. Costurile după formare sunt sub 0,57 USD pentru fiecare wallet.

Evaluarea contractelor și vechimea prețurilor
O plată contractuală este utilizată numai dacă există un eveniment de răscumpărare anterior momentului evaluării. Inclusiv un eveniment cu plată zero confirmă că rezultatul fusese stabilit. Valorile de rezolvare din fotografia arhivei din aprilie nu sunt folosite singure pentru a atribui retrospectiv rezultate în februarie sau martie.
Pentru contractele fără această dovadă, evaluarea folosește prețul mediu ponderat cu cantitatea din ultima tranzacție disponibilă a tokenului, într-o fereastră anterioară de cel mult 24 de ore. Sunt folosite execuțiile individuale ale ordinelor maker, iar rezumatul ordinului taker numai dacă pentru același token și aceeași tranzacție nu există acele execuții. Datele fiecărui preț și evenimentele folosite sunt păstrate în fișiere.
Prețurile sunt observate în tranzacții. Nu reprezintă mijlocul spreadului, un bid executabil pentru întreaga poziție sau prețuri oficiale de marcare. La formare, un preț Gemini are aproximativ 1,77 ore vechime. La alimentare există și un preț GLM de aproximativ 8,68 ore. Aceste limite contează mai ales pentru estimările procentuale TWR.
Model | Vechime maximă la formare, ore | La alimentare, ore | La închidere, ore
{ages}
Zero în tabel poate însemna că nu există poziții ori că toate valorile relevante sunt plăți contractuale, nu o cotație observată chiar în acel moment.

Verificarea sensibilității
Am recalculat limitele diferenței de avere finală în două variante. Prima folosește numai decontările demonstrate și lasă toate celelalte prețuri între zero și un dolar. A doua păstrează și tranzacțiile din ultima oră, dar lasă liber între zero și un dolar fiecare preț mai vechi. Același token primește același preț în trading și holding. Depunerile, numerarul și taxele rămân identice cu cele din calculul principal.
Model | Numai decontări: interval diferență, USD | Decontări și tranzacții din ultima oră: interval, USD
{bounds}
În a doua variantă, GLM rămâne peste holding, iar Claude, Gemini și Mystery rămân sub holding pentru toate valorile admise ale prețurilor mai vechi. În prima variantă, care nu folosește niciun preț de tranzacție la închidere, semnul Gemini nu este determinat. Intervalele sunt limite de evaluare, nu intervale de încredere. Ele nu acoperă o posibilă abatere de la paritatea stablecoinurilor și nu demonstrează că o poziție putea fi lichidată integral la prețul observat. Rezultatele de sensibilitate privesc diferența de avere finală, nu precizia randamentelor TWR.

Ce poate intra în articol
Comparația este utilă ca verificare suplimentară pe tranzacții efective dintr-o piață diferită. Rezultatul descriptiv este că holding încheie cu mai multă avere pentru trei dintre cele patru conturi atribuibile, iar GLM constituie o excepție. Aș raporta diferența de avere finală, randamentele TWR ca estimări suplimentare și verificarea cu prețurile vechi lăsate necunoscute. Nu aș prezenta această comparație ca o replicare identică a mecanismelor de marjă sau lichidare din piața inițială.
Sunt patru conturi în comparația principală, o singură perioadă și capital efectiv redus. Nu calculăm semnificație statistică din patru observații și nu extrapolăm la profitabilitatea generală a agenților LLM. Data de început comun este un reper al arhivei, nu lansarea certificată a experimentului. Blockchainul verifică activitatea walleturilor; identitatea modelului și legătura cu decizia provin din jurnalele Prediction Arena. Cele cinci ordine raportate fără execuție confirmată rămân excluse. GPT păstrează problema de atribuire documentată în auditul anterior.

Surse și reproducere
Envio / moose-code, Polymarket On-Chain Complete v1, CC BY 4.0. Versiune fixată: 7eeb860dea5b79d5c74f3182b70bd08c85c8f833. Datele au fost extrase și transformate pentru această comparație.
https://huggingface.co/datasets/moose-code/polymarket-onchain-v1
https://github.com/enviodev/polymarket-indexer
https://github.com/gnosis/conditional-tokens-contracts/blob/master/contracts/ConditionalTokens.sol
Binance, date publice POL/USDC, bare la un minut; timpul este în microsecunde UTC în arhiva spot din 2026.
https://github.com/binance/binance-public-data
https://data.binance.vision/data/spot/monthly/klines/POLUSDC/1m/POLUSDC-1m-2026-02.zip
https://data.binance.vision/data/spot/monthly/klines/POLUSDC/1m/POLUSDC-1m-2026-03.zip
Convenții de măsurare a performanței și motivul reevaluării la fluxuri mari:
https://www.gipsstandards.org/standards/gips-standards-for-firms/gips-standards-handbook-for-firms/
Aceste referințe susțin metoda; nu se afirmă conformitate GIPS a studiului.

Fișiere
results/comparison.csv: tabelul sintetic.
results/replication_results.json: numerar, evaluări, Modified Dietz și intervale.
results/time_weighted_returns.json: randamentele pe subperioade și evaluarea înaintea alimentării.
results/valuation_marks.json și funding_valuation_marks.json: fiecare preț și dovada sa.
results/gas_valued.json: taxele în POL și conversia lor.
raw/: evenimentele și prețurile recuperate. independent_inputs/: auditul independent anterior, inclusiv exporturile și registrele.
README.txt: instrucțiuni de refacere a calculelor și limitele accesului la surse.

Validare: 10 verificări automate ale acestei replicări, suplimentar celor 10 ale auditului registrelor. Articolul, anexa și arhiva Overleaf nu au fost modificate în această etapă. Rezultatele precedente sunt păstrate separat.
'''
    (ROOT/'Raport_replicare.txt').write_text(report)
    (ROOT/'README.txt').write_text('''Prediction Arena trading versus holding — 2026-11-02

Read Raport_replicare.txt. Primary outcome: terminal wealth difference with identical external funding. Time-weighted returns use transaction-price valuations at formation, immediately before each wallet's single later deposit, and at the endpoint. Modified Dietz is a secondary comparison. These are valuation proxies, not executable liquidation prices. Assume USDC = USDC.e = USD 1; POL investment return is excluded, while wallet-paid gas is charged as an expense at historical POL/USDC prices.

Recalculate saved-data results (Python 3, standard library):
  python calculate_replication.py
  python calculate_twr.py
  python test_replication.py
  python build_report.py
Re-run earlier ledger checks with: python independent_inputs/test_history.py

Re-fetch public sources (Python 3 and pyarrow):
  python collect_valuations.py
  python collect_prices.py
  python collect_funding_prices.py
Collectors resume saved row groups. The independent archive revision is pinned in independent_inputs/range_reader.py. This runtime required an explicitly unverified TLS context for its intercepted public HTTPS connection; no credentials were sent. Review the connection setup before rerunning elsewhere. Polymarket price-history DNS lookup failed and the Coinbase endpoint returned HTTP 403. Actual price data therefore came from independently indexed on-chain fills and the Binance public archive. initial_access.json preserves those access attempts. The unused POL/USDT probe file is retained as a probe only; all gas calculations use POL/USDC.

Source attribution: Envio / moose-code, Polymarket On-Chain Complete v1, CC BY 4.0, https://huggingface.co/datasets/moose-code/polymarket-onchain-v1 ; extracted and transformed. Binance public spot data: https://github.com/binance/binance-public-data . Earlier explorer inputs: PolygonScan and Blockscout. Original files and source URLs are retained. Full underlying operator decision logs remain in the earlier Prediction Arena audit archive; derived order/linkage records needed here are included in independent_inputs.

The scripts implement the period and assumptions stated in the report. Bounds allow each unknown binary outcome price independently in [0,1], so they may be wider than bounds imposing cross-outcome constraints. Historical redemption evidence, rather than a future state snapshot alone, gates contractual payout valuations. Zero-payout redemption events prove resolution but are not wallet income. Gas is charged only to its payer once. Holding retains settlement claims without forced redemption and has no post-formation trading gas. All comparisons are descriptive; no statistical significance or universal policy ranking is asserted.
''')
    print('Report and comparison table written.')

if __name__=='__main__':main()
