export const APP_GATE_COOKIE_NAME = 'vtr_access'

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

export async function createGateToken(password: string): Promise<string> {
  const data = new TextEncoder().encode(password.trim())
  const digest = await crypto.subtle.digest('SHA-256', data)
  return bytesToHex(new Uint8Array(digest))
}

export async function getExpectedGateToken(): Promise<string | null> {
  const password = process.env.APP_GATE_PASSWORD
  if (!password) return null
  return createGateToken(password)
}
