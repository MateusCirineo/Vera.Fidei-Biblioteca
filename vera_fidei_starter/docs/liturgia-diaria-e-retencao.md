# Liturgia Diária e continuidade de leitura

## Decisão de produto

O Vera Fidei deve oferecer uma experiência cotidiana sem deixar de ser
biblioteca, instrumento de estudo, oração e verificação de fontes.

O ciclo aprovado é:

1. **Liturgia Diária:** dá ao usuário um motivo legítimo para abrir o Vera
   Fidei todos os dias.
2. **Continuar lendo:** permite retomar exatamente a obra, edição, arquivo e
   página em que a leitura parou.
3. **Conteúdo relacionado:** aproxima as leituras do dia dos Santos, Orações,
   Padres da Igreja, Catecismos e documentos já presentes no acervo.

Nenhuma dessas áreas deve ser reduzida a simples ferramenta de divulgação ou
funil comercial. Elas fazem parte da finalidade católica e documental do
produto.

## Prioridade aprovada

Antes da Liturgia Diária, implementar e validar:

- salvamento automático da leitura por usuário, obra, edição e PDF;
- sincronização da última página entre PWA, computador e celular;
- fallback local para conexão instável e posterior sincronização;
- ação **Continuar lendo — página X de Y**;
- ação **Recomeçar**, retornando ao início real da obra naquele PDF;
- histórico de obras lidas ou acessadas, separado dos favoritos e do histórico
  de verificações;
- seção de leituras recentes no Perfil;
- privacidade: progresso incluído na exportação e removido com a conta.

Favorito e histórico têm funções diferentes:

- **Favorito:** algo que o usuário escolheu guardar.
- **Histórico de leitura:** algo que ele abriu ou estava lendo.
- **Progresso:** posição exata necessária para continuar.

## Integração da Liturgia Diária

A Liturgia Diária não deve ser misturada aos grupos e contadores das orações
estáveis, nem ocupar uma sétima posição na navegação inferior.

Experiência proposta:

- card destacado **Liturgia de hoje** no Início e na área de Orações;
- tela própria, inicialmente em `/liturgia` ou rota equivalente definida na
  implementação;
- data, celebração, cor litúrgica, primeira leitura, salmo, segunda leitura
  quando houver e Evangelho;
- fonte, horário de atualização e estado de disponibilidade visíveis;
- ligação com o Santo do dia e com orações pertinentes;
- referências para encontrar, no acervo, Padres, Catecismos e documentos
  relacionados às leituras;
- notificação diária somente mediante consentimento do usuário;
- cache diário com timeout e fallback, sem carregamento infinito.

## Fonte e direitos

A integração não deve copiar, raspar ou armazenar leituras integrais apenas
porque elas estão publicamente acessíveis na internet.

Fonte prioritária: CNBB/Edições CNBB, responsável pela tradução oficial usada
no Brasil e pelo portal <https://liturgiadiaria.edicoescnbb.com.br/>.

Antes de republicar o texto integral na PWA ou no aplicativo nativo, obter
autorização escrita que cubra:

- PWA e aplicativo Android;
- área gratuita e planos pagos;
- cache, funcionamento offline e notificações;
- busca e indexação;
- atribuição e correções;
- eventual leitura em voz alta.

Endpoints técnicos da CNBB ou da Canção Nova não devem ser tratados como API
pública licenciada sem autorização expressa. Até existir licença, a alternativa
segura é mostrar somente dados autorizados e oferecer um link identificado para
a fonte oficial, sem iframe, cópia ou armazenamento do texto integral.

## Critérios de conclusão

A Liturgia Diária estará pronta quando:

- a origem e a licença estiverem documentadas;
- a data e o calendário brasileiro estiverem corretos;
- todos os blocos litúrgicos vierem da mesma edição e do mesmo dia;
- o conteúdo apresentar fonte e atualização;
- falhas externas produzirem mensagem clara e fallback seguro;
- a tela funcionar na PWA e no mobile sem alterar as áreas existentes;
- testes cobrirem mudança de data, domingos, solenidades, segunda leitura,
  indisponibilidade da fonte e cache.

## Métricas úteis, sem manipulação

- usuários que abrem a Liturgia do dia;
- retorno em 7 e 30 dias;
- leituras retomadas pelo botão **Continuar lendo**;
- obras iniciadas e concluídas;
- falhas de carregamento e sincronização.

Não usar sequências artificiais, culpa, notificações insistentes ou bloqueios
para forçar retorno. O hábito deve vir da utilidade espiritual e da continuidade
real do estudo.
