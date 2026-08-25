# Automação editorial do Instagram Vera.Fidei

O fluxo gera um carrossel rastreável a partir do acervo e só o publica quando
todas as travas estão satisfeitas. Ele não automatiza curtidas, comentários,
seguidores ou mensagens.

Este documento é o contrato permanente de Codex, Claude Code e dos agentes do
Vera.Fidei. Não é permitido substituir esse padrão por uma interpretação livre.
O contrato visual universal e prioritário está em `../../INSTAGRAM_STYLE.md`.

## Contrato visual homologado

- Sempre gerar exatamente três imagens de `1856 x 2304`.
- Capa: usar `backend/app/social/assets/references/cover_saint_ambrose.png`
  como arquitetura literal, trocando apenas retrato, autor e parte.
- Citação: usar
  `backend/app/social/assets/templates/page_with_logo.png`, que já contém o
  pergaminho e a logo inferior. O corpo deve usar Arial Rounded MT Bold do
  arquivo configurado como `SOCIAL_BODY_FONT_PATH`, no tamanho homologado pelo
  renderizador. Não existe fallback silencioso de fonte.
- Referência completa no topo: autor, datas, século, obra, coleção/volume,
  capítulo ou seção quando disponível, página/colunas e edição.
- Palavras-chave: marrom escuro RGB `(102, 29, 20)`; restante do corpo em preto.
- A base da página de citação deve mostrar recortes reais que contenham o texto
  escolhido, localizados no PDF da própria obra.
- Capa final: usar
  `backend/app/social/assets/references/cta_saint_ambrose.jpg`, preservando
  moldura, composição, chamada e logo; mostrar folha de rosto, fonte e retrato
  do autor correto.
- A prévia homologada em 8 de agosto de 2026 foi a de Santo Agostinho,
  *Comentário aos Salmos (1-50)*, PT 9, p. 54, Paulus. Ela é somente uma
  referência visual: todo conteúdo variável deve ser substituído pelos dados
  reais de cada nova publicação. Os três assets acima são as referências
  versionadas de composição.

Qualquer alteração em fonte, assets ou código visual muda o hash do estilo e
obriga nova prévia e nova aprovação explícita do proprietário.

## Processo dos agentes

1. `orchestrator` define a missão e a ordem das etapas.
2. `planner` registra objetivo, riscos e critério de conclusão.
3. `social_source_agent` escolhe um trecho ainda não publicado. A busca só
   sugere o `chunk_id`; autor, obra, edição, tradução e página são reconstruídos
   do mesmo registro PostgreSQL.
4. `social_consistency_agent` bloqueia índice, OCR quebrado, repetição, autor
   divergente, retrato não aprovado, página ausente ou citação que não possa ser
   localizada dentro do PDF.
5. `social_copy_agent` monta a legenda exclusivamente com os dados validados.
6. `social_art_agent` gera três imagens de 1856 x 2304:
   capa no padrão de Santo Ambrósio, página de citação na fonte Arial Rounded MT
   Bold com destaques em marrom e logo, e capa final no padrão fornecido.
7. `social_approval_agent` confere se o estilo atual foi homologado. Alterações
   no layout, fonte ou assets invalidam automaticamente a homologação.
8. `social_publish_agent` envia as imagens ao endereço público, cria o carrossel
   pela API oficial e grava o ID remoto no ledger.

## Regras que impedem o erro Santo Ambrósio/Santo Agostinho

- Um único `chunk_id` é a origem de autor, obra, texto, edição e página.
- A arte só aceita retratos listados no manifesto de imagens aprovadas.
- A citação precisa ser encontrada dentro da própria página do PDF.
- O ledger bloqueia trechos repetidos e mantém os IDs publicados.
- Se a imagem do santo, a página, a folha de rosto ou a referência falhar, a
  execução para antes da arte/publicação.

## Operação

Gerar uma prévia, sem publicar:

```powershell
.\.venv\Scripts\python.exe -B scripts\run_instagram_agents.py
```

Ver as travas sem mostrar segredos:

```powershell
.\.venv\Scripts\python.exe -B scripts\run_instagram_agents.py --readiness
```

Depois de conferir visualmente a prévia, homologar o estilo:

```powershell
.\.venv\Scripts\python.exe -B scripts\run_instagram_agents.py --approve-style "CAMINHO_DA_PREVIA"
```

Para habilitar a publicação automática, também é obrigatório rotacionar as
credenciais expostas, configurar `INSTAGRAM_PUBLISH_ENABLED=true` e
`INSTAGRAM_SCHEDULE_ENABLED=true`, e então instalar a tarefa diária:

```powershell
.\scripts\install_instagram_schedule.ps1 -At "12:00"
```

A tarefa é idempotente: no máximo uma publicação por data local. Falhas ficam
registradas em `data/social/instagram_posts.jsonl` e logs em
`data/social/logs/`.
