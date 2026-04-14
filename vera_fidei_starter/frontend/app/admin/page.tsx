import UploadForm from '@/components/admin/UploadForm'
import BookList from '@/components/admin/BookList'

export default function AdminPage() {
  return (
    <div className="mx-auto max-w-lg px-4 pt-8 pb-24 space-y-10">
      <div>
        <div className="mb-6">
          <h1 className="font-garamond text-3xl font-semibold text-texto">
            Admin
          </h1>
          <p className="mt-1 text-sm text-texto-secundario">
            Upload de PDFs — o backend detecta tudo automaticamente.
          </p>
        </div>
        <UploadForm />
      </div>

      <div className="border-t border-fundo-borda pt-8">
        <BookList />
      </div>
    </div>
  )
}
