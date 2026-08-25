import Link from 'next/link'
import BrandHeader from '@/components/BrandHeader'

const dataItems = [
  'Dados de cadastro, como nome, e-mail e informações da conta.',
  'Histórico de verificações, favoritos, contagem de buscas, limites e plano ativo.',
  'Textos religiosos enviados ao verificador ou salvos como favoritos podem revelar interesses ou convicções religiosas e recebem tratamento compatível com essa sensibilidade.',
  'Dados técnicos necessários para segurança, autenticação, logs e prevenção de abuso.',
  'Métricas próprias de acesso por navegador, usando identificador aleatório em cookie. Para essa medição não armazenamos endereço IP, identificação da conta, navegador ou termos pesquisados.',
  'Dados de pagamento processados pela Stripe; o Vera.Fidei não armazena número completo de cartão.',
]

const rights = [
  'Confirmar se há tratamento de dados pessoais.',
  'Acessar, exportar, corrigir ou solicitar eliminação quando aplicável.',
  'Solicitar informações sobre compartilhamento e tratamento.',
  'Revogar consentimentos quando esta for a base usada.',
]

export default function PrivacidadePage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:py-10">
      <BrandHeader
        title="Política de privacidade"
        description="Como o Vera.Fidei trata dados pessoais e dados de uso."
      />

      <p className="rounded-lg border border-fundo-borda bg-fundo-card p-4 text-xs leading-relaxed text-texto-terciario">
        Atualizada em 21 de agosto de 2026. Esta política foi estruturada com
        base na LGPD e em orientações públicas da Autoridade Nacional de
        Proteção de Dados.
      </p>

      <section className="mt-8 space-y-3">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Dados que podemos tratar
        </h2>
        <div className="grid gap-3">
          {dataItems.map((item) => (
            <div
              key={item}
              className="rounded-lg border border-fundo-borda bg-fundo-card p-4 text-sm leading-relaxed text-texto-secundario"
            >
              {item}
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8 space-y-3">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Finalidades
        </h2>
        <p className="text-sm leading-relaxed text-texto-secundario">
          Os dados são usados para criar e proteger contas, autenticar usuários,
          entregar a biblioteca e o verificador, controlar limites de uso,
          processar assinaturas, responder solicitações de suporte e melhorar a
          estabilidade do serviço. Métricas agregadas permitem acompanhar acessos
          e uso das funções sem identificar pessoalmente os visitantes. O conteúdo pesquisado não é vendido nem usado
          para publicidade comportamental.
        </p>
      </section>

      <section className="mt-8 space-y-3">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Compartilhamento
        </h2>
        <p className="text-sm leading-relaxed text-texto-secundario">
          Podemos compartilhar dados estritamente necessários com provedores de
          infraestrutura, autenticação, banco de dados, segurança e pagamento.
          Assinaturas e cobranças são operadas pela Stripe, conforme os fluxos
          de checkout, portal de cobrança e webhooks configurados no sistema.
        </p>
      </section>

      <section className="mt-8 space-y-3">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Direitos do titular
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {rights.map((right) => (
            <div
              key={right}
              className="rounded-lg border border-fundo-borda bg-fundo-card p-4 text-sm leading-relaxed text-texto-secundario"
            >
              {right}
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8 space-y-3">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Segurança e retenção
        </h2>
        <p className="text-sm leading-relaxed text-texto-secundario">
          Mantemos medidas técnicas e administrativas para reduzir riscos de
          acesso indevido, perda ou alteração de dados. As informações são
          mantidas pelo tempo necessário para operar o serviço, cumprir
          obrigações legais, resolver disputas e preservar a segurança da
          plataforma. Quando a conta é excluída, os dados operacionais vinculados
          a ela são removidos do banco ativo. Registros que precisem ser mantidos
          por obrigação legal, prevenção a fraude ou defesa de direitos poderão
          ser conservados pelo prazo estritamente necessário. Backups seguem seu
          ciclo protegido de retenção e não retornam ao uso normal do produto.
        </p>
      </section>

      <section className="mt-8 rounded-lg border border-fundo-borda bg-fundo-card p-5">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Solicitações
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-texto-secundario">
          Usuários autenticados podem exportar seus dados ou excluir a conta
          diretamente no Perfil. Para correção, oposição, portabilidade ou outros
          esclarecimentos, use a página de contato.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            href="/perfil"
            className="rounded-md bg-dourado px-4 py-2.5 text-sm font-semibold text-fundo transition-colors hover:bg-dourado-claro"
          >
            Gerenciar meus dados
          </Link>
          <Link
            href="/contato"
            className="rounded-md border border-fundo-borda px-4 py-2.5 text-sm font-semibold text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
          >
            Entrar em contato
          </Link>
          <a
            href="https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares"
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-dourado/40 px-4 py-2.5 text-sm font-semibold text-dourado transition-colors hover:bg-dourado hover:text-fundo"
          >
            Direitos na ANPD
          </a>
        </div>
      </section>
    </div>
  )
}
