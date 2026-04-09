/** @type {import('next').NextConfig} */
const defaultBackendBaseUrl =
  process.env.NODE_ENV === 'production'
    ? 'https://visari-trading-room-api.onrender.com'
    : 'http://127.0.0.1:8000'

const nextConfig = {
  output: 'standalone',
  env: {
    NEXT_PUBLIC_API_BASE_URL:
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      defaultBackendBaseUrl,
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      defaultBackendBaseUrl,
  },
}

module.exports = nextConfig
