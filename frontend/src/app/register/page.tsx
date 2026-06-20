import { Suspense } from 'react'
import RegisterForm from '@/components/RegisterForm'

export default function RegisterPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950" />}>
      <RegisterForm />
    </Suspense>
  )
}
