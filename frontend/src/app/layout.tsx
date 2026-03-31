import type { Metadata } from 'next'
import Image from 'next/image'
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
        <div className="pointer-events-none fixed left-4 top-5 z-50 hidden md:block">
          <Image
            src="/visari-mark.png"
            alt=""
            aria-hidden="true"
            width={30}
            height={26}
            className="opacity-75 mix-blend-screen"
            priority
          />
        </div>
        {children}
      </body>
    </html>
  )
}
