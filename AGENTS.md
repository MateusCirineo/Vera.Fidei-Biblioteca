# Instruções permanentes do Vera.Fidei

Estas regras se aplicam a qualquer agente Codex trabalhando neste repositório.

## Instagram

Antes de criar, alterar, aprovar ou publicar qualquer conteúdo do Instagram,
leia primeiro e integralmente `INSTAGRAM_STYLE.md` e, para a operação técnica,
`vera_fidei_starter/docs/instagram-automation.md`.

`INSTAGRAM_STYLE.md` vale para todas as publicações. Os posts de Santo
Agostinho e Santo Ambrósio são referências visuais, não conteúdos fixos.

O padrão visual homologado é um contrato, não uma sugestão. Nunca recrie a
arte livremente, troque fontes, ajuste cores, escolha outro tamanho ou publique
um retrato encontrado automaticamente. Use exclusivamente o pipeline em
`vera_fidei_starter/backend/app/social/` e os agentes registrados pelo
`orchestrator.py`.

Regras incontornáveis:

- Capa, página de citação e capa final: exatamente três imagens de 1856 x 2304.
- Capa baseada no modelo de Santo Ambrósio; página central usa o pergaminho com
  logo; capa final usa a moldura e composição final fornecidas.
- Corpo em Arial Rounded MT Bold (`ARLRDBD.TTF`) e palavras-chave em
  RGB `(102, 29, 20)`.
- Autor, obra, citação, tradução, edição, página e recorte do PDF devem provir
  do mesmo `chunk_id`/arquivo. Nunca preencher metadados manualmente.
- Retratos precisam estar aprovados no manifesto. Resultado de busca serve só
  para prévia e não pode ser publicado.
- Toda execução gera prévia primeiro. A API real só pode rodar com estilo
  homologado, retrato aprovado, credenciais rotacionadas e flags habilitadas.
- Mudança de código visual, fonte ou asset invalida a aprovação. Não contorne
  os hashes, o ledger, a deduplicação ou as travas de publicação.
- Nunca automatize seguidores, curtidas, comentários ou mensagens.

Se o pedido do usuário conflitar com o contrato, pare antes de publicar e mostre
uma nova prévia para aprovação explícita.
