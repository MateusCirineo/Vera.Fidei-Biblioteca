'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  AUTH_STATE_CHANGED_EVENT,
  PROFILE_AVATAR_CHANGED_EVENT,
  getUser,
  logout,
  migrateLegacyProfileAvatar,
  type UserInfo,
} from '@/lib/auth'

const PLAN_LABELS: Record<string, string> = {
  fiel: 'Fiel',
  catequista: 'Catequista',
  apologeta: 'Apologeta',
  patristico: 'Patrístico',
  magisterio: 'Magistério',
}

export default function UserMenu() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [avatar, setAvatar] = useState('')
  const [resolved, setResolved] = useState(false)
  const [open, setOpen] = useState(false)
  const router = useRouter()
  const pathname = usePathname()
  const isAuthPage = pathname === '/login' || pathname === '/cadastro'

  useEffect(() => {
    let active = true
    let refreshSequence = 0

    async function refreshUser() {
      const requestId = ++refreshSequence
      const currentUser = await getUser()
      if (!active || requestId !== refreshSequence) return

      setUser(currentUser)
      setResolved(true)
      if (!currentUser) {
        setAvatar('')
        setOpen(false)
        return
      }

      setAvatar(currentUser.avatar_url ?? '')
      const migratedAvatar = await migrateLegacyProfileAvatar(currentUser)
      if (!active || requestId !== refreshSequence) return
      setAvatar(migratedAvatar)
    }

    function handleRefresh() {
      void refreshUser()
    }

    function handleVisibilityChange() {
      if (document.visibilityState === 'visible') handleRefresh()
    }

    setOpen(false)
    void refreshUser()
    window.addEventListener(AUTH_STATE_CHANGED_EVENT, handleRefresh)
    window.addEventListener('focus', handleRefresh)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      active = false
      window.removeEventListener(AUTH_STATE_CHANGED_EVENT, handleRefresh)
      window.removeEventListener('focus', handleRefresh)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [pathname])

  useEffect(() => {
    if (!user) return
    const userId = user.id

    function handleAvatarChanged(event: Event) {
      const detail = (event as CustomEvent<{ userId: number; avatar: string }>).detail
      if (detail?.userId === userId) {
        setAvatar(detail.avatar)
      }
    }

    window.addEventListener(PROFILE_AVATAR_CHANGED_EVENT, handleAvatarChanged)
    return () => {
      window.removeEventListener(PROFILE_AVATAR_CHANGED_EVENT, handleAvatarChanged)
    }
  }, [user])

  async function handleLogout() {
    await logout()
    setUser(null)
    setAvatar('')
    setOpen(false)
    router.replace('/verificador')
    router.refresh()
  }

  if (!resolved) return null

  if (!user) {
    if (isAuthPage) return null

    return (
      <Link
        href="/login"
        className="text-xs text-texto-secundario hover:text-dourado transition-colors px-3 py-1 border border-fundo-borda rounded-full"
      >
        Entrar
      </Link>
    )
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-xs text-texto-secundario hover:text-dourado transition-colors"
      >
        <span className="w-7 h-7 overflow-hidden rounded-full bg-dourado/20 flex items-center justify-center text-dourado font-semibold uppercase">
          {avatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={avatar} alt="" className="h-full w-full object-cover" />
          ) : (
            user.name.charAt(0)
          )}
        </span>
        <span className="hidden sm:inline">{user.name.split(' ')[0]}</span>
      </button>

      {open && (
        <div className="absolute right-0 top-9 z-50 w-48 rounded-lg border border-fundo-borda bg-fundo-card shadow-lg py-1">
          <div className="px-3 py-2 border-b border-fundo-borda">
            <p className="text-xs font-medium text-texto truncate">{user.name}</p>
            <p className="text-xs text-texto-terciario truncate">{user.email}</p>
            <p className="text-xs text-dourado mt-0.5">Plano {PLAN_LABELS[user.plan] ?? user.plan}</p>
          </div>
          <Link
            href="/perfil"
            onClick={() => setOpen(false)}
            className="block px-3 py-2 text-xs text-texto-secundario hover:text-dourado hover:bg-fundo transition-colors"
          >
            Meu Perfil
          </Link>
          <Link
            href="/perfil#historico"
            onClick={() => setOpen(false)}
            className="block px-3 py-2 text-xs text-texto-secundario hover:text-dourado hover:bg-fundo transition-colors"
          >
            Meu Histórico
          </Link>
          {user.is_owner && (
            <Link
              href="/admin"
              onClick={() => setOpen(false)}
              className="block px-3 py-2 text-xs font-semibold text-dourado hover:bg-fundo transition-colors"
            >
              Administração
            </Link>
          )}
          <button
            onClick={handleLogout}
            className="w-full text-left px-3 py-2 text-xs text-texto-terciario hover:text-vermelho hover:bg-fundo transition-colors"
          >
            Sair
          </button>
        </div>
      )}
    </div>
  )
}
