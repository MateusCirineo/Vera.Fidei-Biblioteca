'use client'

import { useState } from 'react'
import ProfileHistory from '@/components/perfil/ProfileHistory'
import ProfileReadingHistory from '@/components/perfil/ProfileReadingHistory'

type HistoryTab = 'readings' | 'citations'

export default function ProfileHistoryTabs({
  userId,
  userPlan,
}: {
  userId: number
  userPlan?: string
}) {
  const [activeTab, setActiveTab] = useState<HistoryTab>('readings')

  return (
    <section
      id="historico"
      className="mt-6 rounded-lg border border-fundo-borda bg-fundo-card p-5 sm:p-6"
      aria-labelledby="profile-history-title"
    >
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
          Histórico
        </p>
        <h2 id="profile-history-title" className="mt-1 font-eb-garamond text-xl text-texto">
          Leituras e verificações
        </h2>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-texto-terciario">
          Retome as obras que estava lendo ou consulte suas citações e verificações anteriores.
        </p>
      </div>

      <div
        className="mt-5 grid grid-cols-2 gap-1 rounded-lg border border-fundo-borda bg-fundo p-1"
        role="tablist"
        aria-label="Tipos de histórico"
      >
        <button
          id="profile-readings-tab"
          type="button"
          role="tab"
          aria-selected={activeTab === 'readings'}
          aria-controls="profile-readings-panel"
          tabIndex={activeTab === 'readings' ? 0 : -1}
          onClick={() => setActiveTab('readings')}
          className={`min-h-11 rounded-md px-3 py-2 text-center text-xs font-semibold transition-colors sm:text-sm ${
            activeTab === 'readings'
              ? 'bg-dourado text-fundo shadow-sm'
              : 'text-texto-secundario hover:bg-fundo-card hover:text-dourado'
          }`}
        >
          Obras e leituras
        </button>
        <button
          id="profile-citations-tab"
          type="button"
          role="tab"
          aria-selected={activeTab === 'citations'}
          aria-controls="profile-citations-panel"
          tabIndex={activeTab === 'citations' ? 0 : -1}
          onClick={() => setActiveTab('citations')}
          className={`min-h-11 rounded-md px-3 py-2 text-center text-xs font-semibold transition-colors sm:text-sm ${
            activeTab === 'citations'
              ? 'bg-dourado text-fundo shadow-sm'
              : 'text-texto-secundario hover:bg-fundo-card hover:text-dourado'
          }`}
        >
          Citações e verificações
        </button>
      </div>

      {activeTab === 'readings' && (
        <div
          id="profile-readings-panel"
          role="tabpanel"
          aria-labelledby="profile-readings-tab"
        >
          <ProfileReadingHistory userId={userId} embedded />
        </div>
      )}

      {activeTab === 'citations' && (
        <div
          id="profile-citations-panel"
          role="tabpanel"
          aria-labelledby="profile-citations-tab"
        >
          <ProfileHistory userPlan={userPlan} embedded />
        </div>
      )}
    </section>
  )
}
