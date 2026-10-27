# Comandos da base Markdown

Resolva SKILL_DIR como a pasta da skill e PYTHON como o executável do ambiente escolhido. No Windows, o Python de venv fica em Scripts/python.exe. Os caminhos abaixo são exemplos, substitua-os pelo destino real.

Para integração programática, use --json conforme cli-protocol.md. Sem browser no host, inicie com --no-open --json e capture o evento ready. Instalação e caminhos de skills estão em agent-compatibility.md.

## Ambiente

```sh
python3.12 "$SKILL_DIR/scripts/prepare_environment.py" --venv "/destino/.venv"
"/destino/.venv/bin/python" "$SKILL_DIR/scripts/prepare_environment.py" --check
```

O perfil completo inclui leitores de documentos, análise e ML. Para usar apenas Markdown, índice e visualizador, prepare o venv com `--profile core`. PyYAML e SQLite/FTS5 são suficientes para esse perfil; use `--check --profile core` para verificar apenas o perfil leve, incluindo uma criação real de tabela FTS5 em memória. Sem --profile, o perfil de análise é usado.

O preparo verifica imports reais e grava requirements-analysis.lock.txt. Há um lock testado para macOS arm64/Python 3.12 em references/requirements-macos-arm64-python312.lock.txt, selecionável com --requirements. Não use esse lock como garantia para outra plataforma. Não altere o Python global.

## Extração textual e autoria

```sh
"$PYTHON" "$SKILL_DIR/scripts/extract_corpus.py" "/origem/livro" --output "/temporario/extracao"
```

Extrai TXT, Markdown, Quarto, HTML, PDF textual, DOCX e EPUB em unidades JSONL com localizadores/hashes e cobertura. O script não faz extração semântica de entidades, OCR ou transcrição. Unidade sem texto é parcial; erros de formato são registrados. Exige pasta nova/vazia, preserva a origem e exclui a própria saída da coleta.

O agente lê essas unidades e escreve os registros em `/destino/knowledge/` conforme knowledge-format.md. Remova os intermediários ao concluir a análise; entregue cobertura e localizadores sem cópia do corpus. O extrator escreve unidades em fluxo, sem acumular o corpus inteiro em memória. As unidades JSONL são material de trabalho; a base canônica de conhecimento é Markdown. Mantenha cobertura semântica separada da simples leitura por máquina.

## Migrar um grafo existente

```sh
"$PYTHON" "$SKILL_DIR/scripts/knowledge.py" import-json "/origem/graph.json" --output "/destino/knowledge"
```

Exige pasta nova e preserva o original. Após a migração, edite apenas os Markdown. Relações sem classificação anterior recebem basis: unspecified para não atribuir certeza sem evidência. A migração não relê o corpus nem incorpora automaticamente o texto das fontes.

## Validar, indexar e consultar

```sh
"$PYTHON" "$SKILL_DIR/scripts/knowledge.py" validate "/destino"
"$PYTHON" "$SKILL_DIR/scripts/knowledge.py" build "/destino"
"$PYTHON" "$SKILL_DIR/scripts/knowledge.py" search "/destino" "contrato API" --kind entity
"$PYTHON" "$SKILL_DIR/scripts/knowledge.py" neighbors "/destino" "web" --depth 2 --direction out
```

O build atualiza `.generated/index.sqlite` e exporta graph.json, layout.json, provenance.json, manifest.json, INDEX.md, llms.txt, catálogos paginados e páginas locais de evidências. IDs não dependem do nome do arquivo. As estatísticas changed/unchanged/removed contam documentos; ftsUpdated conta textos modificados no FTS. Projeções relacionais são reconstruídas transacionalmente; documentos inalterados reutilizam o parse e não reindexam o texto.

A busca por texto usa termos, aliases e corpo com BM25. A consulta de vizinhos usa relações explícitas e direção, com profundidade entre 1 e 10. As consultas recusam índice desatualizado; execute build após edição. Não edite o SQLite nem os JSONs gerados.

## Wikipédia obrigatória por padrão

Execute discover sobre a base, revise candidatos pelo sentido, grave uma decisão por nó e aplique sem --output:

```sh
"$PYTHON" "$SKILL_DIR/scripts/enrich_wikipedia.py" discover "/destino" --report "/destino/.generated/wiki-candidates.json"
"$PYTHON" "$SKILL_DIR/scripts/enrich_wikipedia.py" apply "/destino" --report "/destino/.generated/wiki-candidates.json" --decisions "/destino/.generated/wiki-decisions.json" --audit "/destino/.generated/wiki-audit.json"
```

Consulte wikipedia.md. O apply revalida artigos, atualiza frontmatters e reconstrói a exportação. Um journal permite recuperar interrupções com `knowledge.py recover /destino`; edições externas divergentes são protegidas. Após cada nova descoberta, use arquivos de relatório/auditoria novos. Uma edição na base entre descoberta e aplicação exige refazer a revisão.

## Embeddings e análise

```sh
"$PYTHON" "$SKILL_DIR/scripts/generate_embeddings.py" --graph "/destino" --model "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" --output "/destino/.generated/embeddings"
"$PYTHON" "$SKILL_DIR/scripts/analyze_graph.py" "/destino" --embeddings "/destino/.generated/embeddings" --output "/destino/.generated/analysis.json"
```

O primeiro uso pode baixar pesos públicos. Prefira --revision com o commit do modelo. Opções: --batch-size, --device cpu, --cache-dir, --local-only, --overlap-tokens. Para chunks do corpus, use --units /temporario/extracao/units.jsonl e outra pasta de saída.

