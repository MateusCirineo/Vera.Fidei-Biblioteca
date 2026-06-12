'use client'

import { useEffect, useState } from 'react'
import { getUser, UserInfo } from '@/lib/auth'
import Link from 'next/link'

interface Plano {
  key: string
  nome: string
  preco: string
  periodicidade: string
  limite: string
  destaque: boolean
  features: string[]
}

const PLANOS: Plano[] = [
  {
    key: 'fiel',
    nome: 'Fiel',
    preco: 'Grátis',
    periodicidade: '',
    limite: '10 verificações por mês',
    destaque: false,
    features: [
      'Verificação de citações patrísticas',
      'Veredito com nível de confiança',
      'Histórico das últimas verificações',
      'Acesso completo à biblioteca',
    ],
  },
  {
    key: 'catequista',
    nome: 'Catequista',
    preco: 'R$ 9,90',
    periodicidade: '/mês',
    limite: '25 verificações por mês',
    destaque: false,
    features: [
      'Tudo do plano Fiel',
      'Exportação de laudos em PDF',
      'Laudo com referência exata de fonte',
    ],
  },
  {
    key: 'apologeta',
    nome: 'Apologeta',
    preco: 'R$ 29,99',
    periodicidade: '/mês',
    limite: '50 verificações por mês',
    destaque: true,
    features: [
      'Tudo do plano Catequista',
      'Relatório de contexto patrístico completo',
      'Relatório de fidelidade de tradução e edição',
      'Acesso a PDFs digitalizados na biblioteca',
      'Exportação do histórico em CSV',
    ],
  },
  {
    key: 'patristico',
    nome: 'Patrístico',
    preco: 'R$ 59,99',
    periodicidade: '/mês',
    limite: '100 verificações por mês',
    destaque: false,
    features: [
      'Tudo do plano Apologeta',
      'Painel de gestão institucional',
      'Convite e gestão de membros',
      'Relatório mensal de uso',
    ],
  },
  {
    key: 'magisterio',
    nome: 'Magistério',
    preco: 'R$ 99,99',
    periodicidade: '/mês',
    limite: 'Ilimitado',
    destaque: false,
    features: [
      'Tudo do plano Patrístico',
      'Acesso via API Key dedicada',
      'Endpoint REST público /v1/verificar',
      'Geração e revogação de chaves',
      'Integração com sistemas externos',
    ],
  },
]

export default function PlanosPage() {
  const [user, setUser] = useState<UserInfo | null>(null)

  useEffect(() => {
    getUser().then(setUser).catch(() => setUser(null))
  }, [])

  return (
    <div className="max-w-5xl mx-auto px-4 py-12">
      <div className="text-center mb-12">
        <h1 className="font-eb-garamond text-4xl text-dourado mb-3">Planos Vera.Fidei</h1>
        <p className="text-sm text-texto-terciario max-w-md mx-auto leading-relaxed">
          Para estudiosos, catequistas, apologetas e instituições que levam a sério
          a veracidade das fontes católicas.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {PLANOS.map((plano) => {
          const isAtual = user?.plan === plano.key
          const isDestaque = plano.destaque && !isAtual

          return (
            <div
              key={plano.key}
              className={`relative flex flex-col rounded-2xl p-6 border transition-all ${
                isAtual
                  ? 'bg-fundo-card border-dourado shadow-[0_0_24px_rgba(201,168,76,0.15)]'
                  : isDestaque
                  ? 'bg-fundo-card border-dourado/40'
                  : 'bg-fundo-card border-fundo-borda'
              }`}
            >
              {/* Badge */}
              {isAtual && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-dourado text-fundo text-xs font-semibold px-3 py-1 rounded-full whitespace-nowrap">
                    Seu plano atual
                  </span>
                </div>
              )}
              {isDestaque && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-fundo-borda text-texto-secundario text-xs font-medium px-3 py-1 rounded-full whitespace-nowrap">
                    Mais popular
                  </span>
                </div>
              )}

              {/* Header */}
              <div className="mb-5">
                <p className="text-xs text-texto-terciario uppercase tracking-widest mb-1 font-medium">
                  {plano.nome}
                </p>
                <div className="flex items-end gap-1">
                  <span className={`font-eb-garamond text-3xl font-semibold ${isAtual ? 'text-dourado' : 'text-texto'}`}>
                    {plano.preco}
                  </span>
                  {plano.periodicidade && (
                    <span className="text-texto-terciario text-sm mb-0.5">{plano.periodicidade}</span>
                  )}
                </div>
                <p className="text-xs text-texto-terciario mt-2 border-t border-fundo-borda pt-2">
                  {plano.limite}
                </p>
              </div>

              {/* Features */}
              <ul className="flex flex-col gap-2.5 flex-1">
                {plano.features.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-xs text-texto-secundario">
                    <svg viewBox="0 0 16 16" fill="none" className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-dourado">
                      <path d="M3 8l3.5 3.5L13 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    {f}
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <div className="mt-6">
                {isAtual ? (
                  <div className="w-full text-center text-xs text-dourado font-medium py-2.5 rounded-lg border border-dourado/30 bg-dourado/5">
                    Plano ativo
                  </div>
                ) : (
                  <Link
                    href="/login"
                    className="block w-full text-center text-xs font-medium py-2.5 rounded-lg border border-fundo-borda text-texto-secundario hover:border-dourado hover:text-dourado transition-colors"
                  >
                    {user ? 'Fazer upgrade' : 'Começar agora'}
                  </Link>
                )}
              </div>
            </div>
          )
        })}
      </div>

      <p className="text-center text-xs text-texto-terciario mt-10 leading-relaxed">
        Todos os planos incluem acesso à biblioteca patrística e verificador de citações. <br />
        Pagamento seguro · Cancele a qualquer momento ·{' '}
        <Link href="/apresentacao" className="text-dourado hover:underline">
          Saiba mais sobre o Vera.Fidei
        </Link>
      </p>
    </div>
  )
}
