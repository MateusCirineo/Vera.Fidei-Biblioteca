import AdminTabs from '@/components/admin/AdminTabs'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

const INTERNAL_API = process.env.INTERNAL_API_URL ?? 'https://verafidei.oialfred.com/api'

export default async function AdminPage() {
  const token = (await cookies()).get('vf_token')?.value
  if (!token) redirect('/login?redirect=/admin')

  const response = await fetch(`${INTERNAL_API}/auth/admin`, {
    cache: 'no-store',
    headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(10_000),
  }).catch(() => null)
  if (!response?.ok) redirect('/perfil?admin=negado')

  return (
    <div className="mx-auto max-w-6xl px-4 pt-8 pb-24">
      <div className="mb-6">
        <h1 className="font-garamond text-3xl font-semibold text-texto">
          Admin
        </h1>
        <p className="mt-1 text-sm text-texto-secundario">
          Acompanhe métricas em tempo real e gerencie o acervo, os PDFs e os cupons.
        </p>
      </div>

      <AdminTabs />
    </div>
  )
}
