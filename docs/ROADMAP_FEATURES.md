# Roadmap de Features — Vera.Fidei Biblioteca

Funcionalidades planejadas para implementação nas próximas versões do app.
Estas features sustentam o modelo de assinatura e ampliam o valor da plataforma
para pesquisadores e instituições.

---

## 1. Exportação de Laudos (PDF)

### O que é
Permitir que o usuário baixe o laudo completo gerado pelo verificador de citações
em formato PDF, pronto para anexar em trabalhos, artigos, seminários ou documentos oficiais.

### O que o laudo conterá
- Citação analisada e autor atribuído
- Obra e edição localizada
- Trecho encontrado com referência exata (volume, página, coluna)
- Relatório de idioma, tradução e contexto
- Veredito final com nível de confiança
- Data e hora da verificação
- Rodapé com marca Vera.Fidei e link para a plataforma

### Como implementar
- **Backend:** Usar biblioteca `reportlab` ou `weasyprint` para geração de PDF a partir
  do JSON de resposta do pipeline de verificação.
- **Endpoint:** `POST /verificador/exportar-laudo/{verificacao_id}` → retorna PDF como stream.
- **Frontend:** Botão "Exportar Laudo" visível após resultado da verificação,
  disponível apenas para planos Catequista ou superior.
- **Armazenamento:** Laudos podem ser gerados sob demanda (sem armazenar) ou
  salvos temporariamente em S3/R2 com TTL de 24h.

### Dependências
- Sistema de autenticação e planos (necessário para restringir por plano)
- Histórico de verificações (para recuperar resultado por ID)

---

## 2. Histórico de Verificações

### O que é
Guardar um registro de todas as citações verificadas pelo usuário, com resultado,
data e referência — acessível a qualquer momento na conta do usuário.

### Como implementar
- **Banco de dados:** Criar tabela `verification_history` em PostgreSQL:
  ```sql
  CREATE TABLE verification_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    citation_text TEXT NOT NULL,
    author_attributed VARCHAR(255),
    verdict VARCHAR(50),
    confidence_score FLOAT,
    source_reference TEXT,
    created_at TIMESTAMP DEFAULT NOW()
  );
  ```
- **Backend:** Salvar resultado automaticamente após cada verificação bem-sucedida.
- **Endpoint:** `GET /usuario/historico` → lista paginada de verificações do usuário.
- **Frontend:** Página "Meu Histórico" no painel do usuário, com filtros por data e veredito.

### Dependências
- Sistema de autenticação (login/cadastro de usuários)

---

## 3. Painel de Gestão Institucional

### O que é
Área administrativa para instituições (seminários, faculdades, editoras) que assinam
o plano Patrístico — permite visualizar o uso da plataforma por todos os membros vinculados.

### Funcionalidades do painel
- Listagem de usuários vinculados à instituição
- Total de verificações realizadas por período
- Citações mais verificadas
- Relatório de vereditos (quantas confirmadas, inconclusivas etc.)
- Exportação de relatório geral em CSV ou PDF

### Como implementar
- **Modelo de dados:** Criar entidades `Institution` e `InstitutionMember` no banco.
- **Roles:** Adicionar campo `role` nos usuários: `admin_institucional`, `membro`, `usuario_comum`.
- **Backend:** Endpoints protegidos por role:
  - `GET /instituicao/membros`
  - `GET /instituicao/relatorio?inicio=&fim=`
  - `POST /instituicao/convidar-membro`
- **Frontend:** Rota `/admin/instituicao` com dashboard de métricas (usar biblioteca de gráficos,
  ex: Recharts ou Chart.js no Next.js).

### Dependências
- Sistema de autenticação com roles
- Histórico de verificações

---

## 4. Integração via API (Plano Magistério)

### O que é
Permitir que instituições integrem o verificador de citações do Vera.Fidei diretamente
em seus próprios sistemas — sites, plataformas de ensino, portais teológicos — via API REST
autenticada com chave de acesso.

### Como implementar
- **Autenticação:** Gerar API Keys únicas por instituição (`api_keys` table com hash, rate limit e status).
- **Endpoints públicos da API:**
  ```
  POST /api/v1/verificar
    Body: { "citacao": "...", "autor": "..." }
    Headers: { "X-API-Key": "..." }
    Returns: JSON com veredito completo

  GET /api/v1/status
    Retorna status da conta, verificações usadas no mês, limite do plano
  ```
- **Rate limiting:** Middleware de controle de uso por API Key (ex: `slowapi` no FastAPI).
- **Documentação:** Gerar docs automáticos via Swagger/OpenAPI (já disponível no FastAPI em `/docs`).
- **Dashboard da chave:** Interface no painel do usuário para gerar, revogar e monitorar uso da API Key.

### Precificação
Por ser um recurso de integração técnica (desenvolvimento), o plano Magistério terá
valor diferenciado — estimado em **R$ 99,99/mês**.

### Dependências
- Sistema de autenticação
- Painel de gestão (para monitorar uso)
- Rate limiting configurado no backend

---

## Ordem sugerida de implementação

1. **Sistema de autenticação** (base para tudo — login, cadastro, planos)
2. **Histórico de verificações** (necessário para exportação e painel)
3. **Exportação de laudos** (feature de alto valor, rápida de implementar após auth)
4. **Painel de gestão institucional** (para plano Patrístico)
5. **API com chave de acesso** (para plano Magistério)
