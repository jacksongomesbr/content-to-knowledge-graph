# Conteúdo para grafo de conhecimento

Skill para agentes que transforma livros, documentos, pastas e skills de conteúdo em uma base de conhecimento **Markdown com frontmatter**. Inclui fontes rastreáveis, índice SQLite/FTS5, embeddings locais, enriquecimento com Wikipédia e um visualizador 3D no navegador.

```text
Markdown canônico → validação/indexação → SQLite + embeddings
                                      → graph.json + layout → navegador
```

Edite os Markdown; reconstrua os derivados. O JSON preserva a compatibilidade com o visualizador [grafo-do-livro](https://github.com/jacksongomesbr/uft-cc-dwm), mas deixa de ser a fonte principal. IDs são independentes dos nomes dos arquivos.

## Instalar e usar com agentes

A pasta segue o formato aberto Agent Skills. Clone ou copie a skill completa para uma raiz de skills configurada no seu host:

```sh
git clone https://github.com/jacksongomesbr/content-to-knowledge-graph.git /caminho/de/skills/content-to-knowledge-graph
```

O diretório e a descoberta automática dependem do host; não há um caminho universal. Para instalações por clone, use pull --ff-only preservando alterações locais. Hosts sem descoberta de skills podem receber SKILL.md explicitamente. agents/openai.yaml é apenas um adaptador opcional de interface.

```text
Use a skill content-to-knowledge-graph.
Origem: /caminho/do/conteudo
Destino: /caminho/da/base
```

O agente inventaria o corpus, escreve os registros, indexa, consulta a Wikipédia, gera embeddings e abre o visualizador quando houver interface. Veja [compatibilidade](references/agent-compatibility.md), [llms.txt](llms.txt) e [protocolo para automação](references/cli-protocol.md).

## Experimentar o exemplo

Python 3.11/3.12 com SQLite/FTS5 e PyYAML basta para base, índice e navegador. Use um venv:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r references/requirements-core.txt
.venv/bin/python scripts/knowledge.py build examples
.venv/bin/python scripts/knowledge.py search examples "World Wide Web" --kind entity
.venv/bin/python scripts/knowledge.py neighbors examples web --direction out
.venv/bin/python scripts/start_viewer.py examples
```

O servidor compila a base e abre localhost numa porta livre. Ctrl+C encerra. Use --no-open para apenas imprimir a URL. O bundle vem pronto; Node não é necessário para servir. Fontes Markdown, corpus, índice e vetores não são publicados pelo servidor.

## Estrutura da base

```text
projeto/
  knowledge/
    knowledge.yml
    entities/*.md
    relations/*.md
    sources/*.md
    bibliography/*.md
  .generated/               # reconstruível; não versionar
    index.sqlite
    graph.json
    layout.json
    provenance.json
    manifest.json
    INDEX.md
    llms.txt
    index/*.md
    evidence/passages.json  # localizadores; sem texto no modo referenciado
    evidence/*.html
    embeddings/
```

Frontmatter guarda IDs, tipos, aliases, fontes, qualificadores e Wikipédia. O corpo guarda explicações ou evidências. Relações são registros explícitos com origem/destino, predicado e fontes; links no texto não viram arestas automaticamente. Veja o [contrato Markdown](references/knowledge-format.md).

## Migrar JSON existente

```sh
.venv/bin/python scripts/knowledge.py import-json /origem/graph.json --output /destino/knowledge
.venv/bin/python scripts/knowledge.py build /destino
```

O JSON em examples/graph.json é uma fixture legada para migração. A migração exige destino novo, preserva o JSON original e mantém IDs, explicações e referências. Relações sem classificação anterior recebem basis: unspecified. A partir daí, edite somente os documentos. Os scripts ainda aceitam JSON legado para interoperabilidade; não há sincronização bidirecional.

## Análise e embeddings

```sh
python3.12 scripts/prepare_environment.py --venv .venv
.venv/bin/python scripts/generate_embeddings.py --graph /destino \
  --model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
  --output /destino/.generated/embeddings
.venv/bin/python scripts/search_knowledge.py /destino "infraestrutura de comunicação" --mode hybrid
```

O perfil completo instala leitores de documentos, NumPy, NetworkX, Sentence Transformers/PyTorch e ferramentas de análise num ambiente isolado. O primeiro uso do modelo pode baixar pesos públicos; a inferência é local. Há também um lock testado para macOS arm64/Python 3.12.

O cache de entidades é incremental: um texto/alias alterado recalcula somente seu vetor. Trocar Wikipédia, datas ou nome do arquivo mantém os vetores; mudar modelo/revisão/parâmetros invalida o cache correspondente. Hashes, revisão, dimensão, normalização e contadores ficam no manifesto. Chunks do corpus ainda são recompostos por completo.

Busca lexical usa FTS5/BM25; a semântica usa cosseno; a híbrida combina rankings por RRF. São ferramentas de recuperação, não prova de identidade ou relação. Consultas recusam índices/vetores desatualizados. A posição editorial no visualizador não representa a distância dos embeddings.

## Wikipédia por padrão

Em toda criação/atualização, o agente executa discover, revisa o sentido dos candidatos e aplica as decisões na base. Prefere português e usa inglês quando necessário. O script revalida página, revisão, URL e desambiguação antes de atualizar os frontmatters. Entidades sem correspondência segura ficam sem link, com motivo registrado.

Somente rótulos são enviados nas consultas, sem corpus nem embeddings. A leitura complementar não altera as definições ou evidências do material. Restrições explícitas de rede prevalecem; falhas são declaradas como cobertura parcial. Veja o [fluxo completo](references/wikipedia.md).

## Descoberta e consumo por agentes

SKILL.md ensina a tarefa; AGENTS.md orienta manutenção do repositório; llms.txt aponta a documentação. Toda base compilada recebe INDEX.md e catálogos de até 100 registros por página. Use busca e leitura seletiva em vez de carregar todo o corpus. llms.txt não garante descoberta automática e não substitui o SQLite.

Todos os comandos operacionais aceitam --json: envelope comum em stdout, logs em stderr e códigos distintos para erro/uso/cobertura parcial. O servidor emite eventos ready/stopped em JSONL. Veja [o protocolo](references/cli-protocol.md).

## Scripts e documentação

| Script | Função |
|---|---|
| `validate_skill.py` | Validar o contrato Agent Skills, incluindo compatibility |
| `prepare_environment.py` | Preparar ambiente e testar imports |
| `extract_corpus.py` | Extrair texto de documentos |
| `knowledge.py` | Migrar, validar, indexar, buscar, percorrer e recuperar uma base |
| `search_knowledge.py` | Busca lexical, semântica e híbrida |
| `validate_graph.py` | Validar base ou exportação e layout |
| `analyze_graph.py` | Métricas e candidatos por similaridade |
| `generate_embeddings.py` | Inferência local com cache de entidades |
| `enrich_wikipedia.py` | Descoberta e aplicação de links revisados |
| `start_viewer.py` | Compilar/servir a base ou abrir JSON legado |

Leia [SKILL.md](SKILL.md), [comandos](references/running.md), [Markdown/indexação](references/knowledge-format.md), [exportação JSON](references/graph-contract.md) e [ambiente ML](references/python-and-embeddings.md).

## Desenvolvimento

```sh
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py'
.venv/bin/python -m compileall -q scripts
npm ci --ignore-scripts --prefix assets/viewer
npm test --prefix assets/viewer
npm run build --prefix assets/viewer
```

Node 22.12+ compatível com Vite 7 é necessário somente para recompilar o app. Versione os Markdown e as fontes do app; não versione .generated, modelos, caches, corpus pessoais, tokens, venvs ou node_modules. O bundle do visualizador é distribuído versionado para permitir uso sem build.

O CI executa testes offline, constrói o índice do exemplo e compila o visualizador. Inferência real e rede são testadas separadamente para não depender de downloads e serviços externos a cada commit.

## Licença e créditos

Projeto sob [CC BY-SA 4.0](LICENSE.md). O visualizador deriva de **grafo-do-livro**, de **Jackson Gomes**, no projeto uft-cc-dwm; adaptações estão registradas em [ATTRIBUTION.md](assets/viewer/ATTRIBUTION.md). Dependências conservam suas próprias licenças, incluídas no pacote.

## Referências sem duplicação da origem

Novas bases usam content_mode: reference: guardam caminho, SHA-256 e localizadores. A modal recupera o parágrafo ao ser aberta; se a fonte mudou ou não está acessível, informa o limite. A saída padrão não mantém corpus integral. Cópias autossuficientes só são geradas mediante pedido de exportação portátil. Veja o [contrato de evidências](references/knowledge-format.md).
