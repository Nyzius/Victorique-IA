# Assistente Virtual Pessoal (Windows, local)

Aplicativo desktop Windows com chat via Ollama, personalidade configurável, histórico,
memórias explícitas, projetos independentes, RAG de documentos locais com referências,
ferramentas limitadas com autorização no backend e interface própria. Funciona offline
depois da instalação. **Não inclui voz nesta versão.**

> Situação verificada em 18/11/2026 nesta máquina: Windows 11, Python 3.15.1,
> Ollama 0.40.16, GTX 1660 Super 6 GB, 16 GB RAM. Modelo padrão:
> `qwen2.5-coder:7b` (instalado). Embeddings: `nomic-embed-text`.
> OCR local via Tesseract 5.4.0 (idioma `eng`; `por` não foi baixado).

---

## 1. Como iniciar

Formas suportadas:

```bat
run.bat
```

ou

```bat
.venv\Scripts\python.exe run.py
```

Variações úteis:

```bat
.venv\Scripts\python.exe run.py --browser   :: abre no navegador padrão
.venv\Scripts\python.exe run.py --server    :: só o servidor (sem janela), para testes
.venv\Scripts\python.exe run.py --no-ollama :: não tenta iniciar o Ollama
```

A janela nativa usa **pywebview/WebView2**. Se a janela falhar, o `run.py` cai para o
navegador padrão. O backend escuta apenas em `127.0.0.1:8765` (ou `ASSISTANT_PORT`).

### Pré-requisitos já presentes

- `.venv` com Python 3.15.1;
- Ollama ativo em `127.0.0.1:11434`;
- modelos `qwen2.5-coder:7b` e `nomic-embed-text`;
- **Tesseract-OCR** em `C:\Program Files\Tesseract-OCR` (opcional: sem ele o app continua
  funcionando, mas PDFs digitalizados sem camada de texto são recusados com aviso claro).

Se precisar recriar o ambiente em outra máquina:

```bat
py -3.15 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
winget install --id UB-Mannheim.TesseractOCR   :: opcional, para OCR
```

Nada é baixado automaticamente pelo aplicativo. O `run.py` apenas inicia o processo
local do Ollama quando ele já está instalado.

---

## 2. Modelo e desempenho medidos

| Modelo | Contexto | Processamento | Velocidade medida | Observação |
|---|---:|---|---:|---|
| `qwen2.5-coder:7b` (padrão) | 4096 | 84% GPU / 16% CPU | ~16–19 tok/s | 5,2 GB; parte em CPU por causa dos 6 GB de VRAM |
| `qwen2.5:3b` | 4096 | 100% GPU | ~87 tok/s | alternativa mais rápida |

Medições reais nesta máquina:

- chat curto com `qwen2.5-coder:7b`: primeiro token entre **3,3 s e 8,6 s** (carregamento a frio),
  resposta de 41 caracteres em ~4 s;
- 1.107 tokens gerados em **79 s** (frio) a ~16 tok/s;
- RAG com 2 fontes: ~7,8 s no total;
- o relato de **167 s** não se reproduziu com o modelo padrão. Ele é compatível com
  respostas muito longas, carregamento a frio ou uso de modelo maior. Para limitar
  respostas descontroladas, `ASSISTANT_MAX_OUTPUT_TOKENS` (padrão 1024) é enviado como
  `num_predict`.

Para trocar de modelo: **Configurações → Modelo de Linguagem** (a escolha é persistida no
banco) ou `ASSISTANT_MODEL`. O modelo `qwen2.5:7b` **não está instalado** nesta máquina;
não foi baixado automaticamente.

Tool calling real medido nesta máquina: `qwen2.5-coder:7b` devolve a chamada como **JSON em
texto** (`{"name": ..., "arguments": ...}`), que o backend interpreta e valida;
`qwen2.5:3b` usa o campo nativo `tool_calls`. Se um modelo não suportar ferramentas, o app
avisa e continua a conversa sem execução automática.

---

## 3. Privacidade e funcionamento offline

- Interface sem CDN: CSS, JS, ícone e renderizador Markdown são locais.
- Nenhuma fonte, imagem ou script externo é carregado.
- Ollama e embeddings são acessados somente em `127.0.0.1`.
- A única função que acessa a internet é `search_web`, e ela **só executa após
  autorização explícita** do usuário, com o pedido mostrando a consulta e o alvo.
