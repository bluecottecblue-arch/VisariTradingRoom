"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AuthToolbar from "@/components/AuthToolbar";
import BotLabWorkspace from "@/components/botlab/BotLabWorkspace";
import WorkspaceOverview from "@/components/workspace/WorkspaceOverview";
import { projectApi } from "@/lib/api";
import type { ProjectDetail, ProjectSummary } from "@/types";

export default function DashboardPage() {
  const [workspaceMode, setWorkspaceMode] = useState<"strategy" | "botlab">("strategy");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [currentProject, setCurrentProject] = useState<ProjectDetail | null>(null);

  async function loadProjects(preferredProjectId?: string | null) {
    try {
      const response = await projectApi.list() as { projects?: ProjectSummary[] }
      const nextProjects = response.projects || []
      setProjects(nextProjects)
      const selectedId =
        preferredProjectId ||
        currentProjectId ||
        nextProjects.find((project) => project.mode === workspaceMode)?.project_id ||
        nextProjects[0]?.project_id ||
        null
      setCurrentProjectId(selectedId)
    } catch {
      setProjects([])
    }
  }

  async function loadProjectDetail(projectId: string) {
    try {
      const response = await projectApi.detail(projectId) as { project?: ProjectDetail }
      setCurrentProject(response.project || null)
    } catch {
      setCurrentProject(null)
    }
  }

  useEffect(() => {
    loadProjects()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!currentProjectId) {
      setCurrentProject(null)
      return;
    }
    loadProjectDetail(currentProjectId)
  }, [currentProjectId])

  useEffect(() => {
    if (!projects.length) {
      if (currentProjectId !== null) setCurrentProjectId(null);
      return;
    }
    const filtered = projects.filter((project) => project.mode === workspaceMode)
    if (currentProjectId && filtered.some((p) => p.project_id === currentProjectId)) {
      return
    }
    setCurrentProjectId(filtered[0]?.project_id || projects[0]?.project_id || null)
  }, [workspaceMode, projects, currentProjectId]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Sidebar Layout */}
      <div className="flex flex-1 min-h-screen">
        <aside className="hidden w-80 shrink-0 border-r border-slate-800 bg-slate-950 xl:flex xl:flex-col sticky top-0 h-screen">
          <div className="border-b border-slate-800 px-6 py-6">
            <div className="text-[11px] uppercase tracking-[0.28em] text-amber-300">Visari Trading Room</div>
            <div className="mt-3 text-2xl font-semibold text-slate-50">Algo Engine</div>
          </div>

          <div className="space-y-8 px-6 py-6 overflow-y-auto">
            <div className="space-y-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Workspace</div>
              <button
                onClick={() => setWorkspaceMode("strategy")}
                className={`w-full border px-4 py-3 text-left text-sm transition-colors ${
                  workspaceMode === "strategy"
                    ? "border-slate-500 bg-slate-900 text-slate-100"
                    : "border-slate-800 bg-transparent text-slate-500 hover:border-slate-700 hover:text-slate-200"
                }`}
              >
                <div className="font-medium">Strategy Factory</div>
              </button>
              <button
                onClick={() => setWorkspaceMode("botlab")}
                className={`w-full border px-4 py-3 text-left text-sm transition-colors ${
                  workspaceMode === "botlab"
                    ? "border-slate-500 bg-slate-900 text-slate-100"
                    : "border-slate-800 bg-transparent text-slate-500 hover:border-slate-700 hover:text-slate-200"
                }`}
              >
                <div className="font-medium">Bot Lab</div>
              </button>
              <Link
                href="/dashboard"
                className="block w-full border border-slate-800 px-4 py-3 text-left text-sm text-slate-500 transition-colors hover:border-slate-700 hover:text-slate-200"
              >
                <div className="font-medium text-slate-100">Algo Desk</div>
              </Link>
            </div>

            <div className="space-y-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Recent Projects</div>
              <div className="space-y-2">
                {projects.filter((p) => p.mode === workspaceMode).slice(0, 8).map((project) => (
                  <button
                    key={project.project_id}
                    onClick={() => setCurrentProjectId(project.project_id)}
                    className={`w-full border px-4 py-3 text-left transition-colors ${
                      currentProjectId === project.project_id
                        ? "border-slate-500 bg-slate-900 text-slate-100"
                        : "border-slate-900 bg-transparent text-slate-500 hover:border-slate-700 hover:text-slate-200"
                    }`}
                  >
                    <div className="truncate text-sm font-medium">{project.title}</div>
                    <div className="mt-1 text-[10px] text-slate-600 uppercase tracking-tighter">{project.status}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </aside>

        <main className="flex-1 flex flex-col min-h-screen">
          <header className="border-b border-slate-800 px-6 py-4 lg:px-8 flex items-center justify-between sticky top-0 bg-slate-950 z-40">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-500">Visari Trading Room</div>
              <div className="text-xl font-bold bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
                {workspaceMode === "strategy" ? "Strategy Workspace" : "Bot Lab Workspace"}
              </div>
            </div>
            <AuthToolbar />
          </header>

          <div className="flex-1 px-6 py-8 lg:px-12 overflow-y-auto">
            <div className="max-w-7xl mx-auto space-y-12">
              <WorkspaceOverview
                workspaceMode={workspaceMode}
                setWorkspaceMode={setWorkspaceMode}
                projects={projects}
                currentProjectId={currentProjectId}
                setCurrentProjectId={setCurrentProjectId}
                createProject={async (mode) => {
                   const label = mode === "strategy" ? "New Strategy" : "New Bot Lab"
                   const res = await projectApi.create(label, mode) as any
                   if (res.project) loadProjects(res.project.project_id)
                }}
                currentProject={currentProject}
              />

              {workspaceMode === "botlab" && (
                <div className="pt-8 border-t border-slate-800">
                  <BotLabWorkspace />
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
