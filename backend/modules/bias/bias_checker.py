"""
BiasChecker — Controllo esplicito dei bias metodologici

Questo modulo NON è opzionale. Viene eseguito SEMPRE prima di mostrare
i risultati del backtest all'utente.

Se trova problemi seri, li segnala con severity CRITICAL o HIGH
e blocca (o avvisa fortemente) la presentazione dei risultati.
"""
from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class BiasWarning:
    bias_type: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    description: str
    what_it_means: str       # Spiegazione per l'utente non tecnico
    how_to_mitigate: str
    detected_automatically: bool = True


class BiasChecker:
    """
    Controlla i principali bias metodologici nel backtest.
    Alcuni sono rilevabili automaticamente, altri richiedono giudizio umano.
    """

    def run_all_checks(self,
                       strategy_spec: dict,
                       backtest_config: dict,
                       backtest_results: dict,
                       optimization_history: Optional[list] = None) -> dict:
        """
        Esegue tutti i controlli di bias disponibili.
        Ritorna un report completo con severità e spiegazioni.
        """
        warnings = []

        # 1. Look-ahead bias check
        warnings.extend(self._check_lookahead(strategy_spec))

        # 2. Overfitting check
        warnings.extend(self._check_overfitting(
            backtest_results, optimization_history
        ))

        # 3. Data snooping / multiple testing
        warnings.extend(self._check_data_snooping(
            backtest_config, optimization_history
        ))

        # 4. Execution realism
        warnings.extend(self._check_execution_realism(strategy_spec, backtest_config))

        # 5. Sample size
        warnings.extend(self._check_sample_size(backtest_results))

        # 6. Regime dependency
        warnings.extend(self._check_regime_dependency(backtest_results))

        # 7. Selection bias (utente ha descritto solo trade vincenti?)
        warnings.extend(self._check_selection_bias(strategy_spec))

        # 8. Risk of ruin
        warnings.extend(self._check_risk_of_ruin(backtest_results, backtest_config))

        critical = [w for w in warnings if w.severity == "CRITICAL"]
        high = [w for w in warnings if w.severity == "HIGH"]

        return {
            "warnings": [self._serialize(w) for w in warnings],
            "critical_count": len(critical),
            "high_count": len(high),
            "overall_reliability": self._overall_reliability(warnings),
            "can_trust_results": len(critical) == 0,
            "recommendation": self._generate_recommendation(warnings, backtest_results)
        }

    def _check_lookahead(self, spec: dict) -> list[BiasWarning]:
        warnings = []

        # Cerca indicatori tipicamente affetti da look-ahead bias
        indicators = spec.get("formal_spec", {}).get("indicators", [])
        risky_indicators = ["future_close", "next_open", "forward_return"]

        for ind in indicators:
            if any(r in str(ind).lower() for r in risky_indicators):
                warnings.append(BiasWarning(
                    bias_type="look_ahead_bias",
                    severity="CRITICAL",
                    description=f"L'indicatore '{ind.get('name')}' potrebbe usare dati futuri",
                    what_it_means="Stai usando informazioni che non avresti avuto al momento del trade. I risultati sono completamente falsi.",
                    how_to_mitigate="Usa solo indicatori calcolati sui dati disponibili al momento della candela di chiusura.",
                    detected_automatically=True
                ))

        # Controlla se il backtester usa close della candela corrente per entry
        # (pattern comune di look-ahead bias)
        if spec.get("order_execution", {}).get("entry_price") == "current_bar_close":
            warnings.append(BiasWarning(
                bias_type="look_ahead_bias",
                severity="HIGH",
                description="Entry simulata alla chiusura della stessa candela che genera il segnale",
                what_it_means="In realtà non potresti entrare esattamente alla chiusura della candela segnale. Entra alla apertura della candela successiva.",
                how_to_mitigate="Esegui l'ordine alla apertura della candela N+1 dopo il segnale su N.",
                detected_automatically=True
            ))

        return warnings

    def _check_overfitting(self, results: dict,
                            opt_history: Optional[list]) -> list[BiasWarning]:
        warnings = []

        # Se ha fatto walk-forward, controlla l'efficienza
        wf = results.get("walk_forward") or results.get("results", {}).get("walk_forward")
        if wf:
            efficiency = wf.get("wf_efficiency", 0)
            if efficiency < 0.3:
                warnings.append(BiasWarning(
                    bias_type="overfitting",
                    severity="HIGH",
                    description=f"Walk-forward efficiency bassa: {efficiency:.2f}",
                    what_it_means="La strategia performa molto meglio sui dati di training che su quelli non visti. Segno di overfitting.",
                    how_to_mitigate="Riduci il numero di parametri ottimizzati. Usa meno indicatori. Cerca logica più semplice.",
                    detected_automatically=True
                ))
        else:
            warnings.append(BiasWarning(
                bias_type="overfitting",
                severity="MEDIUM",
                description="Nessuna walk-forward analysis eseguita",
                what_it_means="Senza walk-forward non puoi sapere se la strategia funziona su dati non visti.",
                how_to_mitigate="Esegui sempre la walk-forward analysis. Non guardare mai solo i risultati in-sample.",
                detected_automatically=True
            ))

        # Troppi parametri ottimizzati?
        if opt_history:
            n_params = len(opt_history[0].get("params", {})) if opt_history else 0
            n_trades = results.get("total_trades", 0)
            if n_params > 0 and n_trades / n_params < 30:
                warnings.append(BiasWarning(
                    bias_type="overfitting",
                    severity="HIGH",
                    description=f"Rapporto trade/parametri basso: {n_trades}/{n_params} = {n_trades/n_params:.1f}",
                    what_it_means=f"Hai {n_params} parametri ottimizzati ma solo {n_trades} trade. Regola empirica: serve almeno 30 trade per parametro.",
                    how_to_mitigate="Riduci i parametri ottimizzati o aumenta il periodo di backtest.",
                    detected_automatically=True
                ))

        return warnings

    def _check_risk_of_ruin(self, backtest_results: dict, backtest_config: dict) -> list[BiasWarning]:
        warnings = []
        max_consec = backtest_results.get("max_consecutive_losses", 0)
        risk_pct = backtest_config.get("risk_per_trade_pct", 1.0)
        max_consecutive_loss_pct = max_consec * risk_pct
        if max_consecutive_loss_pct > 15:
            warnings.append(BiasWarning(
                bias_type="risk_of_ruin",
                severity="HIGH",
                description=f"{max_consec} perdite consecutive a {risk_pct}% rischio = -{max_consecutive_loss_pct:.0f}% potenziale",
                what_it_means="Una sequenza di perdite consecutive realistica può erodere significativamente il capitale.",
                how_to_mitigate="Considera di ridurre il rischio per trade o aggiungere un circuit breaker giornaliero.",
                detected_automatically=True,
            ))
        return warnings

    def _check_data_snooping(self, config: dict,
                              opt_history: Optional[list]) -> list[BiasWarning]:
        warnings = []

        if opt_history and len(opt_history) > 100:
            warnings.append(BiasWarning(
                bias_type="data_snooping",
                severity="HIGH",
                description=f"Eseguite {len(opt_history)} combinazioni di parametri sugli stessi dati",
                what_it_means="Con abbastanza combinazioni trovi parametri che 'funzionano' per puro caso statistico. Non significa edge reale.",
                how_to_mitigate="Testa poche combinazioni scelte a priori. Usa walk-forward. Considera Bonferroni correction.",
                detected_automatically=True
            ))

        # Se stesso dataset usato per sviluppo E test
        if not config.get("out_sample_start") and not config.get("date_oos_start"):
            warnings.append(BiasWarning(
                bias_type="data_snooping",
                severity="CRITICAL",
                description="Nessun set di test separato definito",
                what_it_means="Hai sviluppato e testato la strategia sugli stessi dati. I risultati non hanno valore predittivo.",
                how_to_mitigate="Dividi i dati: usa 60-70% per sviluppo, 15-20% per validazione, 15-20% per test finale. Non toccare mai il test set finché la strategia è completata.",
                detected_automatically=True
            ))

        return warnings

    def _check_execution_realism(self, spec: dict, config: dict) -> list[BiasWarning]:
        warnings = []

        spread = config.get("spread_pips", 0)
        slippage = config.get("slippage_pips", 0)

        if spread == 0 and slippage == 0:
            warnings.append(BiasWarning(
                bias_type="execution_bias",
                severity="HIGH",
                description="Spread e slippage impostati a zero",
                what_it_means="Nel trading reale paghi sempre spread e spesso soffri slippage. Un backtest senza questi costi sovrastima i profitti.",
                how_to_mitigate="Usa spread reali del broker. Aggiungi almeno 0.5-1 pip di slippage per mercati liquidi.",
                detected_automatically=True
            ))

        if spread < 0.5:
            warnings.append(BiasWarning(
                bias_type="execution_bias",
                severity="MEDIUM",
                description=f"Spread molto basso: {spread} pips",
                what_it_means="Lo spread nei mercati reali può essere più alto, specialmente in condizioni di volatilità o liquidità ridotta.",
                how_to_mitigate="Usa spread conservativo: almeno 1-2 pips per FX major, di più per cross minori.",
                detected_automatically=True
            ))

        return warnings

    def _check_sample_size(self, results: dict) -> list[BiasWarning]:
        warnings = []
        n_trades = results.get("total_trades", 0)

        if n_trades < 30:
            warnings.append(BiasWarning(
                bias_type="sample_size",
                severity="CRITICAL",
                description=f"Solo {n_trades} trade nel backtest",
                what_it_means=f"Con {n_trades} trade non puoi trarre conclusioni statistiche valide. Serve minimo 100-200 trade per avere un campione rappresentativo.",
                how_to_mitigate="Estendi il periodo di backtest. Se la strategia fa pochissimi trade, considera se ha senso algoritmizzarla.",
                detected_automatically=True
            ))
        elif n_trades < 100:
            warnings.append(BiasWarning(
                bias_type="sample_size",
                severity="HIGH",
                description=f"Campione limitato: {n_trades} trade",
                what_it_means="Con meno di 100 trade le metriche statistiche (Sharpe, hit rate) sono inaffidabili.",
                how_to_mitigate="Aumenta il periodo di backtest. Idealmente 200+ trade per metriche affidabili.",
                detected_automatically=True
            ))

        return warnings

    def _check_regime_dependency(self, results: dict) -> list[BiasWarning]:
        warnings = []

        # Se non c'è analisi per regime, avvisa
        if not results.get("stability_by_regime"):
            warnings.append(BiasWarning(
                bias_type="regime_dependency",
                severity="MEDIUM",
                description="Nessuna analisi di stabilità per regime di mercato",
                what_it_means="Una strategia che funziona solo in trend o solo in laterale è fragile. Potrebbe smettere di funzionare se il regime cambia.",
                how_to_mitigate="Analizza separatamente i periodi di trend forte (ADX > 25), trend debole, e mercato laterale.",
                detected_automatically=True
            ))

        return warnings

    def _check_selection_bias(self, spec: dict) -> list[BiasWarning]:
        warnings = []

        examples_valid = spec.get("valid_trade_examples", "")
        examples_invalid = spec.get("invalid_trade_examples", "")

        if examples_valid and not examples_invalid:
            warnings.append(BiasWarning(
                bias_type="selection_bias",
                severity="MEDIUM",
                description="Solo esempi di trade vincenti forniti, nessun esempio di trade perdenti",
                what_it_means="Rischio di cherry-picking: stai descrivendo la strategia basandoti sui trade che ricordi meglio (quelli vincenti), non su tutti i trade che avresti fatto.",
                how_to_mitigate="Fornisci anche esempi di setup che sembravano validi ma che si sono rivelati perdenti. Aiuta a definire le invalidazioni.",
                detected_automatically=True
            ))

        if not examples_valid and not examples_invalid:
            warnings.append(BiasWarning(
                bias_type="selection_bias",
                severity="LOW",
                description="Nessun esempio concreto di trade fornito",
                what_it_means="Senza esempi concreti è più difficile verificare che le regole codificate corrispondano a ciò che fai davvero.",
                how_to_mitigate="Aggiungi 3-5 esempi di trade validi e 2-3 esempi di trade che sembravano ma non erano validi.",
                detected_automatically=False
            ))

        return warnings

    def _overall_reliability(self, warnings: list[BiasWarning]) -> str:
        critical = sum(1 for w in warnings if w.severity == "CRITICAL")
        high = sum(1 for w in warnings if w.severity == "HIGH")

        if critical > 0:
            return "NON AFFIDABILE — Problemi critici rilevati"
        elif high > 2:
            return "BASSA AFFIDABILITÀ — Multipli problemi gravi"
        elif high > 0:
            return "AFFIDABILITÀ MODERATA — Con riserve"
        else:
            return "AFFIDABILITÀ ACCETTABILE — Verifica manuale consigliata"

    def _generate_recommendation(self, warnings: list[BiasWarning], results: dict) -> str:
        critical = [w for w in warnings if w.severity == "CRITICAL"]
        if critical:
            return ("⛔ NON procedere con questo backtest. Risolvi prima i problemi critici: "
                    + "; ".join(w.bias_type for w in critical))

        high = [w for w in warnings if w.severity == "HIGH"]
        if len(high) > 1:
            return ("⚠️  Risultati da trattare con molta cautela. "
                    "Risolvi i problemi di alta severità prima di trarre conclusioni.")

        sharpe = results.get("sharpe_ratio", 0)
        if sharpe < 0.5:
            return "📊 Sharpe ratio basso. La strategia non mostra edge statistico sufficiente."
        elif sharpe < 1.0:
            return "📊 Risultati marginali. La strategia potrebbe avere edge, ma non è convincente."
        else:
            return ("✅ I risultati sono metodologicamente accettabili. "
                    "Questo NON garantisce performance future — procedi con test su demo.")

    def _serialize(self, w: BiasWarning) -> dict:
        return {
            "type": w.bias_type,
            "severity": w.severity,
            "description": w.description,
            "what_it_means": w.what_it_means,
            "how_to_mitigate": w.how_to_mitigate,
            "detected_automatically": w.detected_automatically
        }
