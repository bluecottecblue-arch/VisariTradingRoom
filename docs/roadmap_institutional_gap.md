# VisariTradingRoom — Institutional Gap Roadmap

## Cosa fa già bene la piattaforma

- intake e parsing con fail-fast su strategie non codificabili
- formalizzazione algoritmica con output strutturato
- generazione MQL5 solo se la strategia supera i gate minimi
- backtest con split temporale, Monte Carlo, walk-forward e bias check
- research verdict strutturato con statistiche, robustezza, regime e rischio
- export bloccato se verdict o codice non sono sufficienti

## Cosa replica bene di una pipeline hedge-fund-like

- separazione esplicita tra idea, specifica, backtest e review
- uso di out-of-sample come riferimento principale
- stress di costi e robustness locale
- analisi per regime e review del rischio
- audit trail minimo con snapshot di config, metriche e verdict

## Cosa manca ancora rispetto a una struttura istituzionale

### Portfolio construction

- nessuna allocazione multi-strategy
- nessun controllo di correlazione tra strategie
- nessun budget di rischio per cluster o sleeve

### Execution modeling

- il backtest usa ancora un adapter proxy e non una traduzione completa della formal spec
- modellazione slippage semplice, non order-book aware
- niente latency / queue position modeling

### Research governance

- nessun approval workflow multi-utente
- nessuna firma/versioning rigoroso dei dataset
- nessuna persistenza forte di audit trail e risultati

### Live monitoring

- nessun monitoraggio live di drift
- nessun confronto live vs expected distribution
- nessun alerting operativo

### Production risk governance

- nessun kill switch centralizzato di portafoglio
- nessun controllo intraday aggregato multi-broker/multi-symbol
- nessuna segregation tra research, staging e production

## Priorità realistiche

1. Collegare il backtest alla formal spec reale invece del proxy adapter.
2. Salvare risultati e sessioni in storage persistente.
3. Introdurre portfolio/risk aggregation multi-strategy.
4. Aggiungere drift detection e monitoring live.
5. Migliorare execution modeling su dati tick/bid-ask.
