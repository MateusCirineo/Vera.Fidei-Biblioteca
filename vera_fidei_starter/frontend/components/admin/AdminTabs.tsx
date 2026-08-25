'use client'

import { useState } from 'react'
import type { ReactNode } from 'react'
import UploadForm from '@/components/admin/UploadForm'
import BookList from '@/components/admin/BookList'
import CouponList from '@/components/admin/CouponList'
import AdminMetrics from '@/components/admin/AdminMetrics'

type AdminTab = 'metrics' | 'books' | 'coupons'

export default function AdminTabs() {
  const [activeTab, setActiveTab] = useState<AdminTab>('metrics')

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap gap-2 rounded-lg border border-fundo-borda bg-fundo-card p-2">
        <TabButton active={activeTab === 'metrics'} onClick={() => setActiveTab('metrics')}>
          Métricas
        </TabButton>
        <TabButton active={activeTab === 'books'} onClick={() => setActiveTab('books')}>
          Obras
        </TabButton>
        <TabButton active={activeTab === 'coupons'} onClick={() => setActiveTab('coupons')}>
          Cupons
        </TabButton>
      </div>

      {activeTab === 'metrics' ? (
        <AdminMetrics />
      ) : activeTab === 'books' ? (
        <div className="space-y-10">
          <UploadForm />
          <div className="border-t border-fundo-borda pt-8">
            <BookList />
          </div>
        </div>
      ) : (
        <CouponList />
      )}
    </div>
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'h-10 rounded-md px-4 text-sm font-semibold transition-colors',
        active
          ? 'bg-dourado text-fundo'
          : 'border border-fundo-borda text-texto-secundario hover:border-dourado/60 hover:text-dourado',
      ].join(' ')}
    >
      {children}
    </button>
  )
}
