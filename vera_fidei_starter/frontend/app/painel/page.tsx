'use client'

import { useEffect, useState } from 'react'
import { getUser, getInstituicao, criarInstituicao, convidarMembro, getRelatorio } from '@/lib/auth'
import { useRouter } from 'next/navigation'

interface Membro {
  id: number
  user_id: number
  name: string | null
  email: string | null
  role: string
  joined_at: string | null
}

interface Instituicao {
  id: number
  name: string
  admin_user_id: number
  created_at: string | null
}

interface Relatorio {
  institution_id: number
  institution_name: string
  period: string
  total_verificacoes: number
  distribuicao_vereditos: Record<string, number>
}

const PLAN_ORDER = ['fiel', 'catequista', 'apologeta', 'patristico', 'magisterio']

export default function PainelPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(true)
  const [accessDenied, setAccessDenied] = useState(false)

  const [inst, setInst] = useState<Instituicao | null>(null)
  const [membros, setMembros] = useState<Membro[]>([])
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null)
  const [dataLoading, setDataLoading] = useState(false)

  // Criar instituição
  const [nomeInst, setNomeInst] = useState('')
  const [criando, setCriando] = useState(false)
  const [createError, setCreateError] = useState('')

  // Convidar membro
  const [emailConvite, setEmailConvite] = useState('')
  const [convidando, setConvidando] = useState(false)
  const [conviteMsg, setConviteMsg] = useState('')
  const [conviteError, setConviteError] = useState('')

  useEffect(() => {
    getUser().then((u) => {
      if (!u) {
        router.replace('/login?redirect=/painel')
        return
      }
      if (PLAN_ORDER.indexOf(u.plan) < PLAN_ORDER.indexOf('patristico')) {
        setAccessDenied(true)
        setLoading(false)
        return
      }
      setLoading(false)
      loadInstitution()
    })
  }, [router])

  async function loadInstitution() {
    setDataLoading(true)
    try {
      const [instData, membrosData, relData] = await Promise.allSettled([
        getInstituicao(),
        fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'}/instituicao/membros`, {
          headers: {
            Authorization: `Bearer ${document.cookie.match(/vf_token=([^;]*)/)?.[1] ?? ''}`,
            'X-API-Key': process.env.NEXT_PUBLIC_API_KEY ?? '',
          },
        }).then((r) => (r.ok ? r.json() : Promise.reject())),
        getRelatorio(),
      ])

      if (instData.status === 'fulfilled') setInst(instData.value)
      if (membrosData.status === 'fulfilled') setMembros(membrosData.value.members ?? [])
      if (relData.status === 'fulfilled') setRelatorio(relData.value)
    } catch {
      // Sem instituição ainda
    } finally {
      setDataLoading(false)
    }
  }

  async function handleCriarInstituicao() {
    if (!nomeInst.trim()) return
    setCriando(true)
    setCreateError('')
    try {
      const data = await criarInstituicao(nomeInst.trim())
      setInst(data)
      setNomeInst('')
      await loadInstitution()
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : 'Erro ao criar instituição.')
    } finally {
      setCriando(false)
    }
  }

  async function handleConvidar() {
    if (!emailConvite.trim()) return
    setConvidando(true)
    setConviteMsg('')
    setConviteError('')
    try {
      await convidarMembro(emailConvite.trim())
      setConviteMsg(`Usuário "${emailConvite.trim()}" adicionado com sucesso.`)
      setEmailConvite('')
      await loadInstitution()
    } catch (e: unknown) {
      setConviteError(e instanceof Error ? e.message : 'Erro ao convidar membro.')
    } finally {
      setConvidando(false)
    }
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10">
        <p className="text-sm text-texto-terciario text-center">Carregando…</p>
      </div>
    )
  }

  if (accessDenied) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-10 text-center">
        <h1 className="font-eb-garamond text-2xl text-dourado mb-3">Acesso restrito</h1>
        <p className="text-sm text-texto-terciario mb-4">
          O Painel Institucional requer o plano <strong className="text-texto">Patrístico</strong> ou superior.
        </p>
        <a href="/planos" className="text-sm text-dourado hover:underline">Ver planos disponíveis →</a>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 flex flex-col gap-8">
      <div>
        <h1 className="font-eb-garamond text-2xl text-dourado mb-1">Painel Institucional</h1>
        <p className="text-xs text-texto-terciario">Gerencie sua instituição e membros.</p>
      </div>

      {!inst && !dataLoading && (
        <div className="bg-fundo-card border border-fundo-borda rounded-xl p-5">
          <h2 className="font-eb-garamond text-lg text-texto mb-3">Criar Instituição</h2>
          <p className="text-xs text-texto-terciario mb-4">
            Você ainda não possui uma instituição. Crie uma para gerenciar membros e relatórios.
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Nome da instituição"
              value={nomeInst}
              onChange={(e) => setNomeInst(e.target.value)}
              className="flex-1 text-sm bg-fundo border border-fundo-borda rounded-lg px-3 py-2 text-texto placeholder:text-texto-terciario focus:outline-none focus:border-dourado"
            />
            <button
              onClick={handleCriarInstituicao}
              disabled={criando || !nomeInst.trim()}
              className="text-sm px-4 py-2 rounded-lg bg-dourado text-fundo font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
            >
              {criando ? 'Criando…' : 'Criar'}
            </button>
          </div>
          {createError && <p className="text-xs text-vermelho mt-2">{createError}</p>}
        </div>
      )}

      {dataLoading && (
        <p className="text-sm text-texto-terciario text-center">Carregando dados institucionais…</p>
      )}

      {inst && (
        <>
          <div className="bg-fundo-card border border-fundo-borda rounded-xl p-5">
            <h2 className="font-eb-garamond text-lg text-texto mb-1">{inst.name}</h2>
            <p className="text-xs text-texto-terciario">
              Criada em: {inst.created_at ? new Date(inst.created_at).toLocaleDateString('pt-BR') : '—'}
            </p>
          </div>

          <div className="bg-fundo-card border border-fundo-borda rounded-xl p-5">
            <h2 className="font-eb-garamond text-lg text-texto mb-4">Membros ({membros.length})</h2>

            {membros.length === 0 ? (
              <p className="text-xs text-texto-terciario">Nenhum membro ainda.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-texto-terciario border-b border-fundo-borda">
                      <th className="text-left pb-2 font-normal">Nome</th>
                      <th className="text-left pb-2 font-normal">E-mail</th>
                      <th className="text-left pb-2 font-normal">Papel</th>
                      <th className="text-left pb-2 font-normal">Entrou em</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-fundo-borda">
                    {membros.map((m) => (
                      <tr key={m.id}>
                        <td className="py-2 text-texto pr-3">{m.name ?? '—'}</td>
                        <td className="py-2 text-texto-secundario pr-3">{m.email ?? '—'}</td>
                        <td className="py-2 text-texto-terciario pr-3 capitalize">{m.role}</td>
                        <td className="py-2 text-texto-terciario">
                          {m.joined_at ? new Date(m.joined_at).toLocaleDateString('pt-BR') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="mt-4 pt-4 border-t border-fundo-borda">
              <p className="text-xs text-texto-terciario mb-2">Convidar membro por e-mail:</p>
              <div className="flex gap-2">
                <input
                  type="email"
                  placeholder="email@exemplo.com"
                  value={emailConvite}
                  onChange={(e) => setEmailConvite(e.target.value)}
                  className="flex-1 text-sm bg-fundo border border-fundo-borda rounded-lg px-3 py-2 text-texto placeholder:text-texto-terciario focus:outline-none focus:border-dourado"
                />
                <button
                  onClick={handleConvidar}
                  disabled={convidando || !emailConvite.trim()}
                  className="text-sm px-4 py-2 rounded-lg border border-dourado text-dourado disabled:opacity-50 hover:bg-dourado hover:text-fundo transition-colors"
                >
                  {convidando ? 'Convidando…' : 'Convidar'}
                </button>
              </div>
              {conviteMsg && <p className="text-xs text-green-400 mt-2">{conviteMsg}</p>}
              {conviteError && <p className="text-xs text-vermelho mt-2">{conviteError}</p>}
            </div>
          </div>

          {relatorio && (
            <div className="bg-fundo-card border border-fundo-borda rounded-xl p-5">
              <h2 className="font-eb-garamond text-lg text-texto mb-1">Relatório — {relatorio.period}</h2>
              <p className="text-xs text-texto-terciario mb-4">
                Total de verificações no mês: <strong className="text-texto">{relatorio.total_verificacoes}</strong>
              </p>

              {Object.keys(relatorio.distribuicao_vereditos).length > 0 ? (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-texto-terciario border-b border-fundo-borda">
                      <th className="text-left pb-2 font-normal">Classificação</th>
                      <th className="text-right pb-2 font-normal">Quantidade</th>
                      <th className="text-right pb-2 font-normal">%</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-fundo-borda">
                    {Object.entries(relatorio.distribuicao_vereditos).map(([label, count]) => {
                      const pct = relatorio.total_verificacoes > 0
                        ? ((count / relatorio.total_verificacoes) * 100).toFixed(1)
                        : '0.0'
                      return (
                        <tr key={label}>
                          <td className="py-2 text-texto">{label}</td>
                          <td className="py-2 text-texto-secundario text-right">{count}</td>
                          <td className="py-2 text-texto-terciario text-right">{pct}%</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              ) : (
                <p className="text-xs text-texto-terciario">Nenhuma verificação este mês.</p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
