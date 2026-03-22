"use client";

interface Props {
  formalSpec: any;
  onComplete: () => void;
  onBack: () => void;
}

export default function StepFormalSpec({ formalSpec, onComplete, onBack }: Props) {
  const spec = formalSpec?.formal_spec || {};
  const params = formalSpec?.parameters || [];
  const nonOpt = formalSpec?.non_optimizable || [];
  const sm = formalSpec?.state_machine || {};

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-amber-400 mb-2">Specifica algoritmica formale</h1>
        <p className="text-stone-400 text-sm">
          La tua strategia è stata convertita in una specifica algoritmica rigorosa.
          Leggi attentamente — questa è la base del bot che verrà generato.
          Se qualcosa non corrisponde a ciò che intendevi, torna indietro e modifica.
        </p>
      </div>

      {/* Macchina a stati */}
      {sm.states && (
        <Section title="🔄 Macchina a stati del bot">
          <p className="text-stone-500 text-xs mb-3">
            Il bot si muove attraverso questi stati. Capire questo aiuta a capire il comportamento del bot.
          </p>
          <div className="flex flex-wrap gap-2 mb-4">
            {sm.states.map((s: string) => (
              <span key={s} className="px-3 py-1 bg-stone-800 border border-stone-700 rounded text-stone-300 text-xs font-mono">
                {s}
              </span>
            ))}
          </div>
          {sm.transitions?.map((t: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-xs py-1">
              <span className="text-stone-500 font-mono">{t.from}</span>
              <span className="text-amber-600">→</span>
              <span className="text-stone-300 font-mono">{t.to}</span>
              <span className="text-stone-600">se</span>
              <span className="text-stone-400 italic">{t.condition}</span>
            </div>
          ))}
        </Section>
      )}

      {/* Condizioni di ingresso */}
      {spec.entry_conditions && (
        <Section title="📈 Condizioni di ingresso">
          {spec.entry_conditions.long?.conditions?.length > 0 && (
            <div className="mb-4">
              <div className="text-stone-400 text-xs font-bold mb-2">LONG (logica: {spec.entry_conditions.long.logic})</div>
              {spec.entry_conditions.long.conditions.map((c: any) => (
                <div key={c.id} className="px-3 py-2 mb-2 bg-stone-900 border border-stone-800 rounded">
                  <div className="text-stone-300 text-xs">{c.description}</div>
                  <div className="text-green-400 text-xs font-mono mt-1">{c.mql5_expression}</div>
                </div>
              ))}
            </div>
          )}
          {spec.entry_conditions.short?.conditions?.length > 0 && (
            <div>
              <div className="text-stone-400 text-xs font-bold mb-2">SHORT</div>
              {spec.entry_conditions.short.conditions.map((c: any) => (
                <div key={c.id} className="px-3 py-2 mb-2 bg-stone-900 border border-stone-800 rounded">
                  <div className="text-stone-300 text-xs">{c.description}</div>
                  <div className="text-red-400 text-xs font-mono mt-1">{c.mql5_expression}</div>
                </div>
              ))}
            </div>
          )}
        </Section>
      )}

      {/* Risk management */}
      {spec.risk_management && (
        <Section title="🛡️ Gestione del rischio">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {Object.entries(spec.risk_management).map(([k, v]) => (
              <div key={k} className="px-3 py-2 bg-stone-900 border border-stone-800 rounded">
                <div className="text-stone-500 text-xs">{k.replace(/_/g, " ")}</div>
                <div className="text-stone-200 text-sm font-bold">{String(v)}</div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Parametri ottimizzabili */}
      {params.length > 0 && (
        <Section title="⚙️ Parametri del bot">
          <p className="text-stone-500 text-xs mb-3">
            Questi parametri possono essere modificati nel bot. Quelli marcati come
            "non ottimizzare" NON devono essere usati in ottimizzazione — rischio curve fitting.
          </p>
          <div className="space-y-2">
            {params.map((p: any) => (
              <div key={p.id} className="px-3 py-2 bg-stone-900 border border-stone-800 rounded flex items-start gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-stone-200 text-xs font-bold">{p.name}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      p.optimize ? "bg-green-950 text-green-400" : "bg-stone-800 text-stone-500"
                    }`}>
                      {p.optimize ? "ottimizzabile" : "fisso"}
                    </span>
                  </div>
                  <div className="text-stone-500 text-xs mt-0.5">{p.description}</div>
                  {p.why_not_optimize && (
                    <div className="text-amber-700 text-xs mt-0.5">⚠️ {p.why_not_optimize}</div>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <div className="text-stone-300 text-xs font-mono">{String(p.default_value)}</div>
                  <div className="text-stone-600 text-xs">{p.type}</div>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Non ottimizzare */}
      {nonOpt.length > 0 && (
        <div className="p-4 bg-red-950/10 border border-red-800/40 rounded">
          <h3 className="text-red-400 font-bold text-sm mb-2">
            🚫 Non ottimizzare mai questi aspetti
          </h3>
          <p className="text-stone-500 text-xs mb-3">
            Ottimizzare questi parametri porta a curve fitting — il bot imparerà a memoria
            il passato senza capacità predittiva.
          </p>
          <ul className="space-y-1">
            {nonOpt.map((item: string, i: number) => (
              <li key={i} className="text-red-300 text-xs flex gap-2">
                <span>•</span><span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="p-4 bg-stone-900 border border-stone-700 rounded text-stone-400 text-xs">
        <strong className="text-stone-300">Prima di continuare, chiediti:</strong><br />
        Questa specifica corrisponde a ciò che fai davvero quando tradi?
        Se cSe c'è qualcosaapos;è qualcosa che non quadra, torna indietro e chiariscilo.
        Il bot genererà esattamente ciò che è scritto qui sopra.
      </div>

      <div className="flex gap-4">
        <button onClick={onBack}
          className="px-6 py-3 border border-stone-700 text-stone-400 hover:text-stone-200 rounded transition-colors">
          ← Indietro
        </button>
        <button onClick={onComplete}
          className="flex-1 py-3 bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold rounded transition-colors">
          Procedi al backtest →
        </button>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h2 className="text-stone-300 font-bold text-sm uppercase tracking-wider border-b border-stone-800 pb-2">
        {title}
      </h2>
      {children}
    </div>
  );
}
