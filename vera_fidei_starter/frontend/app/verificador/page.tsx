import VerificationForm from '@/components/verificador/VerificationForm'

export default function VerificadorPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 pt-8 pb-4">
      <div className="mb-6">
        <h1 className="font-garamond text-3xl font-semibold text-texto">
          Verificador
        </h1>
        <p className="mt-1 text-sm text-texto-secundario">
          Insira uma citação patrística para verificar sua autenticidade e
          localizar a fonte primária.
        </p>
      </div>
      <VerificationForm />
    </div>
  )
}
