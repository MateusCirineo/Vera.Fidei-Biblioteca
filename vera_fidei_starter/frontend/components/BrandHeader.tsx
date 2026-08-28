import Image from 'next/image'
import SectionHeading from '@/components/ui/SectionHeading'

interface BrandHeaderProps {
  title: string
  description: string
}

export default function BrandHeader({ title, description }: BrandHeaderProps) {
  return (
    <header className="mb-7">
      <div className="mb-6 flex min-h-14 items-center gap-3 pr-20 sm:pr-24">
        <Image
          src="/branding/Logo-VF-seal.png"
          alt="Vera.Fidei Católico"
          width={96}
          height={96}
          className="h-12 w-12 shrink-0 rounded-full border border-dourado/25 shadow-[0_0_28px_rgba(201,168,76,0.12)]"
          priority
        />
        <div>
          <p className="font-garamond text-xl font-semibold leading-none text-texto">
            Vera.Fidei
          </p>
          <p className="mt-1 text-[11px] font-medium tracking-wide text-dourado">
            Biblioteca Católica Digital
          </p>
        </div>
      </div>

      <SectionHeading as="h1" description={description}>
        {title}
      </SectionHeading>
    </header>
  )
}
