'use client'

import { useState, useRef, useCallback, useEffect } from 'react'
import { backtestApi, formatError } from '@/lib/api'
import type { BacktestResult } from '@/types'

type Phase =
  | 'idle'
  | 'downloading_data'
  | 'backtest_insample'
  | 'backtest_oos'
  | 'walk_forward'
  | 'monte_carlo'
  | 'bias_check'
  | 'complete'
  | 'error'

const PHASE_LABELS: Record<Phase, string> = {
  idle: '',
  downloading_data: 'Scaricamento dati storici...',
  backtest_insample: 'Backtest in-sample...',
  backtest_oos: 'Backtest out-of-sample...',
  walk_forward: 'Walk-forward analysis...',
  monte_carlo: 'Monte Carlo simulation...',
  bias_check: 'Controllo bias metodologici...',
  complete: 'Completato',
  error: 'Errore',
}

export function useBacktest() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [results, setResults] = useState<BacktestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const phaseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => () => {
    mountedRef.current = false
    if (pollRef.current) clearTimeout(pollRef.current)
    if (phaseTimerRef.current) clearInterval(phaseTimerRef.current)
  }, [])

  const run = useCallback(
    async (sessionId: string, config: object) => {
      if (pollRef.current) clearTimeout(pollRef.current)
      if (phaseTimerRef.current) clearInterval(phaseTimerRef.current)
      setPhase('downloading_data')
      setError(null)
      setResults(null)

      // Cicla le fasi visivamente mentre aspettiamo
      const phases: Phase[] = [
        'downloading_data',
        'backtest_insample',
        'backtest_oos',
        'walk_forward',
        'monte_carlo',
        'bias_check',
      ]
      let phaseIdx = 0
      phaseTimerRef.current = setInterval(() => {
        phaseIdx = (phaseIdx + 1) % phases.length
        setPhase(phases[phaseIdx])
      }, 4500)

      try {
        const response = await backtestApi.run(sessionId, config) as any

        // Backend può rispondere direttamente con i risultati (sync) o con task_id (async)
        if (response.status === 'complete' && response.results) {
          if (!mountedRef.current) return
          clearInterval(phaseTimerRef.current!)
          setPhase('complete')
          setResults(response.results)
          return
        }

        // Altrimenti polling
        const taskId = response.task_id
        if (!taskId) throw new Error('Nessun task_id nella risposta del server')
        await pollStatus(taskId)
      } catch (e: unknown) {
        if (!mountedRef.current) return
        clearInterval(phaseTimerRef.current!)
        setPhase('error')
        setError(formatError(e))
      }
    },
    [],
  )

  const pollStatus = useCallback(async (taskId: string) => {
    const check = async () => {
      try {
        const data = await backtestApi.status(taskId) as any

        if (data.status === 'complete') {
          if (!mountedRef.current) return
          clearInterval(phaseTimerRef.current!)
          setPhase('complete')
          setResults(data.results)
        } else if (data.status === 'error') {
          if (!mountedRef.current) return
          clearInterval(phaseTimerRef.current!)
          setPhase('error')
          setError(data.error || 'Errore durante il backtest')
        } else {
          pollRef.current = setTimeout(check, 3000)
        }
      } catch {
        pollRef.current = setTimeout(check, 5000)
      }
    }
    check()
  }, [])

  const reset = useCallback(() => {
    if (pollRef.current) clearTimeout(pollRef.current)
    if (phaseTimerRef.current) clearInterval(phaseTimerRef.current)
    mountedRef.current = true
    setPhase('idle')
    setResults(null)
    setError(null)
  }, [])

  return {
    phase,
    phaseLabel: PHASE_LABELS[phase],
    isRunning: phase !== 'idle' && phase !== 'complete' && phase !== 'error',
    results,
    error,
    run,
    reset,
  }
}
