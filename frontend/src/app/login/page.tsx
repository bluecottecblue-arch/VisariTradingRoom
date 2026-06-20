import LoginForm from '@/components/LoginForm'

type LoginPageProps = {
  searchParams?: {
    next?: string
  }
}

export default function LoginPage({ searchParams }: LoginPageProps) {
  const nextPath = searchParams?.next || '/workspace'
  return (
    <LoginForm
      endpoint="/api/auth/login"
      title="Accesso cliente"
      description="Accedi alla tua area strategie, al Bot Lab, ai backtest validati e ai deliverable MT5."
      submitLabel="Entra in piattaforma"
      nextPath={nextPath}
      registerHref="/register"
      secondaryHref="/admin/login"
      secondaryLabel="Accesso admin"
    />
  )
}