- O backend aplica `Content-Security-Policy` com `connect-src 'self'` e `script-src 'self'`,
  bloqueando exfiltração por scripts injetados.
- Nenhum dado pessoal é salvo automaticamente. Memórias só existem quando o usuário
  cria/edita; conversas são salvas localmente por necessidade do histórico.
- A interface não envia telemetria.
- **OCR local**: PDFs sem camada de texto são renderizados com `pypdfium2` e lidos pelo
  Tesseract na própria máquina; nenhuma página é enviada para fora.
- **Tool calling**: o modelo pode pedir ferramentas; só as ferramentas livres rodam
  automaticamente. Escrita, exclusão, criação de pastas e internet sempre param num pedido
  de autorização no backend. Cada rodada é limitada (3 rodadas / 3 chamadas por padrão).
- **Isolamento por projeto**: conversas, memórias e documentos são filtrados pelo projeto
  ativo. Um chat sem projeto usa apenas documentos globais — nunca recupera conteúdo de
  outro projeto (verificado por teste automatizado e no E2E).

---

## 4. Onde ficam os dados

Tudo por padrão em `data/`:

| Caminho | Conteúdo |
|---|---|
| `data/assistant.db` | histórico, memórias, projetos, personalidades, índice RAG, auditoria |
| `data/documents/` | cópias dos documentos importados |
| `data/backups/` | snapshots do banco |

Variáveis de ambiente para instalação portátil/testes:

- `ASSISTANT_DATA_DIR` — diretório de dados;
- `ASSISTANT_DB_PATH` — caminho do banco;
- `ASSISTANT_PORT` — porta;
- `ASSISTANT_MODEL` — modelo padrão;
- `ASSISTANT_EMBEDDING_MODEL` — modelo de embeddings;
- `ASSISTANT_NUM_CTX` — contexto do Ollama;
- `ASSISTANT_MAX_OUTPUT_TOKENS` — limite de tokens por resposta;
- `ASSISTANT_AUTHORIZED_DIRS` — diretórios autorizados, separados por `;`;
- `ASSISTANT_TOOL_CALLING` — `0` desativa tool calling;
- `ASSISTANT_MAX_TOOL_ROUNDS` / `ASSISTANT_MAX_TOOL_CALLS` — limites do laço de ferramentas;
- `ASSISTANT_OCR` — `0` desativa o OCR;
- `ASSISTANT_OCR_LANG` — idiomas do Tesseract (ex.: `por+eng`; só funciona se os dados
  de idioma estiverem instalados);
- `ASSISTANT_OCR_DPI` / `ASSISTANT_OCR_MIN_CHARS` — renderização e limiar de texto;
- `TESSERACT_CMD` — caminho alternativo para `tesseract.exe`.

**Nunca apague `data/assistant.db` sem backup.** Faça backup antes de qualquer
manutenção.

---

## 5. Backup e restauração

Pela interface: **Configurações → Backup do banco de dados → Criar backup agora**.
Também é possível baixar e restaurar pela própria tela.

Pela API:

```bat
curl -X POST http://127.0.0.1:8765/api/backup -H "Content-Type: application/json" -d "{\"label\":\"manual\"}"
curl http://127.0.0.1:8765/api/backups
curl -X POST http://127.0.0.1:8765/api/backup/restore -H "Content-Type: application/json" -d "{\"name\":\"assistant-....db\",\"confirm\":true}"
```

- O backup usa a API online do SQLite e é verificado com `PRAGMA integrity_check`.
- A restauração exige `confirm=true` e cria automaticamente um backup `pre-restore`.
- A fila de autorizações pendentes é limpa após restaurar.
- Backups não são apagados automaticamente (política conservadora).

---

## 6. Segurança e autorizações

### Camadas implementadas

- **Backend decide**: `POST /api/tools/execute` ignora o campo `authorized` enviado pelo
  cliente. Ferramentas protegidas sempre geram um pedido pendente.
- **Vínculo à ação e aos parâmetros**: o pedido guarda ferramenta, alvo e hash do payload.
  A aprovação executa exatamente o payload armazenado no servidor.
- **Uso único e expiração**: cada `action_id` vale uma vez, por 120 s (configurável por
  `authorization_ttl_seconds`). Reutilização, expiração e adulteração são recusadas.
- **Auditoria**: pedidos, aprovações, recusas, expirações e execuções vão para
  `audit_logs` no SQLite.
