# Carta de Parceria — Editora Paulus
**Para:** [e-mail da Editora Paulus]
**Assunto:** Proposta de Parceria — Vera.Fidei: Plataforma Católica de Verificação de Citações

---

Prezada Equipe da Editora Paulus,

Meu nome é Mateus Cirineo, desenvolvedor e idealizador do **Vera.Fidei Biblioteca** — uma plataforma digital católica criada para combater a desinformação teológica e facilitar o acesso a fontes primárias da tradição da Igreja.

Escrevo com o objetivo de apresentar o projeto e propor uma parceria que acredito ser de grande valor tanto para a missão evangelizadora da Editora Paulus quanto para a comunidade católica que busca fontes confiáveis.

---

## O que é o Vera.Fidei

O Vera.Fidei é uma plataforma web e aplicativo mobile (Android/iOS) que reúne duas funções principais:

**1. Biblioteca Patrística e Teológica Digital**
Um acervo digital de obras dos Padres da Igreja, documentos conciliares, encíclicas e textos teológicos, organizado e pesquisável. O usuário pode navegar por coleções como a *Patrologia Latina* e a *Patrologia Graeca* de Migne, obras do magistério papal, atas de concílios e outros textos fundamentais da tradição católica.

**2. Verificador de Citações com Inteligência Artificial**
O coração do projeto: um sistema de verificação de citações patrísticas e teológicas baseado em múltiplos agentes de inteligência artificial. O usuário cola uma citação atribuída a um autor (por exemplo, Santo Agostinho, São Tomás de Aquino ou um documento conciliar), e o sistema realiza uma verificação completa, indicando se a citação é:

- **Confirmada** — localizada na fonte, com alta correspondência textual e contexto correto
- **Provável** — forte candidato de fonte, sem evidência contrária
- **Inconclusiva** — fonte não localizada com certeza ou edição desconhecida
- **Não sustentada** — paráfrase inventada, atribuição sem fonte rastreável

O sistema verifica idioma, edição, contexto anterior e posterior, fidelidade de tradução e consistência entre agentes — gerando um laudo estruturado e auditável, sem depender de respostas genéricas de IA.

---

## Por que isso importa

Vivemos um momento de crescente circulação de citações falsas ou distorcidas atribuídas a santos, papas e concílios. Frases inventadas, paráfrases imprecisas e desvios de contexto se espalham rapidamente em ambientes digitais, causando confusão doutrinária e prejuízo à credibilidade da Igreja.

O Vera.Fidei nasceu para ser uma resposta técnica e pastoral a esse problema: uma ferramenta acessível a qualquer católico — do leigo ao teólogo — que precise verificar se uma citação é realmente de quem dizem que é, e se está sendo usada corretamente.

---

## Como os livros são utilizados na plataforma

Os livros disponíveis na biblioteca passam por um processo de ingestão técnica que funciona da seguinte forma:

1. **Indexação semântica:** O conteúdo do PDF é processado em blocos de texto que são indexados para busca semântica (por significado) e textual (por palavras exatas). Nenhum conteúdo é alterado ou reescrito.

2. **Busca e verificação:** Quando um usuário submete uma citação para verificação, o sistema busca nos textos indexados trechos correspondentes, extrai o trecho relevante com seu contexto e apresenta a referência exata (obra, volume, página, coluna).

3. **Visualização do original:** O usuário pode acessar o PDF original da obra para conferir o trecho localizado, com navegação direta até a página indicada — garantindo total transparência e acesso à fonte primária.

Os livros **não são redistribuídos livremente** nem disponibilizados para download. Eles funcionam como acervo de referência dentro da plataforma, de forma análoga ao uso em bibliotecas digitais acadêmicas.

---

## O que estou solicitando

### 1. Autorização de uso
Solicito autorização para incluir obras publicadas pela Editora Paulus na biblioteca do Vera.Fidei, especialmente títulos de natureza teológica, patrística, hagiográfica e litúrgica — para fins de consulta, pesquisa e verificação de citações dentro da plataforma.

Estou aberto a discutir os termos de uso, incluindo:
- Quais títulos poderiam ser autorizados
- Modalidade de exibição (trechos apenas, ou acesso completo restrito a assinantes)
- Créditos e atribuição da editora em destaque na plataforma

### 2. Parceria e patrocínio
O Vera.Fidei é um projeto independente, desenvolvido com recursos próprios e movido por missão. Para garantir sua sustentabilidade e crescimento — incluindo servidores, armazenamento em nuvem e desenvolvimento contínuo — estou buscando parceiros que compartilhem do mesmo compromisso com a formação católica séria.

Uma parceria com a Editora Paulus poderia incluir:
- Patrocínio financeiro para manutenção da infraestrutura
- Inclusão do selo e marca da Editora Paulus na plataforma como parceira oficial
- Divulgação mútua nos canais digitais de ambas as partes
- Acesso antecipado a novas funcionalidades e relatórios de uso

---

## Modelo de planos do Verificador de Citações

O Vera.Fidei está em desenvolvimento ativo e constante atualização. O modelo de assinatura encontra-se em fase de implementação, com previsão de lançamento em breve. A plataforma adotará planos progressivos, com nomes inspirados na tradição e missão da Igreja:

| Plano | Preço | Verificações/mês |
|---|---|---|
| **Fiel** | Gratuito | 10 |
| **Catequista** | R$ 9,90/mês | 25 |
| **Apologeta** | R$ 29,99/mês | 50 |
| **Patrístico** | R$ 59,99/mês | 100 |
| **Magistério** *(API institucional)* | R$ 99,99/mês | Sob consulta |

Funcionalidades adicionais como exportação de laudos em PDF, painel de gestão institucional e integração via API já estão sendo projetadas e serão incorporadas à plataforma nas próximas versões.

> Livros autorizados por parceiros como a Editora Paulus poderiam ser destacados com o **selo de parceria**, valorizando a origem das obras e fortalecendo o reconhecimento da editora junto ao público da plataforma.

---

## Sobre o projeto

- **Plataforma:** Web (PWA, instalável) + App Android/iOS (Flutter)
- **Tecnologia:** FastAPI (backend), Next.js (frontend), PostgreSQL, Elasticsearch, ChromaDB
- **Público-alvo:** Leigos, estudantes de teologia, seminaristas, sacerdotes, catequistas e pesquisadores
- **Acervo atual:** Patrologia Latina e Graeca (Migne), documentos conciliares e papais em domínio público
- **Repositório:** https://github.com/MateusCirineo/Vera.Fidei-Biblioteca

---

Acredito que o Vera.Fidei e a Editora Paulus compartilham a mesma missão: levar a fé católica com seriedade, profundidade e acessibilidade ao povo de Deus. Uma parceria entre nós seria natural e frutífera.

Coloco-me à disposição para uma reunião, chamada ou troca de e-mails para apresentar o projeto com mais detalhes, tirar dúvidas e discutir os termos de colaboração.

Agradeço imensamente pela atenção e pelo trabalho que a Editora Paulus realiza em favor da Igreja no Brasil.

Com fraternidade e respeito,

**Mateus Cirineo**
Desenvolvedor e idealizador do Vera.Fidei Biblioteca
GitHub: https://github.com/MateusCirineo
[Seu e-mail]
[Seu telefone/WhatsApp]
