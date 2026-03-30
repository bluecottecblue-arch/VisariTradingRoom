import CommandCenterClient from '@/components/dashboard/CommandCenterClient'

export default async function DashboardPage({
  searchParams,
}: {
  searchParams?: Promise<{ project_id?: string }>
}) {
  const params = (await searchParams) || {}
  return <CommandCenterClient initialProjectId={params.project_id || null} />
}
