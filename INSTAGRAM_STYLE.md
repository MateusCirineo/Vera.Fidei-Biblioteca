# PADRÃO OBRIGATÓRIO PARA TODAS AS PUBLICAÇÕES DO INSTAGRAM VERA.FIDEI

Este arquivo deve ser lido integralmente por Codex, Claude Code e qualquer
agente antes de criar, alterar, aprovar, agendar ou publicar conteúdo para o
Instagram do Vera.Fidei.

## Escopo universal

Este padrão se aplica a **todas as publicações**, independentemente de autor,
santo, Padre da Igreja, obra, coleção, tema ou idioma. Santo Agostinho é apenas
uma prévia aprovada; Santo Ambrósio é apenas a origem dos modelos visuais. Eles
nunca devem ficar fixos no conteúdo de novos posts.

## Elementos fixos em todo post

- Exatamente três imagens, cada uma com `1856 x 2304` pixels.
- Capa com a mesma arquitetura visual do modelo de Santo Ambrósio.
- Página central sobre o pergaminho fornecido, com a logo original no rodapé.
- Corpo em Arial Rounded MT Bold (`ARLRDBD.TTF`), no tamanho homologado pelo
  renderizador.
- Palavras-chave em marrom escuro RGB `(102, 29, 20)`; demais palavras em
  preto.
- Referência completa no topo, seguindo o exemplo aprovado.
- Recortes verdadeiros da página-fonte na base da página central.
- Capa final com a mesma moldura, organização, chamada e logo do modelo
  fornecido.
- Legenda rastreável, construída apenas com dados conferidos no acervo.

## Elementos que obrigatoriamente mudam conforme a publicação

- Nome do autor ou santo.
- Datas e século.
- Retrato correto e previamente aprovado daquele autor.
- Nome da obra.
- Idioma da obra e da tradução apresentada.
- Coleção, volume, capítulo, seção, página, colunas e edição, quando existirem.
- Citação, palavras-chave, recortes da fonte e legenda.

Nunca reutilizar metadados, texto, referência ou retrato do post anterior.

## Regra de integridade da fonte

Autor, obra, citação, idioma, tradução, edição, página e recorte comprobatório
devem ser reconstruídos do mesmo `chunk_id`, livro e arquivo PDF. A busca pode
apenas sugerir o trecho; ela não pode preencher ou corrigir os metadados por
suposição.

Se qualquer elemento divergir, estiver ausente ou parecer índice, nota,
introdução, OCR quebrado ou conteúdo repetido, o post deve ser bloqueado.

## Retratos

- Um retrato encontrado automaticamente pode ser usado somente numa prévia.
- A publicação real exige aprovação no manifesto de retratos.
- Se ainda não houver retrato para o novo autor, preparar uma prévia para
  revisão; nunca usar a imagem de outro santo nem publicar um resultado de
  busca sem aprovação.

## Fluxo obrigatório

```text
orchestrator → planner → social_source_agent → social_consistency_agent
→ social_copy_agent → social_art_agent → social_approval_agent
→ social_publish_agent
```

Toda publicação deve passar por esse fluxo. Não criar atalhos ou scripts
alternativos que publiquem diretamente.

## Aprovação e alterações

- O padrão visual aprovado vale para todos os autores e obras.
- Cada novo retrato ainda precisa representar corretamente o autor exibido.
- Qualquer mudança na fonte, dimensões, cores, templates, composição ou código
  visual invalida o hash do estilo e exige uma nova prévia.
- A API só pode publicar com estilo aprovado, retrato aprovado, pacote íntegro,
  fonte ainda não publicada, credenciais rotacionadas e flags habilitadas.

## Proibições

- Não misturar frase de um autor com nome, obra ou retrato de outro.
- Não inventar tradução, referência, contexto ou página.
- Não retirar a logo nem substituir os templates fornecidos.
- Não automatizar seguidores, curtidas, comentários ou mensagens.
