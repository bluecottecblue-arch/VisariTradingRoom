'use client'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-100 font-mono flex items-center justify-center px-6">
      <div className="max-w-lg w-full border border-red-800/50 bg-stone-900 rounded-lg p-6 space-y-4">
        <h1 className="text-xl font-bold text-red-400">Errore applicazione</h1>
        <p className="text-stone-400 text-sm">
          Si è verificato un errore React non gestito. Il flusso è stato interrotto in modo sicuro.
        </p>
        <p className="text-stone-500 text-xs break-words">{error.message}</p>
        <button
          onClick={reset}
          className="px-5 py-3 bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold rounded"
        >
          Riprova
        </button>
      </div>
    </div>
  )
}