A pasta gerenciada de embeddings v2 pode ser reutilizada: vetores de entidades são reaproveitados por ID e hash semântico, modelo/revisão, versões das bibliotecas e parâmetros. Alterar só Wikipédia ou renomear documento não gera nova inferência; mudar o texto ou um alias recalcula a entidade alterada. Remoções eliminam linhas da matriz. Não reutilize uma pasta antiga sem marcador v2 ou misture chunks e entidades. Chunks são recompostos por completo, sem cache incremental de inferência.

Vetores não entram no frontmatter nem no JSON do visualizador. O manifesto registra hashes do arquivo e do texto semântico, dimensão, normalização, revisão e contadores reused/computed. Tokens/offsets preservam a cobertura de textos longos. O cache dos pesos continua separado do cache dos vetores. O script pode carregar o modelo para verificar sua revisão mesmo quando todos os vetores forem reutilizados.

## Busca semântica e híbrida

```sh
"$PYTHON" "$SKILL_DIR/scripts/search_knowledge.py" "/destino" "infraestrutura para comunicação" --mode semantic
"$PYTHON" "$SKILL_DIR/scripts/search_knowledge.py" "/destino" "infraestrutura para comunicação" --mode hybrid
```

A busca semântica usa o mesmo modelo/revisão, encode simétrico e normalização da matriz. Exige embeddings válidos e índice atual. Por padrão usa apenas pesos já disponíveis localmente; passe --allow-download para obtê-los e --cache-dir quando necessário. A consulta longa demais é recusada em vez de truncada silenciosamente. O modo híbrido combina rankings lexical e vetorial por RRF; não é uma probabilidade de verdade.

## Abrir no navegador

```sh
"$PYTHON" "$SKILL_DIR/scripts/start_viewer.py" "/destino"
```

O launcher valida e compila a base, serve o bundle pronto em 127.0.0.1 numa porta livre e abre o navegador. Não exige Node nem internet; Markdown exige PyYAML. O grafo e os localizadores são carregados no início: após editar a base, reinicie-o. Os parágrafos são consultados sob demanda na origem, com verificação de SHA-256; mudanças na fonte exigem revalidação. O cache limitado mantém apenas hashes, sem texto integral. Ctrl+C encerra o processo.

No agente, use processo persistente de terminal com --no-open, capture a URL e abra no browser disponível. Informe como encerrar. Se o host bloquear localhost, solicite a permissão apropriada ou declare o impedimento. Não abra portas públicas.

Opções: --port, --title, --no-open, --config, --layout e --export-layout. Um layout fornecido precisa corresponder aos bytes da exportação atual. Os temas são agrupamentos editoriais, não distâncias de embeddings. O servidor publica apenas bundle, dados do visualizador e evidence/; não expõe os Markdown, o SQLite, os vetores ou o corpus.

## Compatibilidade JSON e recompilação do app

Os scripts de validação, análise, embeddings, Wikipédia e servidor continuam aceitando JSON legado. Para JSON, enrich_wikipedia.py apply ainda exige --output e preserva a entrada. Esse modo não escreve Markdown; use import-json para migrar definitivamente.

```sh
npm ci --ignore-scripts --prefix "$SKILL_DIR/assets/viewer"
npm run build --prefix "$SKILL_DIR/assets/viewer"
```

Recompile somente se mudar as fontes do visualizador; preserve dist e as licenças. O visualizador continua consumindo o contrato graph-contract.md, sem depender do esquema interno do SQLite.

## Testes

```sh
"$PYTHON" -m unittest discover -s "$SKILL_DIR/scripts" -p 'test_*.py'
```

Os testes de Markdown exigem PyYAML, mas não baixam pesos nem consultam a Wikipédia. Teste inferência real e rede separadamente. Validação estrutural e testes offline não substituem revisão das evidências.

## Escritas concorrentes

Build, recuperação e atualização da Wikipédia usam um lock exclusivo por base. Agentes devem serializar alterações na mesma base e validar novamente antes de escrever. Um lock remanescente após interrupção abrupta não é removido automaticamente: confirme que o PID registrado não está executando uma escrita antes de remover somente knowledge/.write-lock. Leituras e bases distintas continuam independentes.

Após embeddings, gere posições semânticas antes de iniciar o visualizador: `python scripts/semantic_layout.py --graph DESTINO --json`. Veja [avaliação da projeção](semantic-layout.md). Build e servidor preservam a projeção válida automaticamente.

## Site estático para deploy

```sh
python scripts/export_site.py --graph DESTINO --output NOVA_PASTA_SITE --evidence paragraphs --json
```

Inclua `--config viewer-config.json` quando houver catálogo customizado. O destino precisa ser novo. Sirva o resultado por HTTP(S); funciona em subdiretórios e dispensa Python/Node no servidor. Não há deploy automático. `--evidence references` é o padrão sem cópia de texto: mostra que o parágrafo exige a origem local. O modo `paragraphs`, solicitado para uma exportação autossuficiente, inclui somente os parágrafos referenciados, deduplicados. Três referências ausentes, por exemplo, não impedem o site: o comando retorna código 3 e cobertura parcial, com aviso na modal. Não contém a base Markdown, SQLite, modelos ou o corpus integral. Caminhos locais das origens são reduzidos a nomes de arquivo. Confira export-manifest.json e direitos de publicação antes de fazer deploy.
