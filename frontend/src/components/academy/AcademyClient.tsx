'use client'

import Link from 'next/link'
import { useEffect, useMemo, useRef, useState } from 'react'
import AuthToolbar from '@/components/AuthToolbar'
import AppSidebar from '@/components/layout/AppSidebar'
import { EmptyState, ProgressBar, Spinner, inputCls, textareaCls } from '@/components/ui'
import { academyApi, formatError } from '@/lib/api'
import type {
  AcademyBootstrapPayload,
  AcademyIndicator,
  AcademyLatestLesson,
  AcademyLesson,
  AcademyModule,
  AcademySearchResult,
  AcademyLevel,
} from '@/types'

const LEVEL_OPTIONS: Array<{ id: AcademyLevel; label: string; detail: string }> = [
  { id: 'beginner', label: 'Principiante', detail: 'Parto da zero o quasi' },
  { id: 'intermediate', label: 'Intermedio', detail: 'Conosco già bot, test o indicatori' },
  { id: 'advanced', label: 'Avanzato', detail: 'Voglio un percorso più desk-oriented' },
]

function statusTone(status: AcademyModule['status']) {
  if (status === 'completed') return 'border-emerald-900/70 bg-emerald-950/12 text-emerald-300'
  if (status === 'in_progress') return 'border-cyan-900/70 bg-cyan-950/12 text-cyan-300'
  return 'border-slate-900 bg-slate-950/60 text-slate-500'
}

function levelLabel(level?: string | null) {
  if (level === 'advanced') return 'Avanzato'
  if (level === 'intermediate') return 'Intermedio'
  return 'Principiante'
}

