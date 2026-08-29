import type { Metadata, Viewport } from 'next'
import { EB_Garamond, Inter } from 'next/font/google'
import './globals.css'
import PwaRegister from '@/components/PwaRegister'
import AppSplash from '@/components/AppSplash'
import AppChrome from '@/components/AppChrome'
import SiteAnalytics from '@/components/SiteAnalytics'

const PUBLIC_SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? 'https://verafidei.com.br'
).replace(/\/+$/, '')

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
  metadataBase: new URL(PUBLIC_SITE_URL),
  title: 'Vera.Fidei — Biblioteca Católica Digital',
  description:
    'Aplicativo católico criado e desenvolvido por Mateus Cirineo para biblioteca digital, consulta de fontes primárias e verificação de citações.',
  manifest: '/manifest.webmanifest',
  creator: 'Mateus Cirineo',
  authors: [{ name: 'Mateus Cirineo' }],
  applicationName: 'Vera.Fidei',
  keywords: [
    'Vera.Fidei',
    'Mateus Cirineo',
    'biblioteca católica',
    'fontes primárias',
    'verificação de citações',
    'Patrística',
  ],
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/icon.png', sizes: '512x512', type: 'image/png' },
      { url: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
      { url: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
      { url: '/icons/icon-1024.png', sizes: '1024x1024', type: 'image/png' },
    ],
    shortcut: [{ url: '/favicon.ico' }],
    apple: [{ url: '/apple-icon.png', sizes: '180x180', type: 'image/png' }],
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black',
    title: 'Vera.Fidei',
  },
  other: {
    'mobile-web-app-capable': 'yes',
    'apple-mobile-web-app-capable': 'yes',
    'apple-mobile-web-app-title': 'Vera.Fidei',
  },
  openGraph: {
    title: 'Vera.Fidei',
    description:
      'Biblioteca católica digital e verificador de citações criado por Mateus Cirineo.',
    url: PUBLIC_SITE_URL,
    siteName: 'Vera.Fidei',
    images: [{ url: '/branding/Logo-VF.png', width: 1024, height: 1024 }],
    locale: 'pt_BR',
    type: 'website',
  },
}

export const viewport: Viewport = {
  themeColor: '#111111',
  colorScheme: 'dark',
  viewportFit: 'cover',
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
        <PwaRegister />
        <SiteAnalytics />
        <AppSplash />
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  )
}
