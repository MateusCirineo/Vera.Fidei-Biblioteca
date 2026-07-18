import Link from 'next/link'
import BrandHeader from '@/components/BrandHeader'

const channels = [
  {
    label: 'E-mail',
    value: 'vera.fidei661@gmail.com',
    href: 'mailto:vera.fidei661@gmail.com?subject=Suporte%20Vera.Fidei',
  },
  {
    label: 'Instagram',
    value: '@vera.fidei',
    href: 'https://www.instagram.com/vera.fidei',
  },
  {
    label: 'YouTube',
    value: '@mattcirineo',
    href: 'https://www.youtube.com/@mattcirineo',
  },
]

const supportTips = [
  'Para assinatura, envie o e-mail da conta e o plano escolhido.',
  'Para erro no verificador, envie o texto consultado e o horário aproximado.',
  'Para privacidade, diga qual direito deseja exercer e qual conta está envolvida.',
]

export default function ContatoPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:py-10">
      <BrandHeader
        title="Contato e suporte"
        description="Canais para dúvidas, assinatura, privacidade e suporte técnico."
      />

      <section className="grid gap-3 sm:grid-cols-3">
        {channels.map((channel) => (
          <a
            key={channel.label}
            href={channel.href}
            target={channel.href.startsWith('http') ? '_blank' : undefined}
            rel={channel.href.startsWith('http') ? 'noreferrer' : undefined}
            className="rounded-lg border border-fundo-borda bg-fundo-card p-4 transition-colors hover:border-dourado/45"
          >
            <p className="text-xs uppercase tracking-[0.18em] text-texto-terciario">
              {channel.label}
            </p>
            <p className="mt-2 break-words text-sm font-medium text-texto">
              {channel.value}
            </p>
          </a>
        ))}
      </section>

      <section className="mt-8 rounded-lg border border-fundo-borda bg-fundo-card p-5">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Como agilizar o atendimento
        </h2>
        <div className="mt-4 grid gap-3">
          {supportTips.map((tip) => (
            <div key={tip} className="flex gap-3 text-sm leading-relaxed text-texto-secundario">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-dourado" />
              <p>{tip}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8 space-y-4">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Links úteis
        </h2>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/planos"
            className="rounded-md border border-dourado/40 px-4 py-2.5 text-sm font-semibold text-dourado transition-colors hover:bg-dourado hover:text-fundo"
          >
            Planos
          </Link>
          <Link
            href="/termos"
            className="rounded-md border border-fundo-borda px-4 py-2.5 text-sm font-semibold text-texto-secundario transition-colors hover:border-dourado/40 hover:text-dourado"
          >
            Termos de uso
          </Link>
          <Link
            href="/privacidade"
            className="rounded-md border border-fundo-borda px-4 py-2.5 text-sm font-semibold text-texto-secundario transition-colors hover:border-dourado/40 hover:text-dourado"
          >
            Privacidade
          </Link>
        </div>
      </section>
    </div>
  )
}