- **Caminhos**: validação imediata antes da operação, com `resolve()` para seguir
  symlinks/junctions; bloqueio de `..`, caminhos absolutos/UNC fora da whitelist.
- **Caminhos protegidos**: código do app, `.venv`, banco, `data/` e backups não podem
  ser escritos/apagados por ferramentas. Exclusão recursiva exige `recursive: true` e
  autorização específica.
- **Origem/Host**: requisições com `Origin` externo recebem 403; `Host` diferente de
  localhost/127.0.0.1 recebe 400 (mitiga DNS rebinding).
- **Conteúdo não confiável**: documentos/páginas são tratados como dados; o prompt
  instrui o modelo a ignorar comandos embutidos. O Markdown do modelo é escapado antes
  de renderizar (sem HTML arbitrário).
- **Tool calling não amplia permissões**: o modelo só escolhe *qual* ferramenta chamar.
  O backend valida nome, parâmetros obrigatórios, caminhos e categoria; ferramentas
  protegidas continuam criando pedido pendente, e a aprovação executa apenas o payload
  guardado no servidor. Chamadas repetidas idênticas na mesma rodada são ignoradas.

### Limitações de segurança (honestas)

- A API local **não tem login/token**. Qualquer processo do próprio usuário pode chamá-la.
  A proteção é contra páginas web (Origin/Host/CSP), não contra malware local.
- Subprocessos não são usados para executar comandos do modelo. Ainda assim, o app roda
  com os privilégios do usuário; não é um sandbox de sistema operacional.
- A validação de caminho tem uma janela teórica de TOCTOU entre validação e operação;
  symlinks/junctions são resolvidos imediatamente antes, o que reduz o risco.
- A extração de PDF usa a camada de texto quando existe. OCR entra apenas em páginas com
  pouco texto; a qualidade depende da digitalização. Nesta máquina só o idioma `eng` do
  Tesseract está instalado — documentos em português podem ter erros de reconhecimento até
  que `por.traineddata` seja adicionado (não baixado automaticamente).
- Tool calling depende do modelo: o padrão emite JSON textual, interpretado por um parser
  restrito (só nomes registrados e chaves conhecidas). Modelos pequenos podem ocasionalmente
  responder em prosa em vez de chamar a ferramenta; nesse caso nada é executado.
- RAG usa similaridade de cosseno local; não há garantia de que toda resposta esteja
  fundamentada. A UI mostra as fontes e o system prompt proíbe inventar citações, mas
  isso não é uma verificação formal.

---

## 7. Funcionalidades

| Funcionalidade | Estado |
|---|---|
| Chat local com streaming SSE | implementado; testado automaticamente e manualmente (real) |
| Cancelamento de geração | implementado (AbortController + fechamento do stream Ollama + resposta parcial salva); testado |
| Personalidade configurável | implementado; testado (edição sem duplicar perfil) |
| Histórico e persistência | implementado; testado após reinício |
| Memórias explícitas (global/projeto), editar/desativar/excluir | implementado; testado |
| Projetos independentes + exclusão em cascata | implementado; testado (inclui remoção do arquivo) |
| RAG PDF/TXT/MD com documento/página | implementado; testado com embeddings reais |
| Isolamento por projeto (conversas, memórias, documentos, RAG) | implementado; testado automaticamente e no E2E |
| Referências às fontes | implementado; testado |
| Ferramentas de arquivos, cálculo e sistema | implementado; testado |
| Tool-calling autônomo pelo modelo (ferramentas livres) | implementado; testado automaticamente (parser JSON, `tool_calls` nativo, limite de rodadas, fallback) e no E2E real com `qwen2.5-coder:7b` e `qwen2.5:3b` |
| Autorizações no backend | implementado; testado (aprovar/recusar/expirar/replay) |
| Internet somente com autorização | implementado; testado que não há chamada antes da aprovação |
| OCR de PDF digitalizado no upload/RAG | implementado; testado automaticamente (PDF só-imagem) e no E2E com citação de página; limitado aos idiomas instalados no Tesseract |
| Interface desktop própria | implementado (WebView2); página e handlers verificados; janela nativa não automatizada |
| Backup/restauração | implementado; testado |
| Voz | **não implementada nesta versão** |

---

## 8. API principal

