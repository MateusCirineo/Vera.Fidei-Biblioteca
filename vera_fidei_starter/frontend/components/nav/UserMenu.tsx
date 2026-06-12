'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { getUser, logout, type UserInfo } from '@/lib/auth'

export default function UserMenu() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [open, setOpen] = useState(false)
  const router = useRouter()

  useEffect(() => {
    getUser().then(setUser)
  }, [])

  function handleLogout() {
    logout()
    setUser(null)
    setOpen(false)
    router.push('/verificador')
  }

  if (!user) {
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
        <span className="w-7 h-7 rounded-full bg-dourado/20 flex items-center justify-center text-dourado font-semibold uppercase">
          {user.name.charAt(0)}
        </span>
        <span className="hidden sm:inline">{user.name.split(' ')[0]}</span>
      </button>

      {open && (
        <div className="absolute right-0 top-9 z-50 w-48 rounded-lg border border-fundo-borda bg-fundo-card shadow-lg py-1">
          <div className="px-3 py-2 border-b border-fundo-borda">
            <p className="text-xs font-medium text-texto truncate">{user.name}</p>
            <p className="text-xs text-texto-terciario truncate">{user.email}</p>
            <p className="text-xs text-dourado capitalize mt-0.5">Plano {user.plan}</p>
          </div>
          <Link
            href="/perfil"
            onClick={() => setOpen(false)}
            className="block px-3 py-2 text-xs text-texto-secundario hover:text-dourado hover:bg-fundo transition-colors"
          >
            Meu Perfil
          </Link>
          <Link
            href="/historico"
            onClick={() => setOpen(false)}
            className="block px-3 py-2 text-xs text-texto-secundario hover:text-dourado hover:bg-fundo transition-colors"
          >
            Meu Histórico
          </Link>
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
