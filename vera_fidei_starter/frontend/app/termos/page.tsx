import Link from 'next/link'
import BrandHeader from '@/components/BrandHeader'

const sections = [
  {
    title: '1. Uso da plataforma',
    text: 'O Vera.Fidei oferece biblioteca digital, consulta de fontes e verificação de citações para estudo, pesquisa, catequese e produção de conteúdo. O usuário deve utilizar a plataforma de modo lícito, respeitoso e compatível com sua finalidade.',
  },
  {
    title: '2. Conta e segurança',
    text: 'O usuário é responsável por manter seus dados de acesso protegidos e por informar dados corretos ao criar ou manter sua conta. Atividades automatizadas abusivas, tentativas de invasão, extração indevida de dados ou uso que comprometa a estabilidade do serviço podem gerar bloqueio de acesso.',
  },
  {
    title: '3. Verificação de citações',
    text: 'Os resultados do verificador auxiliam a localizar correspondências, contexto e referências, mas não substituem estudo crítico, revisão humana, orientação acadêmica, jurídica ou eclesiástica. Sempre que a precisão for essencial, confira a fonte original indicada.',
  },
  {
    title: '4. Planos e assinaturas',
    text: 'Os planos pagos são mensais e processados por provedor externo de pagamento. A liberação, alteração ou cancelamento do plano depende da confirmação do pagamento e dos eventos recebidos pelo sistema. O usuário pode cancelar a assinatura pelo portal de cobrança quando disponível em sua conta.',
  },
  {
    title: '5. Propriedade intelectual',
    text: 'A marca, a organização da plataforma, a interface, o código e os textos próprios do Vera.Fidei pertencem ao projeto e ao seu autor. Obras e documentos de terceiros mantêm suas respectivas titularidades, licenças e condições de uso.',
  },
  {
    title: '6. Disponibilidade e alterações',
    text: 'O serviço pode passar por manutenção, ajustes técnicos e mudanças de funcionalidades. O Vera.Fidei pode atualizar estes termos para refletir melhorias do produto, exigências legais ou alterações operacionais.',
  },
  {
    title: '7. Cancelamento, arrependimento e reembolso',
    text: 'A assinatura pode ser cancelada pelo portal de cobrança disponível na conta. Solicitações de arrependimento ou reembolso podem ser enviadas pela página de contato e serão tratadas conforme a legislação brasileira aplicável, sem limitação dos direitos legalmente assegurados ao consumidor.',
  },
  {
    title: '8. Legislação e atendimento',
    text: 'Estes termos são regidos pela legislação brasileira. Dúvidas, solicitações sobre cobrança, exercício de direitos ou comunicações relacionadas ao serviço podem ser encaminhadas pela página de contato do Vera.Fidei.',
  },
]

export default function TermosPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:py-10">
      <BrandHeader
        title="Termos de uso"
        description="Condições gerais para uso do Vera.Fidei."
      />

      <p className="rounded-lg border border-fundo-borda bg-fundo-card p-4 text-xs leading-relaxed text-texto-terciario">
        Atualizado em 24 de agosto de 2026. Esta é a versão vigente dos Termos
        de Uso do Vera.Fidei.
      </p>

      <div className="mt-7 space-y-6">
        {sections.map((section) => (
          <section key={section.title} className="space-y-2">
            <h2 className="font-garamond text-2xl font-semibold text-dourado">
              {section.title}
            </h2>
            <p className="text-sm leading-relaxed text-texto-secundario">
              {section.text}
            </p>
          </section>
        ))}
      </div>

      <section className="mt-8 rounded-lg border border-fundo-borda bg-fundo-card p-5">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Contato
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-texto-secundario">
          Dúvidas sobre estes termos podem ser enviadas pela página de contato.
        </p>
        <Link
          href="/contato"
          className="mt-4 inline-flex rounded-md border border-dourado/40 px-4 py-2.5 text-sm font-semibold text-dourado transition-colors hover:bg-dourado hover:text-fundo"
        >
          Falar com suporte
        </Link>
      </section>
    </div>
  )
}