- `GET /api/health`, `GET /api/models`, `GET/POST /api/settings`
- `POST /api/chat` (SSE: `meta`, `sources`, `token`, `tool_call`, `tool_result`,
  `authorization_required`, `notice`, `error`, `done`)
- `GET/POST /api/conversations`, `GET /api/conversations/search`,
  `GET /api/conversations/{id}/messages`, `PUT/DELETE`, `GET .../export`
- `GET/POST /api/personalities`, `DELETE /api/personalities/{id}`
- `GET/POST /api/memories`, `PUT/DELETE /api/memories/{id}`
- `GET/POST /api/projects`, `PUT/DELETE /api/projects/{id}`
- `GET /api/documents`, `POST /api/documents/upload`, `DELETE /api/documents/{id}`
- `GET /api/security/pending`, `POST /api/security/authorize`
- `POST /api/tools/execute`, `GET /api/tools/list`
- `POST /api/backup`, `GET /api/backups`, `GET /api/backups/{name}`,
  `POST /api/backup/restore`

O evento SSE `meta` chega antes dos tokens e já contém `conversation_id`; o evento
`done` também o envia. Assim, uma conversa nova não se perde se a geração for cancelada.

---

## 9. Testes

```bat
.venv\Scripts\python.exe -m pytest -q
```

- Os testes usam um diretório temporário (`ASSISTANT_DATA_DIR`) e **não tocam** em
  `data/assistant.db`.
- Cobertura atual: banco/memória/projetos, personalidade, path guard (incluindo junction),
  autorizações (cliente não executa, replay, expiração, recusa), caminhos protegidos,
  Origin/Host, ausência de rede antes da aprovação, upload/RAG, SSE, cancelamento,
  backup/restauração, isolamento por projeto, handlers e recursos offline da UI,
  tool calling (JSON textual, `tool_calls` nativo, ferramenta protegida pendente,
  limite de rodadas, fallback sem suporte) e OCR de PDF só-imagem.
- Resultado desta rodada: **54 testes passaram** (inclui geração real e verificação
  comportamental do Markdown/XSS executada no Node, ignorada se o Node não existir).
- E2E via `run.py --server` com banco temporário: **12/12** verificações na primeira fase,
  **todas** as da segunda fase (reinício, autorização, RAG, isolamento global × projeto,
  backup, exclusão em cascata, UI offline) e **todas** as da fase C (tool call livre real,
  autorização de escrita real, payload único, `tool_calls` nativo, OCR + RAG com citação).
- O banco real `data/assistant.db` foi comparado com o backup pré-auditoria: schema e
  todas as linhas **logicamente idênticos** (0 conversas/mensagens/memórias/projetos/
  documentos; apenas a personalidade padrão). Nenhum dado do usuário foi alterado.
- A janela nativa WebView2 e os cliques da interface foram verificados por carregamento
  headless do DOM e checagem de handlers; **não** houve automação de cliques na janela.

---

## 10. Estrutura

```
run.py, run.bat
app/
  config.py, main.py
  core/       assistant.py, context_builder.py, personality.py, backup.py
  models/     ollama_client.py
  memory/     database.py, conversation_store.py, memory_store.py, project_store.py
  rag/        document_loader.py, text_splitter.py, vector_store.py
  security/   path_guard.py, permissions.py
  tools/      registry.py, file_tools.py, system_tools.py, web_search.py
  ui/         index.html, css/style.css, js/app.js, js/markdown.js, favicon.svg
tests/
data/         assistant.db, documents/, backups/  (não versionar)
```

---

## 11. Observações de manutenção

- `python-multipart` é obrigatório para o upload multipart do FastAPI. Ele estava ausente
  e impedia o app de iniciar; foi instalado no `.venv` e adicionado ao `requirements.txt`.
- OCR usa `pypdfium2` + `pytesseract` + `Pillow` (licenças permissivas) e o Tesseract
  instalado em `C:\Program Files\Tesseract-OCR`; **não** foi usado PyMuPDF (AGPL).
- Git 2.56 foi instalado e o repositório local foi inicializado (commit inicial
  `000b195`). Não há remoto configurado; `.venv`, `data/` e caches ficam fora do controle
  de versão.
- O console do Windows pode exibir acentos quebrados dependendo da fonte/codepage; o
  `run.bat` ativa UTF-8 e o `run.py` reconfigura os streams.
- Antes de atualizar Ollama, modelos, Python ou dependências, faça backup e teste
  compatibilidade. Não há migração destrutiva automática.
