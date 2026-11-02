from analyze_history import *

def main():
    h=json.loads((OUT/'history_summary.json').read_text())['models']
    c=json.loads((OUT/'cash_reconciliation.json').read_text())
    p=json.loads((OUT/'positions_reconciliation.json').read_text())
    f=json.loads((OUT/'replication_feasibility.json').read_text())['models']
    names={'glm-4.7':'GLM','claude-opus-4-5-20251101':'Claude','gemini-3-pro-preview':'Gemini','gpt-5.2':'GPT','mystery-model-alpha':'Mystery'}
    rows=[]
    for x in h:
        model=x['model_id'];cc=next(y for y in c if y['model_id']==model);pp=next(y for y in p if y['model_id']==model);ff=next(y for y in f if y['model_id']==model)
        b=ff['trading_minus_holding_value_bounds_before_POL_gas']
        rows.append({'model':names[model],'model_id':model,'wallet':x['wallet'],
          'reported_orders':x['operator_orders'],'independently_linked_orders':x['operator_orders_found'],
          'all_independent_executed_orders':x['independent_fill_events'],
          'unlinked_orders_after_formation':ff['unlinked_orders_after_formation'],
          'redemption_events':x['redemption_events'],'positive_redemptions':x['redemption_positive_events'],
          'redemption_proceeds_USDCE':x['redemption_total_USDCE'],
          'initial_stablecoin_cash':str(D(cc['checkpoints']['start']['USDC'])+D(cc['checkpoints']['start']['USDCE'])),
          'formation_cash_USDCE':cc['checkpoints']['formation']['USDCE'],
          'endpoint_cash_USDC':cc['checkpoints']['endpoint']['USDC'],
          'endpoint_cash_USDCE':cc['checkpoints']['endpoint']['USDCE'],
          'external_funding_since_start':cc['external_funding_since_start'],
          'wallet_gas_POL':str(D(x['wallet_paid_gas_POL_study_period']).quantize(D('.00000001'))),
          'rounded_gas_rows':x['wallet_paid_gas_rows_with_rounded_fee'],
          'formation_assets':len(pp['formation_positions_raw']),
          'endpoint_assets_including_dust':len(pp['endpoint_positions_raw']),
          'cash_quantity_ledger_reconciled':ff['cash_and_quantity_ledgers_reconciled'],
          'incremental_terminal_wealth_lower_USD_before_POL_gas':b['lower_USD_at_stablecoin_parity'],
          'incremental_terminal_wealth_upper_USD_before_POL_gas':b['upper_USD_at_stablecoin_parity'],
          'unknown_endpoint_marks':ff['unknown_endpoint_mark_count'],
          'returns_computed':False})
    with (OUT/'wallet_summary.csv').open('w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    lines=['PREDICTION ARENA — ISTORICUL INDEPENDENT AL CELOR CINCI WALLETURI',
      'Audit încheiat la 1 noiembrie 2026','',
      'Concluzie',
      'Am reconstruit numerarul în USDC și USDC.e, execuțiile și cantitățile deținute pentru toate cele cinci walleturi în perioada analizată. Alimentările, conversiile și decontările pot fi separate de rezultatul tranzacționării. Blocajul legat de istoricul conturilor a fost depășit.',
      'Datele permit continuarea unei replicări pe GLM, Claude, Gemini și mystery-model-alpha, folosind execuțiile confirmate. GPT trebuie tratat separat: are o tranzacție după formarea portofoliului care nu poate fi legată de jurnalul LLM disponibil. Nu avem încă o replicare completă a randamentelor din articol: lipsesc unele evaluări de piață la data finală și conversia istorică în dolari a taxelor plătite în POL.',
      '', 'Perioada și comparația',
      'Fereastra de verificare a evenimentelor: 1 februarie – 9 martie 2026 inclusiv. Începutul comun observat în auditul precedent: 9 februarie, 03:45:09 UTC. Portofoliul holding este fixat după 24 de ore, la 10 februarie, 03:45:09 UTC; evaluarea finală este la 10 martie, 00:00 UTC. Începutul comun rămâne un reper al arhivei disponibile, nu o dată de lansare certificată independent.',
      'Exporturile exploratoarelor acoperă și activitatea din afara acestui interval. Numai perioada de studiu a fost reconciliată integral. În calcule nu intră ordinele paper.',
      '', 'Ce am obținut',
      'Arhiva Envio/Hugging Face: 474 de execuții ale celor cinci walleturi și 202 evenimente de decontare. Dintre decontări, 21 au plată pozitivă, în total 284,782866 USDC.e; celelalte nu sunt venituri. Exporturile PolygonScan includ 506 transferuri de poziții în fereastra analizată: 474 asociate tranzacțiilor și 32 retrageri de poziții la decontare. Diferența față de cele 202 evenimente vine din apelurile repetate ori fără poziții de retras.',
      'Toate cele 536 de perechi tranzacție–monedă din registrul numerarului au o valoare identificată. Nu mai există solduri parțiale negative sau diferențe neexplicate între sursele folosite. Toate transferurile de cantități din perioada analizată au fost reconciliate.',
      '', 'Model | Ordine raportate | Confirmate și legate de jurnal | Execuții totale | Decontări cu plată']
    for x in rows:lines.append(f"{x['model']} | {x['reported_orders']} | {x['independently_linked_orders']} | {x['all_independent_executed_orders']} | {x['positive_redemptions']}")
    lines += ['',
      'Cinci ordine raportate ca matched nu au execuție în arhiva independentă, iar PolygonScan nu găsește tranzacțiile indicate: trei pentru Gemini și două pentru GPT. Le păstrăm ca neconfirmate, fără să le includem în tranzacțiile realizate. Această constatare nu dovedește falsificarea jurnalului.',
      'La șase ordine confirmate, cantitatea ori suma din jurnal diferă de execuția independentă, sau cantitatea lipsește. Registrul reconstruit folosește valorile executate. Cele șase ordine GPT fără legătură cu jurnalul sunt cinci înainte de formare și unul la 11 februarie, 18:35:27 UTC, după formare.',
      '', 'Capitalul real și alimentările',
      'Soldurile de mai jos sunt numerar, nu averea totală: la final există și poziții. Sumele USDC și USDC.e sunt adunate la paritate pentru prezentare. Cei 10.000 USD din jurnal nu reprezintă depunerile efective observate în aceste walleturi.',
      'Model | Numerar la început | Alimentări ulterioare | Numerar final USDC | Numerar final USDC.e']
    for x in rows:lines.append(f"{x['model']} | {x['initial_stablecoin_cash']} | {x['external_funding_since_start']} | {x['endpoint_cash_USDC']} | {x['endpoint_cash_USDCE']}")
    lines += ['',
      'Fiecare cont a primit aproximativ 297,42 USDC în timpul experimentului. Această sumă trebuie acordată și portofoliului holding, la aceeași dată. GLM a păstrat alimentarea în USDC; nu trebuie confundată cu disponibilul USDC.e folosit de exchange. Conversiile între monede și costul lor sunt păstrate separat. Nu au fost identificate retrageri externe de stablecoins în perioada de studiu.',
      '', 'Comisioanele',
      'Evenimentele celor 474 de execuții au fee egal cu zero. Cantitățile și transferurile monetare confirmă această constatare pentru intervalul analizat. Există mici restituiri de o milionime de USDC.e la unele cumpărări; ele sunt incluse distinct în registru și nu sunt confundate cu evenimentele FeeRefunded.',
      'Taxele de rețea sunt contabilizate o singură dată pentru fiecare tranzacție și numai dacă expeditorul este walletul agentului. Taxa totală a unei tranzacții plătite de exchange sau de alt expeditor nu este imputată agentului.',
      'Model | Taxe suportate de wallet în POL, 9 februarie – 9 martie | Rânduri cu taxă afișată la 8 zecimale']
    for x in rows:lines.append(f"{x['model']} | {x['wallet_gas_POL']} | {x['rounded_gas_rows']}")
    lines += ['',
      'Taxele exacte sunt păstrate unde sunt disponibile. Pentru restul, sursa afișează opt zecimale în POL; incertitudinea cumulată este sub 0,000001 POL. Nu am folosit cotația POL din noiembrie pentru tranzacțiile din februarie–martie. Registrul nu reprezintă o evaluare completă în dolari a soldului nativ POL.',
      '', 'Ce putem spune deja despre trading față de holding',
      'Putem delimita diferența de avere finală chiar înainte de a recupera toate prețurile. Pentru contractele cu dovadă de decontare înainte de data finală folosim plata contractuală. Pentru restul lăsăm valoarea între zero și un dolar. Același token are același preț în ambele portofolii. Depunerile ulterioare sunt identice, iar costurile conversiilor efectuate rămân în portofoliul tranzacționat.',
      'Aceste intervale nu sunt randamente estimate, intervale de încredere sau rezultate nete de taxele de rețea în dolari. Ele presupun USDC = USDC.e = 1 USD și exclud evaluarea soldului POL. Nu cuantifică incertitudinea de eșantionare.',
      'Model | Diferența finală trading minus holding, USD, înainte de taxele în POL']
    for x in rows:lines.append(f"{x['model']} | [{x['incremental_terminal_wealth_lower_USD_before_POL_gas']}; {x['incremental_terminal_wealth_upper_USD_before_POL_gas']}]")
    lines += ['',
      'În aceste condiții, semnul este stabil pentru trei agenți: GLM este peste holding, iar Claude și mystery-model-alpha sunt sub holding. Pentru Gemini, intervalul include ambele situații. Rezultatul GPT descrie walletul, nu exclusiv deciziile LLM identificabile.',
      '', 'Ce mai trebuie pentru replicarea completă',
      '1. Prețuri istorice comparabile pentru evaluarea portofoliilor la formare și la închidere, ori dovezi suplimentare că anumite contracte erau deja decontate. Lista exactă a tokenurilor fără evaluare finală este în results/replication_feasibility.json.',
      '2. Cotații istorice POL/USD și o regulă comună pentru costurile scenariului holding. Taxele în POL sunt deja colectate.',
      '3. O definiție a randamentului care tratează alimentările intermediare identic. Diferența de avere finală calculată aici evită atribuirea depunerilor tranzacționării, dar nu înlocuiește rata de rentabilitate.',
      '4. GPT exclus din comparația principală până la identificarea ordinului fără jurnal de după formare; poate rămâne într-o analiză separată a walletului.',
      '', 'Surse și limite de colectare',
      'Datele independente provin din arhiva Polygon indexată de Envio (CC BY 4.0), din PolygonScan și din Blockscout. Adresele asociate modelelor provin din Prediction Arena; blockchainul confirmă activitatea adreselor, nu identitatea modelului care a semnat o decizie.',
      'https://huggingface.co/datasets/moose-code/polymarket-onchain-v1',
      'Versiunea arhivei: 7eeb860dea5b79d5c74f3182b70bd08c85c8f833; evenimente până la 24 aprilie 2026, 07:43:41 UTC. Au fost verificate toate grupurile relevante din lunile februarie și martie, cu filtrare înainte de 10 martie. Starea ulterioară a contractelor nu este tratată singură ca dovadă de decontare înainte de închidere.',
      'https://github.com/enviodev/polymarket-indexer',
      'https://github.com/gnosis/conditional-tokens-contracts/blob/master/contracts/ConditionalTokens.sol',
      'Contractul permite decontarea numai după stabilirea plății, iar plata nu poate fi rescrisă ulterior. De aceea un eveniment de decontare din interval, inclusiv cu plată zero, stabilește că rezultatul era cunoscut până atunci.',
      'https://polygonscan.com/  |  https://polygon.blockscout.com/',
      'Exporturile Blockscout singure sunt incomplete pentru aceste conturi. Exportul rapid PolygonScan rotunjește unele sume, iar exportul pozițiilor lasă coloana Item goală. Sumele au fost completate din evenimentele independente și din detalii de tranzacție; tokenurile tranzacționate au fost identificate prin execuții. Pentru retragerile de poziții, identificarea folosește o potrivire unică a cantității în cadrul contractului decontat, verificată și prin suma plătită. Originea fiecărei valori este păstrată în rezultate.',
      'Exportul complet PolygonScan cere CAPTCHA și nu a fost utilizat; au fost folosite exporturile publice ale fiecărei pagini. Nu s-au creat conturi și nu s-au folosit chei private. Transferurile fără valoare și tokenurile spam pot fi ascunse implicit în interfață; analiza monetară include numai cele două contracte autentice USDC. Nu este o certificare a tuturor activelor posibile ale adreselor.',
      '', 'Fișiere utile',
      'results/wallet_summary.csv — sinteza celor cinci conturi.',
      'results/cash_ledger.json și positions_ledger.json — registrele reconstruite.',
      'results/network_fees.json și redemptions_crosschecked.json — taxe și decontări.',
      'results/order_linkage.json — fiecare ordin raportat și verificarea sa independentă.',
      'results/replication_feasibility.json — intervalele comparative și evaluările încă lipsă.',
      'blockscout/ și polygonscan/ — exporturile originale; extracted/ — evenimentele independente extrase.',
      '', 'Validare: 10 teste trecute. Articolul, anexa, cover letter, highlights și arhiva Overleaf nu au fost modificate. Auditul precedent este păstrat separat.']
    (ROOT/'Raport_istoric_independent.txt').write_text('\n'.join(lines)+'\n')
    (ROOT/'README.txt').write_text('Prediction Arena independent wallet audit — 2026-11-01\n\nRead Raport_istoric_independent.txt first.\n\nData attribution: Envio / moose-code, Polymarket On-Chain Complete v1 Dataset, CC BY 4.0, https://huggingface.co/datasets/moose-code/polymarket-onchain-v1 . Extracted and transformed for the five listed wallets. Explorer data: PolygonScan and Blockscout; original CSVs preserved.\n\nRe-run saved-data analysis with Python 3 (standard library):\n  python analyze_history.py\n  python reconcile_cash.py\n  python reconcile_positions.py\n  python assess_replication.py\n  python test_history.py\n  python build_delivery.py\n\nRe-fetch archive: Python 3 plus pyarrow; run extract_archive.py, then extract_conditions.py after analysis has identified redemption conditions. The first scanner resumes completed row groups. Its pinned source revision is in range_reader.py. The original collection used a locally intercepted HTTPS connection. Public collectors now verify certificates; archived responses remain unchanged.\n\nBrowser export: open each wallet on Blockscout; export token transfers and transactions from 2020-01-01 to retrieval date. On PolygonScan open token transfers, transactions and NFT transfers; select 100 rows and download every page using Download Page Data. Export names, pages and coverage are recorded in polygonscan/export_manifest.json and blockscout/export_manifest.json. Quick token exports truncate some amounts; do not use them alone for a precise balance. Exact details for four missing cash transactions were read separately and saved.\n\nThe operator_inputs directory contains derived order records and the prior benchmark diagnostic. The complete decision/event source archive remains in 2026 AlphaLuck/archives/AlphaLuck_PredictionArena_audit_20261101.zip; this new archive does not replace it.\n\nNo point returns are produced. Wealth bounds use equal external cash flows, stablecoin parity, common prices for common tokens, and pre-endpoint settlement evidence. POL inventory and its USD valuation are outside those bounds.\n')

if __name__=='__main__':main()
