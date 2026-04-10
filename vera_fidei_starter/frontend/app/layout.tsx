import type { Metadata } from 'next'
import { EB_Garamond, Inter } from 'next/font/google'
import './globals.css'
import BottomNav from '@/components/nav/BottomNav'

const ebGaramond = EB_Garamond({
  variable: '--font-eb-garamond',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
})

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'Vera.Fidei — Verificador de Citações Patrísticas',
  description:
    'Plataforma católica de verificação de citações patrísticas. Busca lexical e semântica sobre fontes primárias dos Padres da Igreja.',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="pt-BR"
      className={`${ebGaramond.variable} ${inter.variable} h-full`}
    >
      <body className="flex flex-col min-h-dvh bg-fundo text-texto antialiased">
        <main className="flex-1 pb-20">{children}</main>
        <BottomNav />
      </body>
    </html>
  )
}
