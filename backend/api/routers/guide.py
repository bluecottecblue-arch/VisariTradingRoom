"""
Router: Guide — Guida interattiva installazione MetaTrader 5
"""
from fastapi import APIRouter, HTTPException

router = APIRouter()

MT5_GUIDE_STEPS = [
    {
        "id": 1, "title": "Cos'è MetaTrader 5", "icon": "monitor",
        "content": "MetaTrader 5 è una piattaforma di trading professionale gratuita. Il tuo bot è un 'Expert Advisor' (EA) che MT5 esegue automaticamente su un grafico, aprendo e chiudendo ordini secondo le tue regole.",
        "tips": ["MT5 è gratuito — scaricalo dal sito del tuo broker"],
        "warnings": []
    },
    {
        "id": 2, "title": "Scarica e installa MT5", "icon": "download",
        "content": "Vai sul sito del tuo broker e scarica MT5, oppure su https://www.metatrader5.com/en/download. Installa normalmente. Al primo avvio, apri un account DEMO — lo usi per testare il bot prima di rischiare soldi reali.",
        "tips": ["Usa SEMPRE un account DEMO per i primi test"],
        "warnings": ["⚠️ MT5 funziona nativamente solo su Windows. Su Mac usa Wine, Parallels o una VM."]
    },
    {
        "id": 3, "title": "Apri MetaEditor", "icon": "code",
        "content": "MetaEditor è l'ambiente dove importerai il codice del bot. Per aprirlo: nel terminale MT5 premi F4 (il modo più veloce), oppure menu 'Strumenti' → 'MetaEditor'.",
        "tips": ["F4 = apre MetaEditor istantaneamente"],
        "warnings": []
    },
    {
        "id": 4, "title": "Importa il file .mq5", "icon": "file",
        "content": "In MetaEditor → menu 'File' → 'Apri cartella dati'. Si apre Esplora File in: ...\\MQL5\\Experts\\ Copia il file VisariTradingRoom_XXXXXX.mq5 in questa cartella.",
        "tips": ["La cartella Experts è nascosta — il comando 'Apri cartella dati' la trova automaticamente"],
        "warnings": []
    },
    {
        "id": 5, "title": "Compila l'EA", "icon": "cpu",
        "content": "Con il file .mq5 aperto → premi F7 per compilare. ✅ '0 errori' = ok. ⚠️ Warnings = funziona con avvertenze. ❌ Errori = non funziona. Dopo la compilazione appare il file .ex5.",
        "tips": ["F7 = compila."],
        "warnings": ["⚠️ Se ci sono errori di compilazione, NON usare il bot."]
    },
    {
        "id": 6, "title": "Attiva AutoTrading", "icon": "play",
        "content": "MT5 ha un interruttore 'AutoTrading' nella toolbar. Verde ▶ = attivo. Grigio/rosso = disattivato. Clicca per alternare. Usalo come pausa di emergenza.",
        "tips": ["AutoTrading disattivato = pausa immediata del bot"],
        "warnings": ["⚠️ Non abilitare AutoTrading su account reale finché non hai testato 2-4 settimane in demo"]
    },
    {
        "id": 7, "title": "Allega l'EA al grafico", "icon": "chart",
        "content": "Apri il grafico con il timeframe corretto. Navigator → Expert Advisors → doppio clic sull'EA. Tab 'Common' → spunta 'Allow live trading'. Tab 'Inputs' → parametri. Angolo grafico: 🙂 = ok, ☹ = problema.",
        "tips": ["Faccina 🙂 = tutto ok. Faccina ☹ = controlla AutoTrading e 'Allow live trading'"],
        "warnings": []
    },
    {
        "id": 8, "title": "Backtest in Strategy Tester", "icon": "test",
        "content": "Ctrl+R apre Strategy Tester. EA, Simbolo, Timeframe, Date, Deposito. Modello: 'Solo prezzi apertura' per velocità, 'Ogni tick' per precisione. Tab Grafico = equity curve, Report = metriche, Risultati = lista trade.",
        "tips": ["Inizia con 'Solo prezzi apertura', poi verifica con tick reali"],
        "warnings": ["⚠️ I risultati MT5 Tester possono differire leggermente da VisariTradingRoom — è normale"]
    },
    {
        "id": 9, "title": "Test in demo live", "icon": "eye",
        "content": "Lascia girare il bot su demo 2-4 settimane. Controlla: apre ordini? SL/TP corretti? Lot size coerente? Drawdown in linea? Solo dopo vai live e inizia con 0.01 lot.",
        "tips": ["Tieni un diario giornaliero del comportamento del bot"],
        "warnings": ["⚠️ Non andare mai live senza almeno 2-4 settimane di test demo"]
    }
]


@router.get("/mt5-steps")
async def get_mt5_steps():
    return {"steps": MT5_GUIDE_STEPS}


@router.get("/mt5-steps/{step_id}")
async def get_mt5_step(step_id: int):
    steps = [s for s in MT5_GUIDE_STEPS if s["id"] == step_id]
    if not steps:
        raise HTTPException(status_code=404, detail=f"Step {step_id} non trovato")
    return steps[0]
