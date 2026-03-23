import LoginForm from '@/components/LoginForm'

type LoginPageProps = {
  searchParams?: {
    next?: string
  }
}

export default function LoginPage({ searchParams }: LoginPageProps) {
  const nextPath = searchParams?.next || '/'
  return (
    <LoginForm
      endpoint="/api/auth/login"
      title="Login cliente"
      description="Entra con username e password che hai creato per il cliente."
      submitLabel="Entra nell'app"
      nextPath={nextPath}
      secondaryHref="/admin/login"
      secondaryLabel="Vai al login admin"
    />
  )
}
