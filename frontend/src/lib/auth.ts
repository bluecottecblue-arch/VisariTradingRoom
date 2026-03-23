export const SESSION_COOKIE_NAME = 'vtr_session'
export const SESSION_ROLE_COOKIE_NAME = 'vtr_role'
export const SESSION_USERNAME_COOKIE_NAME = 'vtr_username'

export function getBackendBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://127.0.0.1:8000'
  ).replace(/\/+$/, '')
}
