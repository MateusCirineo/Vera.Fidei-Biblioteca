'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  createApiKey,
  getApiKeys,
  getUser,
  logout,
  revokeApiKey,
  type UserInfo,
} from '@/lib/auth'

interface ApiKeyEntry {
  id: number
  label: string | null
  is_active: boolean
  usage_count: number
  created_at: string | null
  last_used_at: string | null
}

interface FavoriteArea {
  id: string
  label: string
  description: string
  href: string
}

const PLAN_ORDER = ['fiel', 'catequista', 'apologeta', 'patristico', 'magisterio']

const PLAN_LABELS: Record<string, string> = {
  fiel: 'Fiel',
  catequista: 'Catequista',
  apologeta: 'Apologeta',
  patristico: 'Patrístico',
  magisterio: 'Magistério',
}

const PLAN_DESCRIPTIONS: Record<string, string> = {
  fiel: 'Consulta pessoal, biblioteca e verificações essenciais.',
  catequista: 'Laudos em PDF e referências para uso em aulas e grupos.',
  apologeta: 'Contexto patrístico, análise de tradução e uso de pesquisa.',
  patristico: 'Gestão institucional, membros e relatório mensal de uso.',
  magisterio: 'Integração via API, chaves dedicadas e acesso ilimitado.',
}

const FAVORITE_AREAS: FavoriteArea[] = [
  {
    id: 'verificador',
    label: 'Verificador',
    description: 'Citações, fontes e laudos',
    href: '/verificador',
  },
  {
    id: 'biblioteca',
    label: 'Biblioteca',
    description: 'Obras, autores e documentos',
    href: '/biblioteca',
  },
  {
    id: 'santos',
    label: 'Santos',
    description: 'Vidas, memória e obras',
    href: '/santos',
  },
  {
    id: 'oracoes',
    label: 'Orações',
    description: 'Orações e devoções',
    href: '/oracoes',
  },
  {
    id: 'historico',
    label: 'Histórico',
    description: 'Verificações recentes',
    href: '/historico',
  },
  {
    id: 'painel',
    label: 'Painel',
    description: 'Instituição e membros',
    href: '/painel',
  },
]

const API_EXAMPLE_URL = `${(process.env.NEXT_PUBLIC_API_URL ?? 'https://verafidei.oialfred.com/api').replace(/\/$/, '')}/v1/verificar`
const AVATAR_MAX_SIZE = 700 * 1024

function storageKey(kind: 'avatar' | 'favorites', userId: number) {
  return `vf_profile_${kind}_${userId}`
}

function planRank(plan: string | undefined) {
  return PLAN_ORDER.indexOf(plan ?? 'fiel')
}

