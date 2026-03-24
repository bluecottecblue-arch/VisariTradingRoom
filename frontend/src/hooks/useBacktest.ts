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
  | 'research_validation'
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
  research_validation: 'Research validation suite...',
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
  const runTokenRef = useRef(0)
  const pollStartRef = useRef(0)
  const errCountRef = useRef(0)

  useEffect(() => () => {
    mountedRef.current = false
    runTokenRef.current += 1
    if (pollRef.current) clearTimeout(pollRef.current)
    if (phaseTimerRef.current) clearInterval(phaseTimerRef.current)
  }, [])

  const run = useCallback(
    async (sessionId: string, config: object, projectId?: string | null) => {
      if (pollRef.current) clearTimeout(pollRef.current)
      if (phaseTimerRef.current) clearInterval(phaseTimerRef.current)
      runTokenRef.current += 1
      const currentToken = runTokenRef.current
      pollStartRef.current = Date.now()
      errCountRef.current = 0

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
        'research_validation',
      ]
      let phaseIdx = 0
      phaseTimerRef.current = setInterval(() => {
        phaseIdx = (phaseIdx + 1) % phases.length
        setPhase(phases[phaseIdx])
      }, 4500)

      try {
        const response = await backtestApi.run(sessionId, config, projectId) as any

        // Backend può rispondere direttamente con i risultati (sync) o con task_id (async)
        if (response.status === 'complete' && response.results) {
          if (!mountedRef.current || runTokenRef.current !== currentToken) return
          clearInterval(phaseTimerRef.current!)
          setPhase('complete')
          setResults(response.results)
          return
        }

        // Altrimenti polling
        const taskId = response.task_id
        if (!taskId) throw new Error('Nessun task_id nella risposta del server')
        await pollStatus(taskId, currentToken)
      } catch (e: unknown) {
        if (!mountedRef.current || runTokenRef.current !== currentToken) return
        clearInterval(phaseTimerRef.current!)
        setPhase('error')
        setError(formatError(e))
      }
    },
    [],
  )

  const pollStatus = useCallback(async (taskId: string, token: number) => {
    const check = async () => {
      if (!mountedRef.current || runTokenRef.current !== token) return

      if (Date.now() - pollStartRef.current > 10 * 60 * 1000) {
        clearInterval(phaseTimerRef.current!)
        setPhase('error')
        setError('Backtest monitoring timed out. The job may still be running on the server. Refresh or retry.')
        return
      }

      try {
        const data = await backtestApi.status(taskId) as any
        if (!mountedRef.current || runTokenRef.current !== token) return
        errCountRef.current = 0 // reset on success

        if (data.status === 'complete') {
          clearInterval(phaseTimerRef.current!)
          setPhase('complete')
          setResults(data.results)
        } else if (data.status === 'error') {
          clearInterval(phaseTimerRef.current!)
          setPhase('error')
          setError(data.error || 'Errore durante il backtest')
        } else {
          pollRef.current = setTimeout(check, 3000)
        }
      } catch {
        if (!mountedRef.current || runTokenRef.current !== token) return
        errCountRef.current += 1
        if (errCountRef.current > 5) {
          clearInterval(phaseTimerRef.current!)
          setPhase('error')
          setError('Too many network errors while checking backtest status.')
          return
        }
        const backoff = Math.min(15000, 3000 * Math.pow(1.5, errCountRef.current))
        pollRef.current = setTimeout(check, backoff)
      }
    }
    check()
  }, [])

  const reset = useCallback(() => {
    runTokenRef.current += 1
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
