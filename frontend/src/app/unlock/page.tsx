import UnlockGate from '@/components/UnlockGate'

type UnlockPageProps = {
  searchParams?: {
    next?: string
  }
}

export default function UnlockPage({ searchParams }: UnlockPageProps) {
  const nextPath = searchParams?.next || '/'
  return <UnlockGate nextPath={nextPath} />
}
