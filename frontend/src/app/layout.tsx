import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'VisariTradingRoom — Da strategia discrezionale a bot MT5',
  description: 'Trasforma la tua strategia di trading in un Expert Advisor per MetaTrader 5. Backtest robusti, bias control, guida installazione passo passo.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="it" className="bg-stone-950">
      <body className="bg-stone-950 text-stone-100 antialiased">
        {children}
      </body>
    </html>
  )
}
