'use client'

import { useEffect, useMemo, useState } from 'react'
import AuthToolbar from '@/components/AuthToolbar'
import AppSidebar from '@/components/layout/AppSidebar'
import ReferralPanel from '@/components/referral/ReferralPanel'
import { Alert, EmptyState, MetricCard, ProgressBar, inputCls } from '@/components/ui'
import { formatError, teamApi } from '@/lib/api'
import type { ProjectSummary, TeamRecord } from '@/types'

type BootstrapPayload = {
  ok: boolean
  teams: TeamRecord[]
  projects: ProjectSummary[]
}

type MemberDraft = {
  username: string
  role: string
}

const ACCENT_OPTIONS = [
  { value: 'cyan', label: 'Cyan' },
  { value: 'amber', label: 'Amber' },
  { value: 'emerald', label: 'Emerald' },
  { value: 'rose', label: 'Rose' },
  { value: 'slate', label: 'Slate' },
]

function teamCompletion(team: TeamRecord) {
  let score = 35
  if (team.brand_name) score += 15
  if (team.support_email) score += 10
  if (team.legal_label) score += 10
  if ((team.members || []).length > 1) score += 15
  if (team.white_label_enabled) score += 15
  return Math.min(score, 100)
}

export default function TeamStudioClient() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<BootstrapPayload | null>(null)
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null)
  const [newTeamName, setNewTeamName] = useState('')

  const [brandName, setBrandName] = useState('')
  const [accent, setAccent] = useState('cyan')
  const [supportEmail, setSupportEmail] = useState('')
  const [legalLabel, setLegalLabel] = useState('')
  const [workspaceLabel, setWorkspaceLabel] = useState('Desk team')
  const [brandFooter, setBrandFooter] = useState('')
  const [whiteLabelEnabled, setWhiteLabelEnabled] = useState(false)
  const [members, setMembers] = useState<MemberDraft[]>([])

  async function loadBootstrap(preferredTeamId?: string | null) {
    setLoading(true)
    setError(null)
    try {
      const payload = (await teamApi.bootstrap()) as BootstrapPayload
      setData(payload)
      const nextSelected =
        preferredTeamId ||
        payload.teams.find((team) => team.team_id === selectedTeamId)?.team_id ||
        payload.teams[0]?.team_id ||
        null
      setSelectedTeamId(nextSelected)
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

  const selectedTeam = useMemo(
    () => data?.teams.find((team) => team.team_id === selectedTeamId) || null,
    [data, selectedTeamId],
  )

  useEffect(() => {
    if (!selectedTeam) return
    setBrandName(selectedTeam.brand_name || selectedTeam.name || '')
    setAccent(selectedTeam.primary_accent || 'cyan')
    setSupportEmail(selectedTeam.support_email || '')
    setLegalLabel(selectedTeam.legal_label || '')
    setWhiteLabelEnabled(Boolean(selectedTeam.white_label_enabled))
    setWorkspaceLabel(String(selectedTeam.settings?.workspace_label || 'Desk team'))
    setBrandFooter(String(selectedTeam.settings?.brand_footer || ''))
    setMembers(
      selectedTeam.members
        ? selectedTeam.members
            .filter((member) => member.role !== 'owner')
            .map((member) => ({ username: member.username, role: member.role }))
        : [],
    )
  }, [selectedTeam])

  const sharedProjects = useMemo(
    () => (data?.projects || []).filter((project) => project.metadata?.team_id === selectedTeamId),
    [data?.projects, selectedTeamId],
  )

  const availableProjects = useMemo(
    () => (data?.projects || []).filter((project) => project.mode === 'strategy' || project.mode === 'botlab'),
    [data?.projects],
  )

  async function createTeam() {
    const name = newTeamName.trim()
    if (name.length < 2) {
      setError('Inserisci un nome team piu chiaro prima di creare il workspace condiviso.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const response = (await teamApi.create(name)) as { team?: TeamRecord }
      setNewTeamName('')
      await loadBootstrap(response.team?.team_id || null)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setSaving(false)
    }
  }

  async function saveBranding() {
    if (!selectedTeamId) return
    setSaving(true)
    setError(null)
    try {
      await teamApi.updateBranding(selectedTeamId, {
        brand_name: brandName,
        primary_accent: accent,
        support_email: supportEmail,
        legal_label: legalLabel,
        white_label_enabled: whiteLabelEnabled,
        settings: {
          workspace_label: workspaceLabel,
          brand_footer: brandFooter,
        },
      })
      await loadBootstrap(selectedTeamId)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setSaving(false)
    }
  }

  async function saveMembers() {
    if (!selectedTeamId) return
    setSaving(true)
    setError(null)
    try {
      await teamApi.replaceMembers(
        selectedTeamId,
        members
          .map((member) => ({
            username: member.username.trim().toLowerCase(),
            role: member.role,
          }))
          .filter((member) => member.username),
      )
      await loadBootstrap(selectedTeamId)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setSaving(false)
    }
  }

  async function toggleProjectShare(projectId: string, currentlyShared: boolean) {
    if (!selectedTeamId) return
    setSaving(true)
    setError(null)
    try {
      await teamApi.shareProject(projectId, currentlyShared ? null : selectedTeamId)
      await loadBootstrap(selectedTeamId)
    } catch (e) {
      setError(formatError(e))
    } finally {
      setSaving(false)
    }
  }

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 xl:pl-80">
        <AppSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="p-8 text-sm text-slate-400">Caricamento team mode...</div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen bg-slate-950 text-slate-100 transition-[padding] duration-200 ${sidebarOpen ? 'xl:pl-80' : 'xl:pl-0'}`}>
      <AppSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <header className="sticky top-0 z-50 flex items-center justify-between border-b border-slate-800 bg-slate-950/90 px-6 py-4 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label={sidebarOpen ? 'Chiudi navigazione' : 'Apri navigazione'}
            onClick={() => setSidebarOpen((current) => !current)}
            className="flex h-11 w-11 items-center justify-center border border-slate-800 text-slate-300 transition-colors hover:border-slate-700 hover:text-slate-100"
          >
            <span className="flex flex-col gap-1.5">
              <span className="block h-0.5 w-4 bg-current" />
              <span className="block h-0.5 w-4 bg-current" />
              <span className="block h-0.5 w-4 bg-current" />
            </span>
          </button>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-cyan-500">Team mode</div>
            <div className="text-xl font-semibold text-slate-50">Collaborazione e white label</div>
          </div>
        </div>
        <AuthToolbar />
      </header>

      <main className="mx-auto max-w-7xl space-y-8 px-6 py-8 lg:px-10">
        <section className="border border-slate-800 bg-slate-950/70 p-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Governance condivisa</div>
              <h1 className="mt-2 text-3xl font-semibold text-slate-50">Team mode per ricerca, consegna e brand</h1>
              <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-400">
                Crea workspace condivise, assegna membri, distribuisci progetti e prepara un layer white label senza toccare i workflow principali di builder, desk o Bot Lab.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <MetricCard label="Team attivi" value={data?.teams.length || 0} />
              <MetricCard
                label="Membri gestiti"
                value={data?.teams.reduce((sum, team) => sum + (team.members || []).length, 0) || 0}
              />
              <MetricCard label="Progetti condivisi" value={sharedProjects.length} />
            </div>
          </div>
        </section>

        {/* === PROGRAMMA REFERRAL === */}
        <section className="border border-amber-800/30 bg-slate-950/70 p-6">
          <div className="mb-5">
            <div className="text-[11px] uppercase tracking-[0.18em] text-amber-400">Programma Referral</div>
            <h2 className="mt-2 text-2xl font-semibold text-slate-50">Invita la community, guadagna mesi gratis</h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
              Porta nuovi membri nella community: chi si iscrive col tuo codice ha il 60% di sconto sul primo mese,
              tu ricevi 1 mese gratis per ogni amico che si abbona.
            </p>
          </div>
          <ReferralPanel />
        </section>

        {error && <Alert type="error">{error}</Alert>}

        <div className="grid gap-8 xl:grid-cols-[0.85fr_1.15fr]">
          <section className="space-y-6">
            <div className="border border-slate-800 bg-slate-950/70 p-5">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Nuovo team</div>
              <div className="mt-4 flex gap-3">
                <input
                  value={newTeamName}
                  onChange={(event) => setNewTeamName(event.target.value)}
                  className={inputCls}
                  placeholder="Desk FX Europa"
                />
                <button
                  type="button"
                  onClick={createTeam}
                  disabled={saving}
                  className="border border-slate-200 bg-slate-100 px-5 py-3 text-sm font-semibold text-slate-950 transition-colors hover:bg-white disabled:opacity-50"
                >
                  Crea
                </button>
              </div>
            </div>

            <div className="border border-slate-800 bg-slate-950/70 p-5">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">I tuoi team</div>
              <div className="mt-4 space-y-3">
                {(data?.teams || []).map((team) => {
                  const active = team.team_id === selectedTeamId
                  const completion = teamCompletion(team)
                  return (
                    <button
                      key={team.team_id}
                      type="button"
                      onClick={() => setSelectedTeamId(team.team_id)}
                      className={`w-full space-y-3 border p-4 text-left transition-colors ${
                        active ? 'border-cyan-700/70 bg-cyan-950/12' : 'border-slate-800 bg-slate-950 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-lg font-semibold text-slate-50">{team.brand_name || team.name}</div>
                          <div className="mt-1 text-sm text-slate-500">{(team.members || []).length} membri · {team.white_label_enabled ? 'white label attivo' : 'modalita standard'}</div>
                        </div>
                        <div className="border border-slate-800 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-slate-400">
                          {team.primary_accent}
                        </div>
                      </div>
                      <ProgressBar value={completion} max={100} label="Prontezza team" />
                    </button>
                  )
                })}
                {!data?.teams.length && (
                  <EmptyState
                    icon="TEAM"
                    title="Nessun team creato"
                    description="Crea il primo team per condividere progetti e preparare una presentazione piu professionale verso clienti o collaboratori."
                  />
                )}
              </div>
            </div>
          </section>

          <section className="space-y-6">
            {selectedTeam ? (
              <>
                <div className="border border-slate-800 bg-slate-950/70 p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Branding e white label</div>
                      <div className="mt-2 text-2xl font-semibold text-slate-50">{selectedTeam.brand_name || selectedTeam.name}</div>
                    </div>
                    <button
                      type="button"
                      onClick={saveBranding}
                      disabled={saving}
                      className="border border-slate-200 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-white disabled:opacity-50"
                    >
                      Salva branding
                    </button>
                  </div>

                  <div className="mt-5 grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Brand name</div>
                      <input value={brandName} onChange={(event) => setBrandName(event.target.value)} className={inputCls} />
                    </div>
                    <div className="space-y-2">
                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Accent</div>
                      <select value={accent} onChange={(event) => setAccent(event.target.value)} className={inputCls}>
                        {ACCENT_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Support email</div>
                      <input value={supportEmail} onChange={(event) => setSupportEmail(event.target.value)} className={inputCls} placeholder="support@desk.com" />
                    </div>
                    <div className="space-y-2">
                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Legal label</div>
                      <input value={legalLabel} onChange={(event) => setLegalLabel(event.target.value)} className={inputCls} placeholder="Desk FX SRL" />
                    </div>
                    <div className="space-y-2">
                      <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Label workspace</div>
                      <input value={workspaceLabel} onChange={(event) => setWorkspaceLabel(event.target.value)} className={inputCls} placeholder="Desk team" />
                    </div>
                    <label className="flex items-center gap-3 border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-300">
                      <input
                        type="checkbox"
                        checked={whiteLabelEnabled}
                        onChange={(event) => setWhiteLabelEnabled(event.target.checked)}
                        className="h-4 w-4 accent-cyan-400"
                      />
                      Attiva white label per consegne e demo
                    </label>
                  </div>
                  <div className="mt-4 space-y-2">
                    <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Footer brand</div>
                    <input
                      value={brandFooter}
                      onChange={(event) => setBrandFooter(event.target.value)}
                      className={inputCls}
                      placeholder="Powered by Visari Trading Room"
                    />
                  </div>
                </div>

                <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
                  <div className="border border-slate-800 bg-slate-950/70 p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Membri</div>
                        <div className="mt-2 text-lg font-semibold text-slate-50">Controllo accessi collaborativi</div>
                      </div>
                      <button
                        type="button"
                        onClick={saveMembers}
                        disabled={saving}
                        className="border border-slate-800 px-4 py-2 text-sm font-semibold text-slate-200 transition-colors hover:border-slate-600 disabled:opacity-50"
                      >
                        Salva membri
                      </button>
                    </div>

                    <div className="mt-4 space-y-3">
                      {members.map((member, index) => (
                        <div key={`${member.username}-${index}`} className="grid gap-3 md:grid-cols-[1fr_180px_44px]">
                          <input
                            value={member.username}
                            onChange={(event) =>
                              setMembers((current) =>
                                current.map((item, itemIndex) => itemIndex === index ? { ...item, username: event.target.value } : item),
                              )
                            }
                            className={inputCls}
                            placeholder="username cliente"
                          />
                          <select
                            value={member.role}
                            onChange={(event) =>
                              setMembers((current) =>
                                current.map((item, itemIndex) => itemIndex === index ? { ...item, role: event.target.value } : item),
                              )
                            }
                            className={inputCls}
                          >
                            <option value="viewer">Viewer</option>
                            <option value="editor">Editor</option>
                            <option value="admin">Admin</option>
                          </select>
                          <button
                            type="button"
                            onClick={() => setMembers((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                            className="border border-rose-950/70 px-3 py-3 text-sm text-rose-200 transition-colors hover:border-rose-700"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={() => setMembers((current) => [...current, { username: '', role: 'viewer' }])}
                        className="w-full border border-slate-800 px-4 py-3 text-sm font-semibold text-slate-300 transition-colors hover:border-slate-700 hover:text-slate-100"
                      >
                        Aggiungi membro
                      </button>
                    </div>
                  </div>

                  <div className="border border-slate-800 bg-slate-950/70 p-5">
                    <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Progetti condivisi</div>
                    <div className="mt-2 text-lg font-semibold text-slate-50">Assegna builder, Bot Lab e desk al team</div>
                    <div className="mt-4 space-y-3">
                      {availableProjects.map((project) => {
                        const shared = project.metadata?.team_id === selectedTeamId
                        return (
                          <div key={project.project_id} className="flex flex-col gap-3 border border-slate-800 bg-slate-950 p-4 md:flex-row md:items-center md:justify-between">
                            <div>
                              <div className="text-base font-semibold text-slate-100">{project.title}</div>
                              <div className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                                {project.mode === 'botlab' ? 'Bot Lab' : 'Strategia'} · {project.status}
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => toggleProjectShare(project.project_id, shared)}
                              className={`border px-4 py-2 text-sm font-semibold transition-colors ${
                                shared
                                  ? 'border-cyan-700/70 bg-cyan-950/12 text-cyan-300 hover:border-cyan-500'
                                  : 'border-slate-800 text-slate-200 hover:border-slate-600'
                              }`}
                            >
                              {shared ? 'Rimuovi dal team' : 'Condividi col team'}
                            </button>
                          </div>
                        )
                      })}
                    </div>

                    {sharedProjects.length > 0 && (
                      <div className="mt-5 border border-slate-800 bg-slate-950 p-4">
                        <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Gia assegnati</div>
                        <div className="mt-3 space-y-2 text-sm text-slate-300">
                          {sharedProjects.map((project) => (
                            <div key={project.project_id}>• {project.title}</div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <EmptyState
                icon="TEAM"
                title="Seleziona o crea un team"
                description="Da qui puoi trasformare l'app in una workspace condivisa, assegnare progetti e preparare un layer white label."
              />
            )}
          </section>
        </div>
      </main>
    </div>
  )
}
