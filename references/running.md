# Scripts e início do visualizador

Resolva `SKILL_DIR` como a pasta desta skill; não dependa do diretório atual. Os comandos abaixo usam caminhos de exemplo entre aspas. `python3` basta para extração TXT/Markdown/Quarto, validação e servidor; use o Python do ambiente de análise para formatos adicionais, métricas e embeddings.

## Preparação

```sh
python3 "$SKILL_DIR/scripts/prepare_environment.py" --check
python3.12 "$SKILL_DIR/scripts/prepare_environment.py" --venv "/destino/.venv"
```

`--check` testa imports em subprocessos e retorna erro se houver ausências ou incompatibilidades. Use um Python 3.11/3.12 disponível para preparar o venv se o Python padrão for incompatível. O preparo instala `requirements-analysis.txt`, executa pip check e imports e grava lock junto ao venv. Não baixa pesos; o teste real de inferência é o comando de embeddings. Não altere Python global. Se já existir ambiente adequado, use seu executável absoluto. Há um lock testado em macOS arm64/Python 3.12 em `requirements-macos-arm64-python312.lock.txt`; nessa plataforma, passe-o por `--requirements`. Em outras plataformas, resolva a especificação base e teste antes de fixar versões.

## Extração e modelagem

```sh
"/destino/.venv/bin/python" "$SKILL_DIR/scripts/extract_corpus.py" "/origem/livro" "/origem/artigos.pdf" --output "/destino/corpus"
```

O script extrai TXT, MD, QMD, HTML, PDF textual, DOCX e EPUB para `units.jsonl` com localizadores e hashes, e grava `coverage.json`. Não segue symlinks e exclui dependências, renders e o próprio destino. Exige destino novo/vazio. Não acessa URLs nem faz OCR/transcrição; obtenha esses textos com as ferramentas apropriadas e registre as limitações. Unidades sem texto retornam estado parcial e código de saída 1.

Depois leia as unidades e realize a extração semântica conforme SKILL.md: este script **não gera entidades e relações automaticamente**. Produza graph.json com evidências revisadas e provenance.json. O arquivo coverage da extração registra leitura por máquina, não revisão semântica; complemente essa distinção no relatório do corpus.

```sh
python3 "$SKILL_DIR/scripts/validate_graph.py" "/destino/graph.json"
"/destino/.venv/bin/python" "$SKILL_DIR/scripts/analyze_graph.py" "/destino/graph.json" --output "/destino/analysis.json"
```

A análise retorna componentes, graus e nós isolados. Não elimina componentes nem inventa conexões. O validador verifica estrutura e links entre registros; não garante que a afirmação seja sustentada pelo texto nem que a URL remota esteja acessível.

## Wikipédia: etapa padrão antes dos embeddings

Execute `enrich_wikipedia.py discover`, revise todos os candidatos e execute `apply`, conforme `wikipedia.md`. Finalize graph.json com o resultado antes de gerar embeddings e layout: o enriquecimento muda os bytes e invalida hashes anteriores. A revisão é tarefa do agente, sem pedir ao usuário para escolher cada artigo.

## Embeddings reais

Escolha modelo após conferir model card/licença e idioma. Modelo multilíngue de exemplo: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Prefira `--revision` com commit resolvido para reprodução. O primeiro uso pode baixar pesos públicos; os textos permanecem na inferência local.

```sh
"/destino/.venv/bin/python" "$SKILL_DIR/scripts/generate_embeddings.py" --graph "/destino/graph.json" --model "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" --output "/destino/embeddings/entities"
"/destino/.venv/bin/python" "$SKILL_DIR/scripts/generate_embeddings.py" --units "/destino/corpus/units.jsonl" --model "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" --output "/destino/embeddings/chunks"
"/destino/.venv/bin/python" "$SKILL_DIR/scripts/analyze_graph.py" "/destino/graph.json" --embeddings "/destino/embeddings/entities" --output "/destino/analysis-with-neighbors.json"
```

