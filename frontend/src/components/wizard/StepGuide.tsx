"use client";

import { useState } from "react";
import { exportApi } from "@/lib/api";
import { deriveLaunchReadinessPack } from "@/lib/launchReadiness";
import type { BotResult } from "@/types";

interface Props {
  botResult: BotResult | null;
  onBack: () => void;
}

const MT5_STEPS = [
  {
    id: 1,
    title: "Cos'è MetaTrader 5",
    icon: "🖥️",
    content: `MetaTrader 5 (MT5) è una piattaforma di trading professionale gratuita sviluppata da MetaQuotes.
    
È il software che eseguirà il tuo bot automaticamente, anche quando non sei davanti al computer — purché il computer sia acceso e connesso a internet.

MT5 ha due componenti principali che userai:
• Il TERMINALE: dove vedi i grafici, le posizioni aperte, l'account
• Il METAEDITOR: dove si scrive e compila il codice degli Expert Advisor

Il tuo bot è un "Expert Advisor" (EA) — un programma MQL5 che gira dentro MT5.`,
  },
  {
    id: 2,
    title: "Scarica e installa MT5",
    icon: "⬇️",
    content: `1. Vai sul sito del tuo broker (quello da cui vuoi tradare)
   → La maggior parte dei broker seri offre MT5 gratuitamente

2. Cerca nella sezione "Piattaforme" o "Download"
   → Clicca "Scarica MetaTrader 5" o "Download MT5"

3. Se il tuo broker non offre MT5, puoi scaricare la versione di test da:
   → https://www.metatrader5.com/it/download
   (ma poi dovrai usare il file di installazione del tuo broker vero)

4. Esegui il file scaricato (.exe su Windows, .dmg su Mac)
   → Segui l'installazione guidata — clicca "Avanti" e poi "Installa"
   → Non cambiare la cartella di installazione a meno che tu non sappia cosa fai

5. Avvia MT5 e inserisci le credenziali del tuo account broker
   → Usa prima un CONTO DEMO per testare il bot`,
  },
  {
    id: 3,
    title: "Apri MetaEditor",
    icon: "✏️",
    content: `MetaEditor è il programma dove metti il file del bot.

Per aprirlo hai due opzioni:

OPZIONE A — dal menù di MT5:
→ In MT5, clicca su "Strumenti" nella barra in alto
→ Clicca "MetaEditor"

OPZIONE B — da tastiera:
→ Premi il tasto F4 mentre MT5 è aperto

Quando MetaEditor si apre, vedrai:
• A sinistra: il "Navigator" con la struttura delle cartelle
• Al centro: l'editor di testo dove appare il codice
• In basso: l'area dove vengono mostrati errori e avvisi

Non devi scrivere codice tu! Il bot è già pronto.`,
  },
  {
    id: 4,
    title: "Copia il file del bot",
    icon: "📁",
    content: `Il file del tuo bot si chiama qualcosa come "VisariTradingRoom_EA_XXXXXXXX.mq5"
(l'hai scaricato nello step precedente).

Devi metterlo nella cartella giusta:

METODO 1 — Dal menù di MetaEditor (più facile):
→ In MetaEditor, clicca su "File" → "Apri cartella dati"
→ Si apre una finestra di Esplora File
→ Vai nella cartella: MQL5 → Experts
→ Copia il file .mq5 in questa cartella

METODO 2 — Trovare la cartella manualmente:
→ La cartella di default su Windows è:
   C:\\Users\\[tuo nome]\\AppData\\Roaming\\MetaQuotes\\Terminal\\[codice]\\MQL5\\Experts
→ Incolla il file .mq5 qui dentro

Dopo aver copiato il file:
→ Torna in MetaEditor
→ Nel Navigator a sinistra, cerca "Experts"
→ Clicca con il tasto destro → "Aggiorna"
→ Dovresti vedere il file della tua strategia`,
  },
  {
    id: 5,
    title: "Compila il bot",
    icon: "🔨",
    content: `"Compilare" significa trasformare il codice in un programma che MT5 può eseguire.
È come "tradurre" il testo del bot in linguaggio macchina.

Per compilare:
1. In MetaEditor, apri il file .mq5 (doppio click nel Navigator)
2. Premi F7 oppure clicca "Compila" nella barra degli strumenti
3. Guarda in basso, nel pannello "Errori"

SE VEDI "0 errori, 0 avvisi":
→ Tutto ok! Il bot è compilato correttamente.

SE VEDI DEGLI ERRORI (righe rosse):
→ C'è un problema nel codice.
→ NON è colpa tua — può succedere che il codice generato abbia piccoli errori.
→ Leggi il messaggio di errore e cerca online "[messaggio errore] MQL5"
→ Oppure torna su VisariTradingRoom e segnala il problema
→ Un errore comune: funzioni deprecate o sintassi leggermente diversa tra versioni MT5

Dopo la compilazione corretta, vedrai un file .ex5 nella stessa cartella.
Questo è il bot compilato — quello che MT5 userà davvero.`,
  },
  {
    id: 6,
    title: "Attiva AutoTrading",
    icon: "🤖",
    content: `Per sicurezza, MT5 nasce con il trading automatico DISATTIVATO.
Devi abilitarlo esplicitamente.

STEP 1 — Abilita il trading automatico globale:
→ In MT5, guarda la barra degli strumenti in alto
→ Cerca il pulsante "AutoTrading" (icona con una freccia circolare verde/rossa)
→ Clicca per attivarlo — deve diventare VERDE con scritta "AutoTrading"

STEP 2 — Verifica i permessi (importante!):
→ Clicca su "Strumenti" → "Opzioni" → "Expert Advisor"
→ Assicurati che sia spuntato:
   ✅ "Consenti il trading automatico"
   ✅ "Consenti importazione di DLL" (se richiesto dal tuo EA)

Se AutoTrading è disattivato, il bot vede i segnali ma NON apre ordini.
È la prima cosa da controllare se il bot "non fa niente".`,
  },
  {
    id: 7,
    title: "Collega il bot al grafico",
    icon: "📈",
    content: `Ora devi "attaccare" il bot a un grafico del mercato che vuoi tradare.

1. Apri un grafico del tuo strumento
   → Clicca su "File" → "Nuovo grafico"
   → Cerca il simbolo (es. EURUSD) e aprilo
   → Imposta il timeframe di ESECUZIONE della tua strategia (es. M15)

2. Apri il Navigator degli EA
   → Premi CTRL+N oppure clicca "Visualizza" → "Navigator"
   → Nella finestra Navigator, espandi "Expert Advisor"
   → Trova il tuo bot nella lista

3. Trascina il bot sul grafico
   → Tieni premuto il tasto sinistro del mouse sul nome del bot
   → Trascinalo sopra il grafico e rilascia

4. Si aprirà una finestra di configurazione:
   → TAB "Comune": assicurati di spuntare "Consenti trading live"
   → TAB "Parametri di input": configura i parametri (risk %, orari, ecc.)
   → Clicca OK

5. In alto a destra del grafico dovresti vedere il nome del bot
   → Con un sorriso 🙂 verde = bot attivo e funzionante
   → Con un sorriso triste 🙁 = problema (controlla AutoTrading)`,
  },
  {
    id: 8,
    title: "Backtest in Strategy Tester",
    icon: "📊",
    content: `Anche se hai già fatto il backtest su VisariTradingRoom, è utile vedere come gira
dentro MT5 usando il suo Strategy Tester integrato.

Per aprire il Strategy Tester:
→ Clicca "Visualizza" → "Strategy Tester" oppure premi CTRL+R

Configurazione del Strategy Tester:
1. "Expert Advisor": seleziona il tuo bot dalla lista
2. "Simbolo": il mercato che vuoi testare (es. EURUSD)
3. "Timeframe": il timeframe di esecuzione (es. M15)
4. "Modello": scegli "Every tick based on real ticks" per il backtest più accurato
   (richiede dati tick — più lento ma più preciso)
   oppure "Open prices only" per test veloce
5. "Periodo": imposta le date del backtest
6. "Deposito iniziale": il capitale iniziale
7. Clicca "Start"

Cosa guarda nei risultati:
• "Equity chart": deve essere una curva tendenzialmente in salita
• "Balance/Equity drawdown": quanto scende nelle fasi negative
• "Profit factor": sopra 1.0 è positivo
• "Expected payoff": guadagno medio per trade in valuta

⚠️ Se i risultati MT5 differiscono da VisariTradingRoom, è normale:
i dati e i modelli di simulazione sono diversi. Fidati del confronto, non del numero assoluto.`,
  },
  {
    id: 9,
    title: "Prima settimana in demo",
    icon: "🔬",
    content: `Questo è il passo più importante. Non saltarlo.

CONTO DEMO = trading reale senza soldi veri.
I prezzi sono reali (o quasi), i trade sono reali, ma il capitale è virtuale.

Come aprire un conto demo su MT5:
→ Clicca "File" → "Apri conto"
→ Scegli il tuo broker → "Conto demo"
→ Scegli il capitale iniziale (es. 10.000$)
→ Completa la registrazione

Cosa monitorare la prima settimana:

OGNI GIORNO:
✅ Il bot si attiva e si disattiva negli orari giusti?
✅ Apre posizioni nei setup corretti?
✅ Rispetta stop loss e take profit?
✅ Il sizing è corretto (quanto rischia per trade)?
✅ Ci sono errori nel log? ("Visualizza" → "Terminale" → "Journal")

COSA FARE SE QUALCOSA NON VA:
→ Controlla il Journal — lì ci sono tutti gli eventi del bot
→ Se apre trade nei momenti sbagliati: c'è un problema logico nel codice
→ Se non apre mai nessun trade: controlla AutoTrading e i permessi
→ Se il sizing è sbagliato: controlla il parametro RiskPercent

QUANDO ANDARE LIVE (mai prima di):
✅ Almeno 4 settimane di demo con risultati coerenti col backtest
✅ Hai capito perché ogni trade viene aperto e chiuso
✅ Hai deciso quale drawdown massimo sei disposto a sopportare
✅ Il capitale live che usi è denaro che puoi permetterti di perdere`,
  },
  {
    id: 10,
    title: "Errori comuni e soluzioni",
    icon: "🛠️",
    content: `Problemi frequenti e come risolverli:

PROBLEMA: Il bot non apre nessun trade
→ Controlla che AutoTrading sia verde (attivo)
→ Controlla che il bot abbia il sorriso verde sul grafico
→ Controlla gli orari: sei nell'orario di sessione configurato?
→ Controlla il Journal per messaggi di errore
→ Verifica che il conto abbia margine sufficiente

PROBLEMA: Errori di compilazione in MetaEditor
→ Leggi il messaggio esatto (clicca due volte sull'errore)
→ Cerca "[messaggio errore] MQL5" su Google
→ Spesso sono funzioni che si chiamano diversamente in versioni MT5 diverse

PROBLEMA: Il bot apre trade in momenti sbagliati
→ Il codice potrebbe avere un'imprecisione nella logica
→ Spegni il bot (rimuovilo dal grafico) subito
→ Segnala il comportamento su VisariTradingRoom per rivedere le regole

PROBLEMA: Lo spread è troppo alto
→ Il bot dovrebbe già controllare lo spread (parametro MaxSpreadPoints)
→ Se non lo fa, il codice va aggiornato

PROBLEMA: Il bot si chiude da solo
→ MT5 si è aggiornato o riavviato
→ Devi riattecare il bot al grafico dopo ogni riavvio
→ Soluzione: lascia MT5 sempre aperto su un computer dedicato o VPS

CONSIGLIO PRO: VPS (Virtual Private Server)
Per il trading automatico, molti trader usano un VPS — un computer virtuale
sempre acceso e connesso. Evita interruzioni per aggiornamenti di Windows,
cadute di corrente, ecc. Costo: ~10-20$/mese.`,
  },
];

