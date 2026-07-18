'use client'

import Image from 'next/image'
import type { ReactNode } from 'react'

interface AuthShellProps {
  title: ReactNode
  subtitle: ReactNode
  children: ReactNode
  footer: ReactNode
}

export default function AuthShell({ title, subtitle, children, footer }: AuthShellProps) {
  return (
    <div className="min-h-[calc(100dvh-5rem)] px-4 pb-28 pt-10 sm:pt-16">
      <div className="mx-auto flex w-full max-w-sm flex-col items-center">
        <Image
          src="/branding/Logo-VF-seal.png"
          alt="Vera.Fidei"
          width={160}
          height={160}
          priority
          className="h-28 w-28 rounded-full shadow-[0_0_34px_rgba(201,168,76,0.18)]"
        />

        <div className="mt-4 text-center">
          <p className="font-garamond text-4xl font-semibold leading-none text-dourado">
            Vera.Fidei
          </p>
          <p className="mt-2 text-xs font-medium uppercase tracking-[0.22em] text-dourado-claro">
            Biblioteca Cat&oacute;lica Digital
          </p>
        </div>

        <div className="mt-8 w-full rounded-lg border border-dourado/25 bg-fundo-card px-5 py-6 shadow-[0_18px_70px_rgba(0,0,0,0.32)]">
          <div className="mb-6 text-center">
            <h1 className="font-garamond text-2xl font-semibold text-texto">
              {title}
            </h1>
            <p className="mt-1 text-sm text-texto-terciario">{subtitle}</p>
          </div>

          {children}

          <div className="mt-6 border-t border-fundo-borda pt-5">
            {footer}
          </div>
        </div>
      </div>
    </div>
  )
}
