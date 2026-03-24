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
      title="Client Access"
      description="Access your strategy workspace, Bot Lab, validated backtests and MT5 delivery pipeline."
      submitLabel="Enter Platform"
      nextPath={nextPath}
      secondaryHref="/admin/login"
      secondaryLabel="Admin access"
    />
  )
}
