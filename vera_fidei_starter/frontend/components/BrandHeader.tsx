import Image from 'next/image'

interface BrandHeaderProps {
  title: string
  description: string
}

export default function BrandHeader({ title, description }: BrandHeaderProps) {
  return (
    <header className="mb-6">
      <div className="mb-5 flex items-center gap-3">
        <Image
          src="/branding/Logo-VF.png"
          alt="Vera.Fidei Católico"
          width={96}
          height={54}
          className="h-12 w-auto shrink-0"
          priority
        />
        <div>
          <p className="font-garamond text-lg font-semibold text-texto">
            Vera.Fidei
          </p>
          <p className="text-xs text-dourado">Biblioteca Católica Digital</p>
        </div>
      </div>

      <h1 className="font-garamond text-3xl font-semibold text-texto">
        {title}
      </h1>
      <p className="mt-1 text-sm text-texto-secundario">{description}</p>
    </header>
  )
}
