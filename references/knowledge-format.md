# Fonte canônica: Markdown com frontmatter

Edite os documentos de `knowledge/`. O SQLite, os embeddings, o JSON e o layout são artefatos derivados; não há sincronização bidirecional. Um ID identifica um registro e não muda quando o arquivo é renomeado. IDs de entidades e relações são globalmente únicos entre essas duas coleções; fontes e bibliografia têm seus próprios namespaces.

```text
projeto/
  knowledge/
    knowledge.yml
    entities/*.md
    relations/*.md
    sources/*.md
    bibliography/*.md
  .generated/
    index.sqlite
    manifest.json
    INDEX.md
    llms.txt
    index/*.md
    graph.json
    layout.json
    provenance.json
    evidence/*.html
    embeddings/
```

Pode-se passar ao CLI a pasta `projeto/` ou `knowledge/`. Uma base em pasta com outro nome também funciona: nesse caso `.generated/` fica dentro dessa pasta. Apenas as quatro coleções são indexadas; renders e índices não entram no corpus.

## Configuração

`knowledge.yml` usa YAML seguro:

```yaml
schema_version: 1
book_url: http://localhost:5173/
graph_metadata: {}
```

`book_url` é a base real das fontes web, mantida para compatibilidade. Páginas locais com path `evidence/...html` são geradas em `.generated/evidence/` e servidas pelo launcher em localhost. `graph_metadata` preserva metadados adicionais da raiz do JSON legado; não substitui os campos de configuração.

## Entidades

`entities/internet.md`:

```markdown
---
id: internet
kind: entity
label: Internet
entity_type: concept
theme: web
aliases:
  - Rede mundial de computadores
summary: Infraestrutura global de comunicação entre redes.
sources:
  - historia-web
evidence:
  - source: historia-web
    locator: Seção Web e Internet, parágrafo 1
---

A Internet transporta dados entre redes interligadas.
A Web é um dos sistemas que utilizam essa infraestrutura.
```

`id`, `kind`, `label`, `entity_type`, `theme`, `summary` e `sources` são obrigatórios; o corpo não pode estar vazio e vira `detail` na exportação. `aliases` é uma lista de strings únicas, preservada na exportação para busca no visualizador. `math` e `wikipedia` mantêm os campos do contrato de exportação. `evidence` é opcional para migração, mas recomendado na extração nova; cada item referencia uma fonte declarada também em sources e tem locator. Outros metadados podem ser preservados, mas não use campos conflitantes com o contrato.

O índice semântico usa label, aliases ordenados, summary, math quando presente e corpo. Wikipédia, datas, evidências, caminho do arquivo e formatação do frontmatter não entram no texto dos embeddings. Alterar esses metadados pode atualizar o índice/exportação sem exigir nova inferência.

## Relações

`relations/web-uses-internet.md`:

```markdown
---
id: web-uses-internet
kind: relation
source: web
target: internet
predicate: uses
label: utiliza a infraestrutura da
basis: explicit
sources:
  - historia-web
---

A Web utiliza a infraestrutura da Internet.
```

`source` e `target` são IDs de entidades. O corpo contém a proposição contextual e vira `summary` na exportação. `predicate` guarda um vocabulário normalizado definido em MODEL.md; o visualizador utiliza label. `basis` aceita `explicit`, `inferred` e `unspecified`; inferências exigem `rationale` no frontmatter. A migração usa unspecified quando o JSON antigo não tinha essa classificação, sem inventar que a relação era explícita. Novas relações devem ser classificadas e justificadas pelo agente.

Não derive arestas automaticamente de links Markdown, proximidade textual ou similaridade vetorial. Links no corpo servem à leitura; relações são registros explícitos.

## Fontes

`sources/historia-web.md`:

```markdown
---
id: historia-web
kind: source
source_kind: book
title: Manual de exemplo
chapter: 1
path: evidence/manual.html
sourceFile: chapters/01-introducao.qmd
section: Web e Internet
anchor: web-internet
citations: []
---

Excerto curto ou paráfrase identificada que permita conferir a proposição.
Indique os localizadores e preserve a atribuição da origem.
```

`source_kind` corresponde ao `kind` do contrato JSON (`book` ou `bibliography`); omita quando não corresponder ao material. `kind: source` identifica o registro Markdown. Os demais campos seguem `graph-contract.md`; use chapter 0 para material sem capítulo real. O corpo mantém evidência adicional, indexável e apresentada nas páginas locais. Na migração, corpo vazio é permitido: o gerador apresenta apenas o localizador e declara que o texto original não foi incorporado. Não inventa excertos.

## Bibliografia

Um arquivo em `bibliography/` tem `kind: bibliography`, `id`, `label`, `path` e `anchor`. O corpo pode conter a referência completa; as chaves de citations das fontes devem existir nessa coleção.

## Validação e indexação

O parser usa YAML seguro, recusa chaves duplicadas e trata datas como strings. O compilador verifica identidades, tipos de campos, fontes, citações e extremidades das relações antes de atualizar o índice. A validação estrutural não substitui a revisão do sentido das afirmações. O schema continua existindo, apenas está distribuído em documentos legíveis.

`knowledge.py build` calcula hashes de conteúdo, reaproveita o parse dos documentos inalterados e atualiza as linhas FTS somente se o texto indexável mudou. As pequenas projeções relacionais são reconstruídas transacionalmente a cada build para conferir integridade. Arquivos removidos saem do índice; renomeações preservam IDs. Não se baseia somente em mtime.