Outras opções: `--batch-size`, `--device cpu`, `--cache-dir`, `--local-only`, `--overlap-tokens`. Exige saída nova/vazia. Usa encode simétrico sem prefixo automático; modelos que exigem instruções ou modos assimétricos precisam de adaptação explícita. O tokenizer deve suportar offsets (fast tokenizer). Textos longos são segmentados por tokens e os vetores de entidades são médias renormalizadas dos chunks. O manifesto registra essa decisão. IDs e vetores ficam alinhados; `chunks.mapping.json` contém os offsets para recuperar a evidência. Hashes de texto registram a versão; pesos usam o cache do provedor. O script recompõe a saída, não implementa cache incremental de vetores.

## Iniciar no navegador

```sh
python3 "$SKILL_DIR/scripts/start_viewer.py" "/destino/graph.json"
```

O comando valida o grafo, gera layout editorial em memória, inicia em `127.0.0.1` numa porta livre e abre o navegador. Não depende de Node, internet, embeddings nem do livro original. O terminal mostra URL e caminho dos dados. Mantenha o processo ativo; encerre com Ctrl+C. Os dados são um snapshot: reinicie depois de editar graph.json.

No agente, execute como processo persistente usando a ferramenta de terminal, capture a URL e abra-a pelo browser do app quando disponível. Use `--no-open` para evitar abrir o navegador do sistema nesse caso. O host pode exigir permissão para escutar localhost; declare o bloqueio se ocorrer. Não lance processos desacoplados sem informar como encerrá-los.

Opções:
- `--port 4317`: porta fixa; se ocupada, retorna erro sem encerrar processos alheios.
- `--no-open`: apenas imprime a URL.
- `--layout "/destino/layout.json"`: usa layout existente após validar hash e posições.
- `--export-layout "/destino/layout.json"`: grava o layout sem substituir arquivo existente.
- `--title "Título do conteúdo"`: título da página.
- `--config "/destino/viewer-config.json"`: título/subtítulo e rótulos/paleta de tipos/temas.

O servidor expõe apenas o aplicativo, três JSONs e arquivos em `evidence/` junto ao grafo; não publica o diretório inteiro, corpus ou embeddings. Para fontes locais, gere páginas curtas escapadas em `evidence/` e aponte os campos path/anchor para elas. Links externos continuam usando bookUrl. O launcher não renderiza evidências automaticamente.

O visualizador aceita tipos/temas de outros domínios (slugs minúsculos), com fallback para o nome e cores padrão, ou catálogos em config. A ferramenta original, sem adaptações, continua exigindo seus catálogos fixos. O layout genérico mantém a estrutura esperada (hash e posições), mas usa centros determinados pelos temas presentes; não replica as coordenadas específicas do livro.

## Recompilar o visualizador quando seu código mudar

O bundle pronto fica em `assets/viewer/dist/`; não armazene node_modules na skill. As fontes derivadas estão em `assets/viewer/src/`, com atribuição e licença CC BY-SA 4.0 em `ATTRIBUTION.md` e `LICENSE.md`. As licenças de dependências ficam em `THIRD_PARTY_LICENSES/`.

```sh
npm ci --ignore-scripts --prefix "$SKILL_DIR/assets/viewer"
npm run build --prefix "$SKILL_DIR/assets/viewer"
```

Recompile antes de distribuir uma alteração de fonte. Para servir os dados atuais, basta Python; o grafo não é embutido na compilação. Aplique testes de busca, filtros, relações/fontes, teclado, tela estreita e fallback sem WebGL após mudanças no app.

## Testes incluídos

```sh
python3 "$SKILL_DIR/scripts/test_pipeline.py"
python3 "$SKILL_DIR/scripts/test_wikipedia.py"
```

Os testes cobrem referências quebradas, colisões de IDs, layout/hash, temas novos, grafo vazio, preservação das origens e exclusão do destino na extração. A inferência exige teste separado com pesos reais; os testes unitários não baixam modelos.
