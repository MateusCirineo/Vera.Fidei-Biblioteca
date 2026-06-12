'use client'

import { useEffect, useState } from 'react'
import { getUser, logout, getApiKeys, createApiKey, revokeApiKey, UserInfo } from '@/lib/auth'
import { useRouter } from 'next/navigation'

interface ApiKeyEntry {
  id: number
  label: string | null
  is_active: boolean
  usage_count: number
  created_at: string | null
  last_used_at: string | null
}

const PLAN_LABELS: Record<string, string> = {
  fiel: 'Fiel',
  catequista: 'Catequista',
  apologeta: 'Apologeta',
  patristico: 'Patrístico',
  magisterio: 'Magistério',
}

export default function PerfilPage() {
  const router = useRouter()
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)

  // API Keys state
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
      if (u.plan === 'magisterio') {
        loadKeys()
      }
    })
  }, [router])

  async function loadKeys() {
    setKeysLoading(true)
    try {
      const data = await getApiKeys()
      setKeys(data.items ?? [])
    } catch {
      // silencioso — usuário pode não ter chaves ainda
    } finally {
      setKeysLoading(false)
    }
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
      setKeys((prev) => prev.map((k) => k.id === id ? { ...k, is_active: false } : k))
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
      <div className="max-w-xl mx-auto px-4 py-10">
        <p className="text-sm text-texto-terciario text-center">Carregando…</p>
      </div>
    )
  }

  if (!user) return null

  return (
    <div className="max-w-xl mx-auto px-4 py-10 flex flex-col gap-8">
      <div>
        <h1 className="font-eb-garamond text-2xl text-dourado mb-4">Meu Perfil</h1>
        <div className="bg-fundo-card border border-fundo-borda rounded-xl p-5 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-texto-terciario">Nome</span>
            <span className="text-sm text-texto">{user.name}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-texto-terciario">E-mail</span>
            <span className="text-sm text-texto">{user.email}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-texto-terciario">Plano</span>
            <span className="text-sm text-dourado font-medium">
              {PLAN_LABELS[user.plan] ?? user.plan}
            </span>
          </div>
        </div>
      </div>

      {user.plan === 'magisterio' && (
        <div>
          <h2 className="font-eb-garamond text-xl text-texto mb-3">Chaves de API</h2>

          <div className="bg-fundo-card border border-fundo-borda rounded-xl p-5 mb-4">
            <p className="text-xs text-texto-terciario mb-3">
              Use sua chave no header <code className="text-dourado">X-VF-Api-Key</code> para acessar o endpoint público.
            </p>
            <div className="bg-fundo rounded-lg p-3 mb-3 overflow-x-auto">
              <code className="text-xs text-texto-secundario whitespace-pre">{`curl -X POST https://api.verafidei.com/v1/verificar \\
  -H "X-VF-Api-Key: SUA_CHAVE" \\
  -H "Content-Type: application/json" \\
  -d '{"citacao": "...", "autor": "Santo Agostinho"}'`}</code>
            </div>

            <div className="flex gap-2 mb-2">
              <input
                type="text"
                placeholder="Rótulo da chave (opcional)"
                value={newKeyLabel}
                onChange={(e) => setNewKeyLabel(e.target.value)}
                className="flex-1 text-sm bg-fundo border border-fundo-borda rounded-lg px-3 py-2 text-texto placeholder:text-texto-terciario focus:outline-none focus:border-dourado"
              />
              <button
                onClick={handleGenerateKey}
                disabled={generatingKey}
                className="text-sm px-4 py-2 rounded-lg bg-dourado text-fundo font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
              >
                {generatingKey ? 'Gerando…' : 'Gerar chave'}
              </button>
            </div>
            {error && <p className="text-xs text-vermelho mt-1">{error}</p>}
          </div>

          {keysLoading ? (
            <p className="text-xs text-texto-terciario">Carregando chaves…</p>
          ) : keys.length === 0 ? (
            <p className="text-xs text-texto-terciario">Nenhuma chave gerada ainda.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {keys.map((k) => (
                <div
                  key={k.id}
                  className="bg-fundo-card border border-fundo-borda rounded-lg p-4 flex items-start justify-between gap-3"
                >
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <span className="text-sm text-texto font-medium truncate">
                      {k.label || <span className="text-texto-terciario italic">Sem rótulo</span>}
                    </span>
                    <span className="text-xs text-texto-terciario">
                      Criada em: {k.created_at ? new Date(k.created_at).toLocaleDateString('pt-BR') : '—'}
                    </span>
                    <span className="text-xs text-texto-terciario">
                      Último uso: {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString('pt-BR') : 'Nunca'}
                    </span>
                    <span className="text-xs text-texto-terciario">
                      Uso total: {k.usage_count}
                    </span>
                    <span className={`text-xs font-medium mt-0.5 ${k.is_active ? 'text-green-400' : 'text-texto-terciario line-through'}`}>
                      {k.is_active ? 'Ativa' : 'Revogada'}
                    </span>
                  </div>
                  {k.is_active && (
                    <button
                      onClick={() => handleRevoke(k.id)}
                      className="text-xs text-texto-terciario hover:text-vermelho transition-colors flex-shrink-0"
                    >
                      Revogar
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div>
        <button
          onClick={handleLogout}
          className="text-sm px-4 py-2 rounded-lg border border-fundo-borda text-texto-secundario hover:text-vermelho hover:border-vermelho transition-colors"
        >
          Sair da conta
        </button>
      </div>

      {modalKey && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4">
          <div className="bg-fundo-card border border-dourado rounded-xl p-6 max-w-md w-full flex flex-col gap-4">
            <h3 className="font-eb-garamond text-lg text-dourado">Chave gerada com sucesso</h3>
            <p className="text-xs text-texto-terciario">
              Salve esta chave agora — ela <strong className="text-texto">não será exibida novamente</strong>.
            </p>
            <div className="bg-fundo rounded-lg p-3 overflow-x-auto">
              <code className="text-sm text-texto break-all select-all">{modalKey}</code>
            </div>
            <button
              onClick={() => setModalKey(null)}
              className="text-sm px-4 py-2 rounded-lg bg-dourado text-fundo font-medium hover:opacity-90 transition-opacity"
            >
              Entendi, fechar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
