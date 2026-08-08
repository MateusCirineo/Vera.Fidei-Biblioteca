'use client'

import { usePathname } from 'next/navigation'
import BottomNav from '@/components/nav/BottomNav'
import SiteFooter from '@/components/SiteFooter'
import UserMenu from '@/components/nav/UserMenu'

export default function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isFullscreenViewer = pathname.startsWith('/viewer/pdf') || pathname.startsWith('/visualizar')

  if (isFullscreenViewer) {
    return <main className="min-h-dvh bg-zinc-950">{children}</main>
  }

  return (
    <>
      <header className="fixed top-0 right-0 z-40 p-3 flex justify-end">
        <UserMenu />
      </header>
      <main className="flex-1 pb-20">{children}</main>
      <SiteFooter />
      <BottomNav />
    </>
  )
}
