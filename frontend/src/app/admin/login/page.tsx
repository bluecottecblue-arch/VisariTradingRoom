import LoginForm from '@/components/LoginForm'

type AdminLoginPageProps = {
  searchParams?: {
    next?: string
  }
}

export default function AdminLoginPage({ searchParams }: AdminLoginPageProps) {
  const nextPath = searchParams?.next || '/admin'
  return (
    <LoginForm
      endpoint="/api/auth/admin/login"
      title="Login admin"
      description="Accedi con le credenziali admin per gestire gli account cliente."
      submitLabel="Entra nel pannello admin"
      nextPath={nextPath}
      secondaryHref="/login"
      secondaryLabel="Vai al login cliente"
    />
  )
}