function shortDate(value?: string | null) {
  if (!value) return '—'
  try {
    return new Intl.DateTimeFormat('it-IT', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return value
  }
}

function pickLesson(module: AcademyModule | undefined, preferredLessonId?: string | null) {
  if (!module || !module.lessons.length) return null
  if (preferredLessonId) {
    const preferred = module.lessons.find((lesson) => lesson.id === preferredLessonId)
    if (preferred) return preferred
  }
  return module.lessons.find((lesson) => !lesson.completed) || module.lessons[0]
}

function resolveSelection(payload: AcademyBootstrapPayload, preferred?: { moduleId?: string | null; lessonId?: string | null }) {
  const modules = payload.catalog.modules
  const preferredModule = preferred?.moduleId ? modules.find((module) => module.id === preferred.moduleId) : null
  if (preferredModule) {
    const preferredLesson = pickLesson(preferredModule, preferred?.lessonId)
    return {
      moduleId: preferredModule.id,
      lessonId: preferredLesson?.id || null,
    }
  }

  const continueItem = payload.dashboard.continue_from_here
  if (continueItem) {
    return {
      moduleId: continueItem.module_id,
      lessonId: continueItem.lesson_id,
    }
  }

  const suggested = payload.catalog.modules.find((module) => module.id === payload.dashboard.personalized_suggestion.module_id)
  if (suggested) {
    return {
      moduleId: suggested.id,
      lessonId: pickLesson(suggested)?.id || null,
    }
  }

  const firstAvailable = modules.find((module) => !module.locked) || modules[0]
  return {
    moduleId: firstAvailable?.id || null,
    lessonId: pickLesson(firstAvailable)?.id || null,
  }
}

function LessonCard({
  lesson,
  active,
  onSelect,
  onToggle,
}: {
  lesson: AcademyLesson
  active: boolean
  onSelect: () => void
  onToggle: () => void
}) {
  return (
    <div
      className={`group space-y-3 border p-4 text-left transition-colors ${
        active
          ? 'border-cyan-700/70 bg-cyan-950/12'
          : 'border-slate-800 bg-slate-950/70 hover:border-slate-700'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <button type="button" onClick={onSelect} className="min-w-0 text-left">
          <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">{lesson.difficulty}</div>
          <div className="mt-2 text-lg font-semibold text-slate-100">{lesson.title}</div>
        </button>
        <button
          type="button"
          onClick={onToggle}
          className={`mt-1 h-5 w-5 border transition-colors ${
            lesson.completed ? 'border-cyan-400 bg-cyan-400' : 'border-slate-700 bg-transparent'
          }`}
          aria-label={lesson.completed ? 'Segna come non completata' : 'Segna come completata'}
        />
      </div>
      <button type="button" onClick={onSelect} className="block w-full text-left">
        <p className="text-sm leading-relaxed text-slate-400">{lesson.summary}</p>
        <div className="mt-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>{lesson.duration_min} min</span>
            <span>{lesson.completed ? 'Completata' : 'Da fare'}</span>
          </div>
          <span className="border border-slate-700 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300 transition-colors group-hover:border-cyan-700/70 group-hover:text-cyan-300">
            Apri lezione
          </span>
        </div>
      </button>
    </div>
  )
}

function BulletList({ items, tone = 'cyan' }: { items: string[]; tone?: 'cyan' | 'amber' | 'slate' }) {
  const dotClass =
    tone === 'amber' ? 'bg-amber-300' : tone === 'slate' ? 'bg-slate-400' : 'bg-cyan-300'
  return (
    <ul className="mt-3 space-y-2 text-sm text-slate-300">
      {items.map((item) => (
        <li key={item} className="flex gap-2">
          <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${dotClass}`} />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

function IndicatorCard({ indicator, highlighted }: { indicator: AcademyIndicator; highlighted?: boolean }) {
  return (
    <article
      id={`indicator-${indicator.id}`}
      className={`space-y-4 border p-5 ${
        highlighted ? 'border-cyan-700/70 bg-cyan-950/12' : 'border-slate-800 bg-slate-950/72'
      }`}
    >
      <div className="space-y-2">
        <h4 className="text-xl font-semibold text-slate-50">{indicator.name}</h4>
        <div className="text-xs uppercase tracking-[0.18em] text-slate-500">Formula</div>
        <p className="text-sm text-slate-300">{indicator.formula || 'Non indispensabile.'}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Interpretazione</div>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{indicator.interpretation}</p>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Quando funziona</div>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{indicator.works_when}</p>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Quando non funziona</div>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{indicator.fails_when}</p>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Uso in strategia</div>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{indicator.strategy_use}</p>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
        <div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Esempio pratico</div>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{indicator.example}</p>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Errori comuni</div>
          <ul className="mt-2 space-y-2 text-sm text-slate-300">
            {indicator.common_mistakes.map((mistake) => (
              <li key={mistake} className="flex gap-2">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300" />
                <span>{mistake}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </article>
  )
}

export default function AcademyClient() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [data, setData] = useState<AcademyBootstrapPayload | null>(null)
  const [selectedModuleId, setSelectedModuleId] = useState<string | null>(null)
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(null)
  const [selectedIndicatorId, setSelectedIndicatorId] = useState<string | null>(null)
  const [profileLevel, setProfileLevel] = useState<AcademyLevel>('beginner')
  const [profileText, setProfileText] = useState('')
  const [loading, setLoading] = useState(true)
  const [savingProfile, setSavingProfile] = useState(false)
  const [updatingLesson, setUpdatingLesson] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<AcademySearchResult[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const lastViewedRef = useRef<string | null>(null)
  const profileTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const lessonDetailRef = useRef<HTMLElement | null>(null)

  const applyPayload = (payload: AcademyBootstrapPayload, preferred?: { moduleId?: string | null; lessonId?: string | null }) => {
    setData(payload)
    setProfileLevel((payload.profile.detected_level as AcademyLevel) || 'beginner')
    setProfileText(payload.profile.freeform_background || '')
    const selection = resolveSelection(payload, preferred || { moduleId: selectedModuleId, lessonId: selectedLessonId })
    setSelectedModuleId(selection.moduleId)
    setSelectedLessonId(selection.lessonId)
  }

  const loadBootstrap = async (preferred?: { moduleId?: string | null; lessonId?: string | null }) => {
    setLoading(true)
    setError(null)
    try {
      const payload = await academyApi.bootstrap() as AcademyBootstrapPayload
      applyPayload(payload, preferred)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBootstrap()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.trim().length < 2) {
      setSearchResults([])
      setSearchLoading(false)
      return
    }
    setSearchLoading(true)
    const timeout = window.setTimeout(async () => {
      try {
        const result = await academyApi.search(searchQuery) as { query: string; results: AcademySearchResult[] }
        setSearchResults(result.results || [])
      } catch {
        setSearchResults([])
      } finally {
        setSearchLoading(false)
      }
    }, 180)
    return () => window.clearTimeout(timeout)
  }, [searchQuery])

  useEffect(() => {
    const node = profileTextareaRef.current
    if (!node) return
    node.style.height = '0px'
    node.style.height = `${Math.max(42, node.scrollHeight)}px`
  }, [profileText])

  const selectedModule = useMemo(
    () => data?.catalog.modules.find((module) => module.id === selectedModuleId) || null,
    [data, selectedModuleId],
  )

  const selectedLesson = useMemo(
    () => selectedModule?.lessons.find((lesson) => lesson.id === selectedLessonId) || pickLesson(selectedModule || undefined) || null,
    [selectedLessonId, selectedModule],
  )

  useEffect(() => {
    if (!data || !selectedModuleId || !selectedLessonId) return
    const key = `${selectedModuleId}:${selectedLessonId}`
    if (lastViewedRef.current === key) return
    lastViewedRef.current = key
    academyApi
      .markViewed(selectedModuleId, selectedLessonId)
      .then((payload) => applyPayload(payload as AcademyBootstrapPayload, { moduleId: selectedModuleId, lessonId: selectedLessonId }))
      .catch(() => null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, selectedModuleId, selectedLessonId])

  const handleSelectModule = (module: AcademyModule) => {
    if (module.locked) return
    setSelectedModuleId(module.id)
    setSelectedLessonId(pickLesson(module)?.id || null)
    setSelectedIndicatorId(null)
  }

  const handleSelectSearchResult = (result: AcademySearchResult) => {
    setSearchQuery('')
    setSearchResults([])
    const module = data?.catalog.modules.find((item) => item.id === result.module_id)
    if (!module) return
    setSelectedModuleId(module.id)
    setSelectedLessonId(result.lesson_id || pickLesson(module)?.id || null)
    setSelectedIndicatorId(result.indicator_id || null)
  }

  const handleToggleLesson = async (lesson: AcademyLesson) => {
    if (!selectedModule) return
    setUpdatingLesson(lesson.id)
    setError(null)
    try {
      const payload = await academyApi.setLessonProgress(selectedModule.id, lesson.id, !lesson.completed) as AcademyBootstrapPayload
      applyPayload(payload, { moduleId: selectedModule.id, lessonId: lesson.id })
    } catch (e) {
      setError(formatError(e))
    } finally {
      setUpdatingLesson(null)
    }
  }

  const openLesson = (moduleId: string, lessonId: string) => {
    setSelectedModuleId(moduleId)
    setSelectedLessonId(lessonId)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        lessonDetailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    })
  }

  const handleSaveProfile = async () => {
    setSavingProfile(true)
    setError(null)
    try {
      const payload = await academyApi.updateProfile({
        level_input: profileLevel,
        freeform_background: profileText,
      }) as AcademyBootstrapPayload
      applyPayload(payload)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setSavingProfile(false)
    }
  }

  const latestLessons = data?.dashboard.latest_lessons || []

  return (
    <div className={`min-h-screen bg-slate-950 text-slate-100 transition-[padding] duration-200 ${sidebarOpen ? 'xl:pl-80' : 'xl:pl-0'}`}>
      <AppSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-h-screen">
        <aside className="hidden w-80 shrink-0 border-r border-slate-800 bg-slate-950 xl:flex xl:flex-col sticky top-0 h-screen">
          <div className="border-b border-slate-800 px-6 py-6 md:pl-[3.25rem]">
            <div className="text-[11px] uppercase tracking-[0.28em] text-cyan-300">Algorithmic Trading Academy</div>
            <div className="mt-3 text-2xl font-semibold text-slate-50">Percorso completo</div>
            <div className="mt-3">
              <ProgressBar value={data?.dashboard.total_progress_pct || 0} max={100} label="Progresso totale" />
            </div>
          </div>

          <div className="space-y-4 overflow-y-auto px-5 py-5">
            {(data?.catalog.modules || []).map((module) => (
              <button
                key={module.id}
                onClick={() => handleSelectModule(module)}
                disabled={module.locked}
                className={`w-full border p-4 text-left transition-colors ${
                  selectedModuleId === module.id
                    ? 'border-cyan-700/70 bg-cyan-950/12'
                    : module.locked
                      ? 'border-slate-900 bg-slate-950/60 text-slate-600'
                      : 'border-slate-800 bg-slate-950/72 hover:border-slate-700'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{module.category}</div>
                    <div className="mt-2 text-sm font-semibold text-slate-100">{module.title}</div>
                  </div>
                    <span className={`shrink-0 border px-2 py-1 text-[10px] uppercase tracking-[0.16em] ${statusTone(module.status)}`}>
                    {module.status === 'completed' ? 'Completato' : module.status === 'locked' ? 'Bloccato' : 'In corso'}
                  </span>
                </div>
                <div className="mt-4">
                  <ProgressBar value={module.progress_pct} max={100} />
                </div>
                <div className="mt-3 text-xs text-slate-500">
                  {module.completed_lessons}/{module.total_lessons} lezioni · {module.estimated_hours.toFixed(1)}h
                </div>
              </button>
            ))}
          </div>
        </aside>

        <main className="flex-1 flex flex-col min-h-screen">
          <header className="border-b border-slate-800 px-6 py-4 lg:px-8 flex items-center justify-between sticky top-0 bg-slate-950/95 backdrop-blur z-40">
            <div className="flex items-center gap-3 md:pl-2">
              <button
                type="button"
                aria-label={sidebarOpen ? "Chiudi navigazione" : "Apri navigazione"}
                onClick={() => setSidebarOpen((current) => !current)}
                className="flex h-11 w-11 shrink-0 items-center justify-center border border-slate-800 text-slate-300 transition-colors hover:border-slate-700 hover:text-slate-100"
              >
                <span className="flex flex-col gap-1.5">
                  <span className="block h-0.5 w-4 bg-current" />
                  <span className="block h-0.5 w-4 bg-current" />
                  <span className="block h-0.5 w-4 bg-current" />
                </span>
              </button>
              <div>
                <div className="text-[10px] uppercase tracking-widest text-slate-500">Visari Trading Room</div>
                <div className="text-xl font-bold bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
                  Algorithmic Trading Academy
                </div>
              </div>
            </div>
            <AuthToolbar />
          </header>

          <div className="flex-1 overflow-y-auto px-6 py-8 lg:px-12">
            <div className="mx-auto max-w-7xl space-y-6">
              {loading && <Spinner label="Carico Academy..." />}

              {!loading && error && (
                <div className="border border-rose-900/70 bg-rose-950/10 px-4 py-3 text-sm text-rose-200">
                  {error}
                </div>
              )}

              {!loading && data && (
                <>
                  <section className="border border-slate-800/90 bg-[linear-gradient(135deg,rgba(8,47,73,0.24),rgba(15,23,42,0.88)_42%,rgba(2,6,23,0.96))] px-6 py-7 lg:px-8">
                    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-end">
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.26em] text-cyan-300">Academy</div>
                        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-50 lg:text-5xl">
                          Da base solida a bot realmente governabili.
                        </h1>
                        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-400">
                          Un percorso tecnico, progressivo e operativo per trasformare conoscenza quantitativa in builder, bot, validazione e controllo runtime dentro Visari.
                        </p>
                      </div>
                      <div className="border border-slate-800 bg-slate-950/60 p-5">
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Continua da qui</div>
                        {data.dashboard.continue_from_here ? (
                          <div className="mt-3 space-y-3">
                            <div className="text-lg font-semibold text-slate-50">{data.dashboard.continue_from_here.lesson_title}</div>
                            <div className="text-sm text-slate-400">{data.dashboard.continue_from_here.module_title}</div>
                            <button
                              onClick={() => {
                                setSelectedModuleId(data.dashboard.continue_from_here?.module_id || null)
                                setSelectedLessonId(data.dashboard.continue_from_here?.lesson_id || null)
                              }}
                              className="border border-cyan-700/70 bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-cyan-400"
                            >
                              Riprendi
                            </button>
                          </div>
                        ) : (
                          <div className="mt-3 text-sm text-slate-500">Nessuna lezione avviata ancora.</div>
                        )}
                      </div>
                    </div>
                  </section>

                  <section className="grid gap-4 xl:grid-cols-4">
                    <div className="border border-slate-800 bg-slate-950/72 p-5">
                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Progresso totale</div>
                      <div className="mt-3 text-3xl font-semibold text-cyan-300">{data.dashboard.total_progress_pct}%</div>
                      <div className="mt-2 text-sm text-slate-500">
                        {data.dashboard.completed_lessons}/{data.dashboard.total_lessons} lezioni completate
                      </div>
                    </div>
                    <div className="border border-slate-800 bg-slate-950/72 p-5">
                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Livello rilevato</div>
                      <div className="mt-3 text-3xl font-semibold text-slate-50">{levelLabel(data.profile.detected_level)}</div>
                      <div className="mt-2 text-sm text-slate-500">Percorso adattato al tuo profilo operativo.</div>
                    </div>
                    <div className="border border-slate-800 bg-slate-950/72 p-5">
                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Modulo consigliato</div>
                      <div className="mt-3 text-xl font-semibold text-slate-50">{data.dashboard.personalized_suggestion.module_title}</div>
                      <div className="mt-2 text-sm leading-relaxed text-slate-500">{data.dashboard.personalized_suggestion.reason}</div>
                    </div>
                    <div className="border border-slate-800 bg-slate-950/72 p-5">
                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Ultime lezioni</div>
                      <div className="mt-3 space-y-2 text-sm">
                        {latestLessons.slice(0, 3).map((lesson: AcademyLatestLesson) => (
                          <button
                            key={lesson.lesson_id}
                            onClick={() => {
                              setSelectedModuleId(lesson.module_id)
                              setSelectedLessonId(lesson.lesson_id)
                            }}
                            className="block text-left text-slate-300 transition-colors hover:text-slate-100"
                          >
                            {lesson.lesson_title}
                          </button>
                        ))}
                        {!latestLessons.length && <div className="text-slate-500">Nessuna attività recente.</div>}
                      </div>
                    </div>
                  </section>

                  <section className="border border-slate-800 bg-slate-950/72 p-4">
                    <div className="grid gap-4 xl:grid-cols-[minmax(0,0.78fr)_290px] xl:items-start">
                      <div className="relative max-w-3xl">
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Ricerca Academy</div>
                        <input
                          value={searchQuery}
                          onChange={(event) => setSearchQuery(event.target.value)}
                          placeholder="Cerca moduli, lezioni, indicatori"
                          className={`${inputCls} mt-3 py-2.5`}
                        />
                        {(searchLoading || searchResults.length > 0) && (
                          <div className="absolute left-0 right-0 top-[84px] z-20 border border-slate-800 bg-slate-950 shadow-2xl">
                            {searchLoading && <div className="px-4 py-3 text-sm text-slate-500">Ricerca in corso...</div>}
                            {!searchLoading &&
                              searchResults.map((result) => (
                                <button
                                  key={`${result.kind}-${result.id}`}
                                  onClick={() => handleSelectSearchResult(result)}
                                  className="block w-full border-b border-slate-900 px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-slate-900/70"
                                >
                                  <div className="text-sm font-semibold text-slate-100">{result.title}</div>
                                  <div className="mt-1 text-xs uppercase tracking-[0.16em] text-cyan-300">{result.subtitle}</div>
                                  <div className="mt-1 text-sm text-slate-500">{result.snippet}</div>
                                </button>
                              ))}
                          </div>
                        )}
                      </div>

                      <div className="border border-slate-800 bg-slate-950/70 p-4">
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Dimmi il tuo livello</div>
                        <div className="mt-3 grid gap-2">
                          {LEVEL_OPTIONS.map((option) => (
                            <button
                              key={option.id}
                              onClick={() => setProfileLevel(option.id)}
                              className={`border px-3 py-3 text-left transition-colors ${
                                profileLevel === option.id
                                  ? 'border-cyan-700/70 bg-cyan-950/12 text-slate-50'
                                  : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                              }`}
                            >
                              <div className="text-sm font-semibold">{option.label}</div>
                              <div className="mt-1 text-xs">{option.detail}</div>
                            </button>
                          ))}
                        </div>
                        <textarea
                          ref={profileTextareaRef}
                          value={profileText}
                          onChange={(event) => setProfileText(event.target.value)}
                          rows={1}
                          placeholder="Oppure descrivi in poche righe cosa sai già e cosa vuoi ottenere."
                          className={`${textareaCls} mt-3 min-h-[42px] overflow-hidden py-2.5`}
                        />
                        <button
                          onClick={handleSaveProfile}
                          disabled={savingProfile}
                          className="mt-3 w-full border border-cyan-700/70 bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-cyan-400 disabled:opacity-70"
                        >
                          {savingProfile ? 'Aggiorno...' : 'Aggiorna percorso'}
                        </button>
                      </div>
                    </div>
                  </section>

                  <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_310px]">
                    <div className="space-y-6">
                      {!selectedModule && (
                        <EmptyState icon="ACADEMY" title="Seleziona un modulo" description="Scegli un modulo dalla sidebar per iniziare." />
                      )}

                      {selectedModule && (
                        <>
                          <section className="border border-slate-800 bg-slate-950/72 p-6">
                            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
                              Academy / {selectedModule.category} / {selectedModule.title}
                            </div>
                            <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
                              <div>
                                <h2 className="text-3xl font-semibold tracking-tight text-slate-50">{selectedModule.title}</h2>
                                <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-400">{selectedModule.description}</p>
                              </div>
                              <div className={`border px-3 py-2 text-[11px] uppercase tracking-[0.18em] ${statusTone(selectedModule.status)}`}>
                                {selectedModule.status === 'completed' ? 'Completato' : selectedModule.locked ? 'Bloccato' : 'In corso'}
                              </div>
                            </div>
                            <div className="mt-5 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
                              <div className="border border-slate-800 bg-slate-950/60 p-4">
                                <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Obiettivi pratici</div>
                                <ul className="mt-3 space-y-2 text-sm text-slate-300">
                                  {selectedModule.objectives.map((objective) => (
                                    <li key={objective} className="flex gap-2">
                                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-300" />
                                      <span>{objective}</span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                              <div className="border border-slate-800 bg-slate-950/60 p-4">
                                <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Modulo</div>
                                <div className="mt-3 grid gap-3">
                                  <div className="text-sm text-slate-300">{selectedModule.total_lessons} lezioni</div>
                                  <div className="text-sm text-slate-300">{selectedModule.estimated_hours.toFixed(1)} ore stimate</div>
                                  <div className="text-sm text-slate-300">{selectedModule.difficulty}</div>
                                  <ProgressBar value={selectedModule.progress_pct} max={100} label="Avanzamento modulo" />
                                </div>
                              </div>
                            </div>
                          </section>

                          <section className="space-y-4">
                            <div className="flex items-center justify-between">
                              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Lezioni</div>
                              <div className="text-xs text-slate-500">
                                {selectedModule.completed_lessons}/{selectedModule.total_lessons} completate
                              </div>
                            </div>
                            <div className="grid gap-4 lg:grid-cols-2">
                              {selectedModule.lessons.map((lesson) => (
                                <LessonCard
                                  key={lesson.id}
                                  lesson={lesson}
                                  active={selectedLesson?.id === lesson.id}
                                  onSelect={() => openLesson(selectedModule.id, lesson.id)}
                                  onToggle={() => handleToggleLesson(lesson)}
                                />
                              ))}
                            </div>
                          </section>

                          {selectedLesson && (
                            <section ref={lessonDetailRef} className="border border-slate-800 bg-slate-950/72 p-6">
                              <div className="flex flex-wrap items-start justify-between gap-4">
                                <div>
                                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Lezione attiva</div>
                                  <h3 className="mt-2 text-3xl font-semibold tracking-tight text-slate-50">{selectedLesson.title}</h3>
                                  <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-400">{selectedLesson.summary}</p>
                                </div>
                                <button
                                  onClick={() => handleToggleLesson(selectedLesson)}
                                  disabled={updatingLesson === selectedLesson.id}
                                  className={`border px-4 py-2 text-sm font-semibold transition-colors ${
                                    selectedLesson.completed
                                      ? 'border-emerald-900/70 bg-emerald-950/12 text-emerald-300'
                                      : 'border-cyan-700/70 bg-cyan-500 text-slate-950 hover:bg-cyan-400'
                                  }`}
                                >
                                  {selectedLesson.completed ? 'Lezione completata' : updatingLesson === selectedLesson.id ? 'Salvo...' : 'Segna completata'}
                                </button>
                              </div>

                              <div className="mt-6 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
                                <div className="space-y-5">
                                  {selectedLesson.why_it_matters && (
                                    <div className="border border-slate-800 bg-slate-950/60 p-5">
                                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Perché conta davvero</div>
                                      <p className="mt-3 text-sm leading-relaxed text-slate-300">{selectedLesson.why_it_matters}</p>
                                    </div>
                                  )}

                                  <div className="border border-slate-800 bg-slate-950/60 p-5">
                                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Teoria operativa</div>
                                    <p className="mt-3 text-sm leading-relaxed text-slate-300">{selectedLesson.theory}</p>
                                  </div>

                                  {!!selectedLesson.framework?.length && (
                                    <div className="border border-slate-800 bg-slate-950/60 p-5">
                                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Framework operativo</div>
                                      <BulletList items={selectedLesson.framework} tone="slate" />
                                    </div>
                                  )}

                                  {!!selectedLesson.deep_sections?.length && (
                                    <div className="grid gap-5 lg:grid-cols-2">
                                      {selectedLesson.deep_sections.map((section) => (
                                        <div key={`${selectedLesson.id}-${section.title}`} className="border border-slate-800 bg-slate-950/60 p-5">
                                          <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{section.title}</div>
                                          <p className="mt-3 text-sm leading-relaxed text-slate-300">{section.body}</p>
                                          {!!section.bullets?.length && <BulletList items={section.bullets} tone={section.tone || 'slate'} />}
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  <div className="grid gap-5 lg:grid-cols-2">
                                    <div className="border border-slate-800 bg-slate-950/60 p-5">
                                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Cosa fare in pratica</div>
                                      <BulletList items={selectedLesson.practical} tone="cyan" />
                                    </div>
                                    <div className="border border-slate-800 bg-slate-950/60 p-5">
                                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Errori comuni</div>
                                      <BulletList items={selectedLesson.mistakes} tone="amber" />
                                    </div>
                                  </div>

                                  {selectedLesson.case_study && (
                                    <div className="border border-slate-800 bg-slate-950/60 p-5">
                                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Caso reale</div>
                                      <p className="mt-3 text-sm leading-relaxed text-slate-300">{selectedLesson.case_study}</p>
                                    </div>
                                  )}

                                  {!!selectedLesson.app_exercise?.length && (
                                    <div className="border border-slate-800 bg-slate-950/60 p-5">
                                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Esercizio dentro Visari</div>
                                      <BulletList items={selectedLesson.app_exercise} tone="cyan" />
                                    </div>
                                  )}
                                </div>

                                <div className="space-y-5">
                                  <div className="border border-slate-800 bg-slate-950/60 p-5">
                                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Collegamento con Visari</div>
                                    <div className="mt-3 grid gap-3">
                                      {selectedLesson.app_links.map((link) => (
                                        <Link
                                          key={`${selectedLesson.id}-${link.href}`}
                                          href={link.href}
                                          className="border border-slate-800 px-4 py-3 text-sm font-semibold text-slate-100 transition-colors hover:border-slate-700 hover:text-white"
                                        >
                                          {link.label}
                                        </Link>
                                      ))}
                                    </div>
                                  </div>
                                  <div className="border border-slate-800 bg-slate-950/60 p-5">
                                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Meta lezione</div>
                                    <div className="mt-3 space-y-2 text-sm text-slate-300">
                                      <div>Difficoltà: {selectedLesson.difficulty}</div>
                                      <div>Durata stimata: {selectedLesson.duration_min} min</div>
                                      <div>Ultima apertura: {shortDate(selectedLesson.last_viewed_at)}</div>
                                    </div>
                                  </div>
                                  {!!selectedLesson.checklist?.length && (
                                    <div className="border border-slate-800 bg-slate-950/60 p-5">
                                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Checklist</div>
                                      <BulletList items={selectedLesson.checklist} tone="slate" />
                                    </div>
                                  )}
                                  {!!selectedLesson.before_continue?.length && (
                                    <div className="border border-slate-800 bg-slate-950/60 p-5">
                                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Prima di continuare</div>
                                      <BulletList items={selectedLesson.before_continue} tone="amber" />
                                    </div>
                                  )}
                                </div>
                              </div>
                            </section>
                          )}

                          {selectedModule.indicator_categories && (
                            <section className="space-y-5 border border-slate-800 bg-slate-950/72 p-6">
                              <div className="flex flex-wrap items-center gap-3">
                                <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Signal & Indicator Library</div>
                                <div className="text-sm text-slate-500">Enciclopedia pratica dei segnali con uso, limiti e integrazione in strategia.</div>
                              </div>

                              {selectedIndicatorId && (
                                <div className="border border-cyan-700/70 bg-cyan-950/12 p-5">
                                  <div className="text-[11px] uppercase tracking-[0.18em] text-cyan-300">Indicatore in evidenza</div>
                                  <div className="mt-2 text-lg font-semibold text-slate-50">
                                    {selectedModule.indicator_categories.flatMap((category) => category.indicators).find((item) => item.id === selectedIndicatorId)?.name}
                                  </div>
                                </div>
                              )}

                              {selectedModule.indicator_categories.map((category) => (
                                <div key={category.id} className="space-y-4">
                                  <div>
                                    <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{category.title}</div>
                                    <p className="mt-2 max-w-4xl text-sm leading-relaxed text-slate-400">{category.description}</p>
                                  </div>
                                  <div className="grid gap-4 xl:grid-cols-2">
                                    {category.indicators.map((indicator) => (
                                      <IndicatorCard
                                        key={indicator.id}
                                        indicator={indicator}
                                        highlighted={indicator.id === selectedIndicatorId}
                                      />
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </section>
                          )}
                        </>
                      )}
                    </div>

                    <aside className="space-y-5">
                      <section className="border border-slate-800 bg-slate-950/72 p-5">
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Dashboard Academy</div>
                        <div className="mt-4 space-y-4">
                          {data.dashboard.modules.slice(0, 6).map((module) => (
                            <div key={module.module_id}>
                              <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                                <span>{module.title}</span>
                                <span>{module.progress_pct}%</span>
                              </div>
                              <ProgressBar value={module.progress_pct} max={100} />
                            </div>
                          ))}
                        </div>
                      </section>

                      <section className="border border-slate-800 bg-slate-950/72 p-5">
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Suggerimento personalizzato</div>
                        <div className="mt-3 text-lg font-semibold text-slate-50">{data.dashboard.personalized_suggestion.module_title}</div>
                        <p className="mt-2 text-sm leading-relaxed text-slate-400">{data.dashboard.personalized_suggestion.reason}</p>
                        <button
                          onClick={() => {
                            const target = data.catalog.modules.find((module) => module.id === data.dashboard.personalized_suggestion.module_id)
                            if (!target) return
                            setSelectedModuleId(target.id)
                            setSelectedLessonId(pickLesson(target)?.id || null)
                          }}
                          className="mt-4 w-full border border-slate-800 px-4 py-3 text-sm font-semibold text-slate-100 transition-colors hover:border-slate-700"
                        >
                          Apri percorso consigliato
                        </button>
                      </section>

                      <section className="border border-slate-800 bg-slate-950/72 p-5">
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Ultime lezioni viste</div>
                        <div className="mt-4 space-y-3">
                          {latestLessons.length ? (
                            latestLessons.map((lesson) => (
                              <button
                                key={lesson.lesson_id}
                                onClick={() => {
                                  setSelectedModuleId(lesson.module_id)
                                  setSelectedLessonId(lesson.lesson_id)
                                }}
                                className="block w-full border border-slate-800 bg-slate-950/60 px-4 py-3 text-left transition-colors hover:border-slate-700"
                              >
                                <div className="text-sm font-semibold text-slate-100">{lesson.lesson_title}</div>
                                <div className="mt-1 text-xs text-slate-500">{lesson.module_title}</div>
                              </button>
                            ))
                          ) : (
                            <div className="text-sm text-slate-500">Inizia una lezione e qui vedrai il tuo storico recente.</div>
                          )}
                        </div>
                      </section>
                    </aside>
                  </section>
                </>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