export default function PerfilPage() {
  const router = useRouter()
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [avatar, setAvatar] = useState('')
  const [favorites, setFavorites] = useState<string[]>([])
  const [profileNotice, setProfileNotice] = useState('')

  const [keys, setKeys] = useState<ApiKeyEntry[]>([])
  const [keysLoading, setKeysLoading] = useState(false)
  const [newKeyLabel, setNewKeyLabel] = useState('')
  const [generatingKey, setGeneratingKey] = useState(false)
  const [modalKey, setModalKey] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getUser().then((u) => {
      if (!u) {
        router.replace('/login?redirect=/perfil')
        return
      }

      setUser(u)
      setLoading(false)
      setAvatar(localStorage.getItem(storageKey('avatar', u.id)) ?? '')

      try {
        const storedFavorites = localStorage.getItem(storageKey('favorites', u.id))
        setFavorites(storedFavorites ? JSON.parse(storedFavorites) : ['verificador', 'biblioteca'])
      } catch {
        setFavorites(['verificador', 'biblioteca'])
      }

      if (u.plan === 'magisterio') {
        loadKeys()
      }
    })
  }, [router])

  const activeKeys = useMemo(() => keys.filter((key) => key.is_active).length, [keys])
  const currentPlanRank = planRank(user?.plan)
  const nextPlan = user ? PLAN_ORDER[currentPlanRank + 1] : null
  const selectedFavorites = FAVORITE_AREAS.filter((area) => favorites.includes(area.id))

  async function loadKeys() {
    setKeysLoading(true)
    try {
      const data = await getApiKeys()
      setKeys(data.items ?? [])
    } catch {
      setKeys([])
    } finally {
      setKeysLoading(false)
    }
  }

  function handleAvatarChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file || !user) return

    setProfileNotice('')
    if (!file.type.startsWith('image/')) {
      setProfileNotice('Escolha um arquivo de imagem.')
      return
    }
    if (file.size > AVATAR_MAX_SIZE) {
      setProfileNotice('Use uma imagem com até 700 KB.')
      return
    }

    const reader = new FileReader()
    reader.onload = () => {
      const value = typeof reader.result === 'string' ? reader.result : ''
      setAvatar(value)
      localStorage.setItem(storageKey('avatar', user.id), value)
    }
    reader.readAsDataURL(file)
  }

  function removeAvatar() {
    if (!user) return
    setAvatar('')
    localStorage.removeItem(storageKey('avatar', user.id))
  }

  function toggleFavorite(id: string) {
    if (!user) return
    const next = favorites.includes(id)
      ? favorites.filter((favorite) => favorite !== id)
      : [...favorites, id]
    setFavorites(next)
    localStorage.setItem(storageKey('favorites', user.id), JSON.stringify(next))
  }

  async function handleGenerateKey() {
    setGeneratingKey(true)
    setError('')
    try {
      const data = await createApiKey(newKeyLabel)
      setModalKey(data.key)
      setNewKeyLabel('')
      await loadKeys()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao gerar chave.')
    } finally {
      setGeneratingKey(false)
    }
  }

  async function handleRevoke(id: number) {
    if (!confirm('Revogar esta chave? Esta ação não pode ser desfeita.')) return
    try {
      await revokeApiKey(id)
      setKeys((prev) => prev.map((key) => key.id === id ? { ...key, is_active: false } : key))
    } catch {
      alert('Erro ao revogar chave.')
    }
  }

  function handleLogout() {
    logout()
    router.push('/')
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10">
        <p className="text-sm text-texto-terciario text-center">Carregando...</p>
      </div>
    )
  }

  if (!user) return null

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 sm:py-10">
      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(300px,0.75fr)]">
        <div className="rounded-lg border border-fundo-borda bg-fundo-card p-5 sm:p-6">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <div className="flex flex-col items-start gap-3">
              <div className="h-24 w-24 overflow-hidden rounded-full border border-dourado/35 bg-dourado/10">
                {avatar ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={avatar} alt="" className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center font-eb-garamond text-4xl text-dourado">
                    {user.name.charAt(0).toUpperCase()}
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <label
                  htmlFor="profile-photo"
                  className="cursor-pointer rounded-md bg-dourado px-3 py-2 text-xs font-medium text-fundo transition-colors hover:bg-dourado-claro"
                >
                  Trocar foto
                </label>
                <input
                  id="profile-photo"
                  type="file"
                  accept="image/*"
                  className="sr-only"
                  onChange={handleAvatarChange}
                />
                {avatar && (
                  <button
                    type="button"
                    onClick={removeAvatar}
                    className="rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-terciario transition-colors hover:border-vermelho hover:text-vermelho"
                  >
                    Remover
                  </button>
                )}
              </div>
            </div>

            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium uppercase tracking-[0.22em] text-texto-terciario">
                Perfil
              </p>
              <h1 className="mt-2 font-eb-garamond text-3xl text-dourado">
                {user.name}
              </h1>
              <p className="mt-1 break-all text-sm text-texto-secundario">{user.email}</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div>
                  <p className="text-xs text-texto-terciario">Plano</p>
                  <p className="mt-1 text-sm font-medium text-dourado">
                    {PLAN_LABELS[user.plan] ?? user.plan}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-texto-terciario">Favoritos</p>
                  <p className="mt-1 text-sm text-texto">{favorites.length}</p>
                </div>
                <div>
                  <p className="text-xs text-texto-terciario">API keys</p>
                  <p className="mt-1 text-sm text-texto">{user.plan === 'magisterio' ? activeKeys : 'Bloqueado'}</p>
                </div>
              </div>
              {profileNotice && (
                <p className="mt-3 text-xs text-vermelho">{profileNotice}</p>
              )}
            </div>
          </div>
        </div>

        <aside className="rounded-lg border border-fundo-borda bg-fundo-card p-5 sm:p-6">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
            Assinatura
          </p>
          <h2 className="mt-2 font-eb-garamond text-2xl text-texto">
            {PLAN_LABELS[user.plan] ?? user.plan}
          </h2>
          <p className="mt-2 text-xs leading-relaxed text-texto-terciario">
            {PLAN_DESCRIPTIONS[user.plan] ?? 'Plano ativo da conta.'}
          </p>
          <div className="mt-5 h-1.5 rounded-full bg-fundo">
            <div
              className="h-full rounded-full bg-dourado"
              style={{ width: `${Math.max(20, ((currentPlanRank + 1) / PLAN_ORDER.length) * 100)}%` }}
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href="/planos"
              className="rounded-md bg-dourado px-3 py-2 text-xs font-medium text-fundo transition-colors hover:bg-dourado-claro"
            >
              Ver planos
            </Link>
            {nextPlan && (
              <Link
                href="/planos"
                className="rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
              >
                Próximo: {PLAN_LABELS[nextPlan]}
              </Link>
            )}
          </div>
        </aside>
      </section>

      <section className="mt-6">
        <div className="mb-3 flex items-end justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
              Atalhos
            </p>
            <h2 className="mt-1 font-eb-garamond text-xl text-texto">
              Áreas favoritas
            </h2>
          </div>
          <span className="text-xs text-texto-terciario">
            {selectedFavorites.length} selecionada{selectedFavorites.length === 1 ? '' : 's'}
          </span>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {FAVORITE_AREAS.map((area) => {
            const selected = favorites.includes(area.id)
            return (
              <div
                key={area.id}
                className={`rounded-lg border bg-fundo-card p-4 transition-colors ${
                  selected ? 'border-dourado/55' : 'border-fundo-borda'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-eb-garamond text-lg text-texto">{area.label}</h3>
                    <p className="mt-1 text-xs leading-relaxed text-texto-terciario">
                      {area.description}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => toggleFavorite(area.id)}
                    aria-pressed={selected}
                    title={selected ? 'Remover dos favoritos' : 'Adicionar aos favoritos'}
                    className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md border transition-colors ${
                      selected
                        ? 'border-dourado bg-dourado text-fundo'
                        : 'border-fundo-borda text-texto-terciario hover:border-dourado hover:text-dourado'
                    }`}
                  >
                    <svg viewBox="0 0 24 24" fill={selected ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.6" className="h-4 w-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m12 17.3-5.3 3 1.2-5.9-4.5-4 6-.7L12 4.2l2.6 5.5 6 .7-4.5 4 1.2 5.9-5.3-3Z" />
                    </svg>
                  </button>
                </div>
                <Link
                  href={area.href}
                  className="mt-4 inline-flex rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
                >
                  Abrir
                </Link>
              </div>
            )
          })}
        </div>
      </section>

      {user.plan === 'magisterio' && (
        <section className="mt-6 rounded-lg border border-fundo-borda bg-fundo-card p-5 sm:p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
                Integrações
              </p>
              <h2 className="mt-1 font-eb-garamond text-xl text-texto">Chaves de API</h2>
            </div>
            <span className="text-xs text-dourado">{activeKeys} ativa{activeKeys === 1 ? '' : 's'}</span>
          </div>

          <div className="mt-4 overflow-x-auto rounded-md bg-fundo p-3">
            <code className="whitespace-pre text-xs text-texto-secundario">{`curl -X POST ${API_EXAMPLE_URL} \\
  -H "X-VF-Api-Key: SUA_CHAVE" \\
  -H "Content-Type: application/json" \\
  -d '{"citacao": "...", "autor": "Santo Agostinho"}'`}</code>
          </div>

          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              placeholder="Rótulo da chave (opcional)"
              value={newKeyLabel}
              onChange={(e) => setNewKeyLabel(e.target.value)}
              className="min-w-0 flex-1 rounded-md border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
            />
            <button
              onClick={handleGenerateKey}
              disabled={generatingKey}
              className="rounded-md bg-dourado px-4 py-2 text-sm font-medium text-fundo transition-colors hover:bg-dourado-claro disabled:opacity-50"
            >
              {generatingKey ? 'Gerando...' : 'Gerar chave'}
            </button>
          </div>
          {error && <p className="mt-2 text-xs text-vermelho">{error}</p>}

          <div className="mt-5 border-t border-fundo-borda pt-4">
            {keysLoading ? (
              <p className="text-xs text-texto-terciario">Carregando chaves...</p>
            ) : keys.length === 0 ? (
              <p className="text-xs text-texto-terciario">Nenhuma chave gerada ainda.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-fundo-borda text-texto-terciario">
                      <th className="pb-2 pr-4 text-left font-normal">Rótulo</th>
                      <th className="pb-2 pr-4 text-left font-normal">Criada</th>
                      <th className="pb-2 pr-4 text-left font-normal">Último uso</th>
                      <th className="pb-2 pr-4 text-right font-normal">Uso</th>
                      <th className="pb-2 text-right font-normal">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-fundo-borda">
                    {keys.map((key) => (
                      <tr key={key.id}>
                        <td className="py-3 pr-4 text-texto">
                          {key.label || <span className="text-texto-terciario italic">Sem rótulo</span>}
                        </td>
                        <td className="py-3 pr-4 text-texto-terciario">
                          {key.created_at ? new Date(key.created_at).toLocaleDateString('pt-BR') : '-'}
                        </td>
                        <td className="py-3 pr-4 text-texto-terciario">
                          {key.last_used_at ? new Date(key.last_used_at).toLocaleDateString('pt-BR') : 'Nunca'}
                        </td>
                        <td className="py-3 pr-4 text-right text-texto-secundario">{key.usage_count}</td>
                        <td className="py-3 text-right">
                          {key.is_active ? (
                            <button
                              onClick={() => handleRevoke(key.id)}
                              className="text-dourado transition-colors hover:text-vermelho"
                            >
                              Revogar
                            </button>
                          ) : (
                            <span className="text-texto-terciario">Revogada</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      )}

      <div className="mt-6 flex justify-end">
        <button
          onClick={handleLogout}
          className="rounded-md border border-fundo-borda px-4 py-2 text-sm text-texto-secundario transition-colors hover:border-vermelho hover:text-vermelho"
        >
          Sair da conta
        </button>
      </div>

      {modalKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
          <div className="w-full max-w-md rounded-lg border border-dourado bg-fundo-card p-6">
            <h3 className="font-eb-garamond text-xl text-dourado">Chave gerada com sucesso</h3>
            <p className="mt-2 text-xs leading-relaxed text-texto-terciario">
              Salve esta chave agora. Ela não será exibida novamente.
            </p>
            <div className="mt-4 overflow-x-auto rounded-md bg-fundo p-3">
              <code className="break-all text-sm text-texto">{modalKey}</code>
            </div>
            <button
              onClick={() => setModalKey(null)}
              className="mt-4 w-full rounded-md bg-dourado px-4 py-2 text-sm font-medium text-fundo transition-colors hover:bg-dourado-claro"
            >
              Entendi, fechar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
