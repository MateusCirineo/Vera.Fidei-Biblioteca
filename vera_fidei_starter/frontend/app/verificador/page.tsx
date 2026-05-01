import VerificationForm from '@/components/verificador/VerificationForm'
import BrandHeader from '@/components/BrandHeader'

export default function VerificadorPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 pt-8 pb-4">
      <BrandHeader
        title="Verificador"
        description="Insira uma citação patrística para verificar sua autenticidade e localizar a fonte primária."
      />
      <VerificationForm />
    </div>
  )
}
