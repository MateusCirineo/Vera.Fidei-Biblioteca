'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  createApiKey,
  getApiKeys,
  getUser,
  logout,
  openBillingPortal,
  revokeApiKey,
  type UserInfo,
} from '@/lib/auth'
import ProfileFavorites from '@/components/perfil/ProfileFavorites'
import ProfileHistory from '@/components/perfil/ProfileHistory'

interface ApiKeyEntry {
  id: number
  label: string | null
  is_active: boolean
  usage_count: number
  created_at: string | null
  last_used_at: string | null
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

const AVATAR_MAX_SIZE = 700 * 1024

function storageKey(kind: 'avatar', userId: number) {
  return `vf_profile_${kind}_${userId}`
}

function planRank(plan: string | undefined) {
  const index = PLAN_ORDER.indexOf(plan ?? 'fiel')
  return index >= 0 ? index : 0
}

function isOwner(user: UserInfo | null) {
  return user?.billing_status === 'owner' || user?.email.toLowerCase() === 'mateuscirineo@gmail.com'
}

function billingStatusText(user: UserInfo) {
  if (isOwner(user)) return 'Acesso total permanente.'
  if (!user.billing_status) return 'Sem assinatura paga ativa.'
  if (user.billing_status === 'pending_payment') return 'Pagamento Pix aguardando confirmacao.'
  if (user.billing_cancel_at_period_end && user.billing_current_period_end) {
    return `Cancelamento agendado para ${new Date(user.billing_current_period_end).toLocaleDateString('pt-BR')}.`
  }
  if (user.billing_status === 'active') return 'Assinatura mensal ativa.'
  if (user.billing_status === 'trialing') return 'Assinatura em periodo de teste.'
  if (user.billing_status === 'past_due') return 'Pagamento pendente. Atualize a forma de pagamento.'
  if (user.billing_status === 'canceled') return 'Assinatura cancelada.'
  return `Status da assinatura: ${user.billing_status}.`
}

export default function PerfilPage() {
  const router = useRouter()
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [avatar, setAvatar] = useState('')
  const [favoriteTotal, setFavoriteTotal] = useState(0)
  const [profileNotice, setProfileNotice] = useState('')
  const [billingNotice, setBillingNotice] = useState('')
  const [billingLoading, setBillingLoading] = useState(false)
  const [loadError, setLoadError] = useState('')

  const [keys, setKeys] = useState<ApiKeyEntry[]>([])
  const [keysLoading, setKeysLoading] = useState(false)
  const [newKeyLabel, setNewKeyLabel] = useState('')
  const [generatingKey, setGeneratingKey] = useState(false)
  const [showApiTools, setShowApiTools] = useState(false)
  const [modalKey, setModalKey] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    let settled = false
    const timeoutId = window.setTimeout(() => {
      if (!active || settled) return
      setLoadError('Nao foi possivel carregar sua sessao. Verifique a conexao e tente novamente.')
      setLoading(false)
    }, 9000)

    getUser().then((u) => {
      if (!active) return
      settled = true
      window.clearTimeout(timeoutId)
      if (!u) {
        router.replace('/login?redirect=/perfil')
        return
      }

      setLoadError('')
      setUser(u)
      setLoading(false)
      setAvatar(localStorage.getItem(storageKey('avatar', u.id)) ?? '')
    }).catch(() => {
      if (!active) return
      settled = true
      window.clearTimeout(timeoutId)
      setLoadError('Nao foi possivel carregar sua sessao. Entre novamente ou tente recarregar.')
      setLoading(false)
    })
    return () => {
      active = false
      window.clearTimeout(timeoutId)
    }
  }, [router])

  const activeKeys = useMemo(() => keys.filter((key) => key.is_active).length, [keys])
  const currentPlanRank = planRank(user?.plan)
  const nextPlan = user ? PLAN_ORDER[currentPlanRank + 1] : null
  const canManageBilling = user?.billing_provider !== 'manual_pix'
    && Boolean(user?.billing_status)
    && user?.billing_status !== 'owner'
    && user?.billing_status !== 'pending_payment'

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
      window.dispatchEvent(new CustomEvent('vf:profile-avatar-changed', {
        detail: { userId: user.id, avatar: value },
      }))
    }
    reader.readAsDataURL(file)
  }

  function removeAvatar() {
    if (!user) return
    setAvatar('')
    localStorage.removeItem(storageKey('avatar', user.id))
    window.dispatchEvent(new CustomEvent('vf:profile-avatar-changed', {
      detail: { userId: user.id, avatar: '' },
    }))
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

  async function handleOpenApiTools() {
    setShowApiTools(true)
    await loadKeys()
  }

  async function handleManageBilling() {
    if (!user) return
    if (isOwner(user)) {
      setBillingNotice('Esta conta ja tem acesso total permanente.')
      return
    }
    setBillingNotice('')
    setBillingLoading(true)
    try {
      const { url } = await openBillingPortal()
      window.location.assign(url)
    } catch (err: unknown) {
      setBillingNotice(err instanceof Error ? err.message : 'Erro ao abrir assinatura.')
      setBillingLoading(false)
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

  if (!user && loadError) {
    return (
      <div className="mx-auto max-w-xl px-4 py-10">
        <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
          <p className="font-eb-garamond text-2xl text-dourado">Perfil indisponivel</p>
          <p className="mt-2 text-sm leading-relaxed text-texto-terciario">{loadError}</p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-md bg-dourado px-4 py-2 text-sm font-medium text-fundo transition-colors hover:bg-dourado-claro"
            >
              Tentar novamente
            </button>
            <Link
              href="/login?redirect=/perfil"
              className="rounded-md border border-fundo-borda px-4 py-2 text-sm text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
            >
              Entrar novamente
            </Link>
          </div>
        </div>
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
                  <p className="mt-1 text-sm text-texto">{favoriteTotal}</p>
                </div>
                <div>
                  <p className="text-xs text-texto-terciario">Integrações</p>
                  <p className="mt-1 text-sm text-texto">{user.plan === 'magisterio' ? 'Área técnica' : 'Bloqueado'}</p>
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
          <p className="mt-2 text-xs leading-relaxed text-dourado">
            {billingStatusText(user)}
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
            {canManageBilling && (
              <button
                type="button"
                onClick={handleManageBilling}
                disabled={billingLoading}
                className="rounded-md border border-dourado/40 px-3 py-2 text-xs text-dourado transition-colors hover:bg-dourado hover:text-fundo disabled:opacity-50"
              >
                {billingLoading ? 'Abrindo...' : 'Gerenciar/cancelar'}
              </button>
            )}
            {nextPlan && (
              <Link
                href="/planos"
                className="rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
              >
                Próximo: {PLAN_LABELS[nextPlan]}
              </Link>
            )}
          </div>
          {billingNotice && <p className="mt-3 text-xs text-vermelho">{billingNotice}</p>}
        </aside>
      </section>

      <ProfileFavorites onTotalChange={setFavoriteTotal} />

      {user.plan === 'magisterio' && (
        <section className="mt-6 rounded-lg border border-fundo-borda bg-fundo-card p-5 sm:p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
                Integrações
              </p>
              <h2 className="mt-1 font-eb-garamond text-xl text-texto">Chaves de API</h2>
              <p className="mt-2 max-w-2xl text-xs leading-relaxed text-texto-terciario">
                Área restrita para integrações técnicas. Não é necessária para usar o app normalmente.
              </p>
            </div>
            {showApiTools && (
              <span className="text-xs text-dourado">{activeKeys} ativa{activeKeys === 1 ? '' : 's'}</span>
            )}
          </div>

          {!showApiTools ? (
            <button
              type="button"
              onClick={handleOpenApiTools}
              className="mt-4 rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
            >
              Abrir área técnica
            </button>
          ) : (
            <>
              <div className="mt-4 rounded-md border border-dourado/25 bg-dourado/10 px-3 py-2 text-xs leading-relaxed text-texto-secundario">
                As chaves existentes não exibem o valor secreto. Uma chave nova aparece apenas uma vez, no momento em que for gerada.
              </div>

              <div className="mt-4 rounded-md border border-fundo-borda bg-fundo p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-texto-terciario">
                  Endpoint REST
                </p>
                <pre className="mt-2 overflow-x-auto rounded-md bg-black/30 p-3 text-[11px] leading-relaxed text-texto-secundario">
{`curl -X POST https://verafidei.oialfred.com/api/v1/verificar \\
  -H "X-VF-Api-Key: SUA_CHAVE" \\
  -H "Content-Type: application/json" \\
  -d '{"citacao":"...", "autor":"Santo Agostinho"}'`}
                </pre>
                <div className="mt-3 flex flex-wrap gap-2">
                  <a
                    href="mailto:vera.fidei661@gmail.com?subject=Vera.Fidei%20-%20suporte%20Magisterio"
                    className="rounded-md border border-dourado/40 px-3 py-2 text-xs text-dourado transition-colors hover:bg-dourado hover:text-fundo"
                  >
                    Suporte prioritÃ¡rio
                  </a>
                  <Link
                    href="/contato"
                    className="rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
                  >
                    Ver contato
                  </Link>
                </div>
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
            </>
          )}
        </section>
      )}

      <ProfileHistory userPlan={user.plan} />

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