export default function StepGuide({ botResult, onBack }: Props) {
  const [activeStep, setActiveStep] = useState(1);

  const step = MT5_STEPS.find((s) => s.id === activeStep)!;
  const launchPack = deriveLaunchReadinessPack(botResult, null);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-amber-400 mb-2">Guida installazione MetaTrader 5</h1>
        <p className="text-stone-400 text-sm">
          Segui questi passi nell&apos;ordine. Non dare nulla per scontato — ogni passo è spiegato
          come se fosse la prima volta che usi MetaTrader.
        </p>
      </div>

      {launchPack && (
        <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="border border-slate-800 bg-slate-950/70 p-5">
            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Protocollo di lancio consigliato</div>
            <div className="mt-2 flex items-start justify-between gap-3">
              <div>
                <div className="text-lg font-semibold text-slate-100">{launchPack.label}</div>
                <div className="mt-2 text-sm leading-relaxed text-slate-400">{launchPack.summary}</div>
              </div>
              <span className={`border px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] ${launchPack.toneClass}`}>
                {launchPack.mode.replaceAll("_", " ")}
              </span>
            </div>
          </div>
          <div className="border border-slate-800 bg-slate-950/70 p-5">
            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Prima settimana</div>
            <div className="mt-3 space-y-2">
              {launchPack.firstWeekProtocol.map((item, index) => (
                <div key={index} className="text-sm leading-relaxed text-slate-300">• {item}</div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="flex gap-6">
        {/* Step navigation sidebar */}
        <div className="w-48 flex-shrink-0 space-y-1">
          {MT5_STEPS.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveStep(s.id)}
              className={`w-full text-left px-3 py-2 rounded text-xs transition-colors ${
                s.id === activeStep
                  ? "bg-amber-500/20 text-amber-400 border border-amber-700/50"
                  : "text-stone-500 hover:text-stone-300 hover:bg-stone-800"
              }`}
            >
              <span className="mr-2">{s.icon}</span>
              <span className="text-[11px]">{s.title}</span>
            </button>
          ))}
        </div>

        {/* Step content */}
        <div className="flex-1 min-w-0">
          <div className="p-6 bg-stone-900 border border-stone-700 rounded">
            <div className="flex items-center gap-3 mb-4">
              <span className="text-3xl">{step.icon}</span>
              <div>
                <div className="text-stone-500 text-xs mb-1">Passo {step.id} di {MT5_STEPS.length}</div>
                <h2 className="text-stone-100 font-bold text-lg">{step.title}</h2>
              </div>
            </div>
            <div className="text-stone-300 text-sm leading-relaxed whitespace-pre-wrap">
              {step.content}
            </div>
          </div>

          {/* Navigation buttons */}
          <div className="flex gap-3 mt-4">
            <button
              onClick={() => setActiveStep((s) => Math.max(s - 1, 1))}
              disabled={activeStep === 1}
              className="px-4 py-2 border border-stone-700 hover:border-stone-500 text-stone-400 text-sm rounded transition-colors disabled:opacity-30"
            >
              ← Precedente
            </button>
            {activeStep < MT5_STEPS.length ? (
              <button
                onClick={() => setActiveStep((s) => s + 1)}
                className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold text-sm rounded transition-colors"
              >
                Passo successivo →
              </button>
            ) : (
              <div className="flex-1 p-3 bg-green-950/30 border border-green-800/50 rounded text-green-400 text-sm text-center font-bold">
                ✅ Hai completato tutti i passi! In bocca al lupo con il tuo bot.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Download reminder */}
      {botResult?.download_ready && (
        <div className="p-4 bg-stone-900 border border-amber-800/40 rounded flex items-center justify-between">
          <div>
            <p className="text-stone-300 font-bold text-sm">Hai già scaricato il tuo Expert Advisor?</p>
            <p className="text-stone-500 text-xs">Ti serve per il passo 4 — copia il file nella cartella Experts</p>
          </div>
          <button
            onClick={() => {
              const a = document.createElement("a");
              a.href = exportApi.downloadMql5Url(botResult.session_id);
              a.download = "VisariTradingRoom_EA.mq5";
              a.click();
            }}
            className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold text-sm rounded transition-colors flex-shrink-0"
          >
            ⬇ Scarica .mq5
          </button>
        </div>
      )}

      <div className="flex gap-4">
        <button onClick={onBack} className="px-6 py-3 border border-stone-700 text-stone-400 rounded text-sm hover:border-stone-500 transition-colors">
          ← Torna al bot
        </button>
      </div>
    </div>
  );
}
