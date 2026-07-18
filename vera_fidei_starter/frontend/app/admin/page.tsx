import AdminTabs from '@/components/admin/AdminTabs'

export default function AdminPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-8 pb-24">
      <div className="mb-6">
        <h1 className="font-garamond text-3xl font-semibold text-texto">
          Admin
        </h1>
        <p className="mt-1 text-sm text-texto-secundario">
          Gerencie o acervo, os PDFs anexados e os cupons de assinatura.
        </p>
      </div>

      <AdminTabs />
    </div>
  )
}
