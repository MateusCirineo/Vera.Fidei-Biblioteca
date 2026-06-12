'use client'

import { useEffect, useState } from 'react'
import { getUser, UserInfo } from '@/lib/auth'

interface Plano {
  key: string
  nome: string
  preco: string
  limite: string
  features: string[]
}

const PLANOS: Plano[] = [
  {
    key: 'fiel',
    nome: 'Fiel',
    preco: 'Grátis',
    limite: '10 verificações/mês',
    features: [
      'Acesso à verificação de citações',
      'Histórico básico',
    ],
  },
  {
    key: 'catequista',
    nome: 'Catequista',
    preco: 'R$ 9,90/mês',
    limite: '25 verificações/mês',
    features: [
      'Tudo do plano Fiel',
      'Exportação de laudos em PDF',
    ],
  },
  {
    key: 'apologeta',
    nome: 'Apologeta',
    preco: 'R$ 29,99/mês',
    limite: '50 verificações/mês',
    features: [
      'Tudo do plano Catequista',
      'Acesso à biblioteca completa',
    ],
  },
  {
    key: 'patristico',
    nome: 'Patrístico',
    preco: 'R$ 59,99/mês',
    limite: '100 verificações/mês',
    features: [
      'Tudo do plano Apologeta',
      'Painel de gestão institucional',
      'Convite de membros',
      'Relatório mensal da instituição',
    ],
  },
  {
    key: 'magisterio',
    nome: 'Magistério',
    preco: 'R$ 99,99/mês',
    limite: 'Ilimitado',
    features: [
      'Tudo do plano Patrístico',
      'Acesso via API Key (X-VF-Api-Key)',
      'Endpoint público /v1/verificar',
      'Gestão e revogação de chaves',
    ],
  },
]

export default function PlanosPage() {
  const [user, setUser] = useState<UserInfo | null>(null)

  useEffect(() => {
    getUser().then(setUser).catch(() => setUser(null))
  }, [])

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <h1 className="font-eb-garamond text-3xl text-dourado mb-2 text-center">Planos</h1>
      <p className="text-sm text-texto-terciario text-center mb-10">
        Escolha o plano ideal para o seu uso da Vera.Fidei.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {PLANOS.map((plano) => {
          const isAtual = user?.plan === plano.key
          return (
            <div
              key={plano.key}
              className={`bg-fundo-card rounded-xl p-5 flex flex-col gap-3 border-2 transition-colors ${
                isAtual ? 'border-dourado' : 'border-fundo-borda'
              }`}
            >
              <div className="flex items-center justify-between">
                <h2 className="font-eb-garamond text-lg text-texto">{plano.nome}</h2>
                {isAtual && (
                  <span className="text-xs bg-dourado text-fundo px-2 py-0.5 rounded-full font-medium">
                    Seu plano
                  </span>
                )}
              </div>

              <p className="text-dourado font-semibold text-xl">{plano.preco}</p>
              <p className="text-xs text-texto-terciario">{plano.limite}</p>

              <ul className="flex flex-col gap-1.5 mt-1">
                {plano.features.map((f) => (
                  <li key={f} className="text-xs text-texto-secundario flex items-start gap-1.5">
                    <span className="text-dourado mt-0.5">✓</span>
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>

      {!user && (
        <p className="text-center text-xs text-texto-terciario mt-10">
          <a href="/login" className="text-dourado hover:underline">Entre na sua conta</a> para ver o seu plano atual.
        </p>
      )}
    </div>
  )
}