O SQLite contém documents, nodes, edges, sources, bibliography, source_refs, citations e o índice FTS5. Há índices de origem/destino e consulta recursiva de vizinhos. A busca textual usa Unicode sem distinção de acentos, pesos por campo e BM25. Consultas recusam índice desatualizado em vez de servir dados silenciosamente antigos. SQLite/FTS5 é pré-requisito do Python escolhido; o comando informa erro se a extensão faltar.

As consultas SQLite e híbridas estão disponíveis aos scripts/agente. O visualizador continua lendo a exportação JSON e filtrando em memória; não consulta diretamente o SQLite.

`search_knowledge.py` oferece busca lexical, semântica e híbrida. A híbrida combina rankings por reciprocal rank fusion (constante 60), evitando somar diretamente BM25 e cosseno. Os resultados são sugestões de recuperação, não probabilidades de verdade. A busca semântica exige modelo/revisão iguais aos embeddings e valida os hashes e o alinhamento dos vetores.

## Atualizações da Wikipédia

O script lê a base diretamente. Após revisão e nova consulta na API, atualiza somente o campo wikipedia de cada entidade e reconstrói o índice/exportação. O frontmatter é serializado novamente, podendo normalizar formatação/comentários YAML. O corpo e os demais valores são preservados. Cada arquivo é substituído atomicamente; um journal permite recuperar uma interrupção entre arquivos com `knowledge.py recover`. Uma edição externa divergente bloqueia recuperação automática.

## Migração

```sh
python scripts/knowledge.py import-json /origem/graph.json --output /destino/knowledge
python scripts/knowledge.py build /destino
```

O importador exige pasta nova, mantém o JSON original e preserva IDs, campos e explicações. Os nomes gerados têm um sufixo derivado do ID para evitar colisões de filesystem; podem ser renomeados depois. A migração não incorpora automaticamente o corpus original nem pressupõe que o leu.

Depois da migração, edite apenas os Markdown. O JSON legado continua aceito pelos scripts para interoperabilidade; edições nele não retornam à base Markdown.

## Navegação para agentes

O build gera .generated/INDEX.md, .generated/llms.txt e catálogos por coleção em .generated/index/. Cada página tem até 100 registros; links apontam aos Markdown canônicos por caminhos relativos. As entradas iniciais são exemplos em ordem de ID, não uma classificação de importância. Páginas antigas são removidas quando a coleção diminui. Esses arquivos são reconstruíveis e não entram no corpus.

A navegação é de filesystem; o visualizador não expõe esses documentos nem os Markdown canônicos por HTTP. O llms.txt do repositório é separado e mapeia a documentação da skill. Use os comandos com --json para recuperar dados sem interpretar mensagens humanas.

## Referências por frase ou parágrafo

O padrão é content_mode: reference. A fonte guarda sourceFile absoluto (arquivo cadastrado) e source_sha256 (SHA-256 dos bytes originais), com descrição curta no corpo, sem cópia do documento. Cada evidence guarda source, locator e lines inclusivas, desde 1 na unidade extraída; unit é document para texto/DOCX/HTML, página inteira desde 1 para PDF ou caminho do item EPUB. heading pode guardar a seção revista, permitindo apresentar contexto sem carregar a fonte. Inclua aliases apenas após revisão; relation_text opcional deve existir literalmente no parágrafo.

O build gera .generated/evidence/passages.json apenas com metadados/localizadores. A modal solicita /evidence-passage?id=<ID cadastrado>. O servidor valida o hash e recupera o parágrafo da origem. A API não aceita caminhos, URLs ou intervalos fornecidos pelo navegador. Fonte ausente, alterada ou sem leitor gera aviso explícito, sem usar conteúdo antigo. Texto é lido em fluxo até o parágrafo; PDF extrai somente a página indicada. Outros leitores podem precisar processar a unidade em memória, sem manter cópias persistentes. Não há cache integral padrão. URLs remotas precisam de um leitor conectado e registro de versão; a implementação local declara a indisponibilidade, sem fazer downloads silenciosos.

Os metadados técnicos ficam em Detalhes da fonte, recolhidos. Nomes e aliases literais são destacados com a cor da entidade; predicados literais usam sublinhado tracejado na cor da origem. Inferências mantêm basis/rationale. Destaque lexical não comprova sustentação semântica. O contrato graph.json v1 permanece compatível.

Somente quando o usuário solicitar exportação portátil, pode-se usar content_mode: original com texto único no corpo da fonte e content_sha256 (SHA-256 do corpo UTF-8 após strip). Esse modo preserva compatibilidade com bases anteriores e autoriza parágrafos derivados na exportação. O padrão referenciado depende de a origem continuar acessível.

Extrações de corpus são intermediárias temporárias, fora da saída final. Não mantenha units.jsonl, snapshots integrais ou páginas derivadas com cópias do original em uma entrega referenciada. Atualize o hash e localizadores apenas após revisar mudanças da fonte.

Para entidades com sentido ambíguo, o campo opcional `semantic_description` aceita uma definição contextual textual fiel às fontes. Quando presente, label + descrição substituem o restante da entrada do embedding; não substituem resumo/corpo na interface nem contam como evidência. Veja [posicionamento semântico](semantic-layout.md).
