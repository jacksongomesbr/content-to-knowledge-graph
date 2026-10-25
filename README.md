# Conteúdo para grafo de conhecimento

Skill para agentes que transforma livros, documentos, pastas e skills de conteúdo em um grafo de conhecimento com entidades, relações e fontes rastreáveis. Inclui scripts Python e um visualizador 3D que abre no navegador.

O contrato de dados é compatível com o modelo `grafo-do-livro v1`, do projeto [uft-cc-dwm](https://github.com/jacksongomesbr/uft-cc-dwm). A cópia adaptada do visualizador aceita outros domínios e não depende do livro original.

## Instalar no Codex

Clone o repositório para a pasta pessoal de skills. O destino deve estar livre; preserve uma instalação anterior antes de trocar sua origem.

```sh
git clone https://github.com/jacksongomesbr/content-to-knowledge-graph.git ~/.codex/skills/content-to-knowledge-graph
```

Se já tiver instalado a skill por esse clone, atualize com `git -C ~/.codex/skills/content-to-knowledge-graph pull --ff-only`. Em hosts que carregam o catálogo no início da conversa, abra uma nova conversa para descobrir a skill.

## Usar

```text
Use $content-to-knowledge-graph.
Origem: /caminho/do/conteudo
Destino: /caminho/do/grafo
```

O agente inventaria as fontes, extrai entidades e relações, registra evidências e cobertura, busca artigos correspondentes na Wikipédia, gera embeddings locais e inicia o visualizador. Você também pode pedir apenas os dados ou atualizar um grafo existente preservando IDs.

A extração semântica e a revisão das correspondências da Wikipédia são tarefas do agente. Os scripts automatizam extração textual, validação, inferência de embeddings, consultas e aplicação de decisões; não substituem essas revisões por igualdade de nomes ou similaridade vetorial.

## Abrir o exemplo sem instalar dependências

Python 3.10 ou superior basta para validar o grafo e iniciar o visualizador compilado:

```sh
python3 scripts/validate_graph.py examples/graph.json
python3 scripts/start_viewer.py examples/graph.json
```

O servidor escolhe uma porta livre em `127.0.0.1`, imprime a URL e abre o navegador. Encerre com Ctrl+C. Use `--no-open` para apenas obter a URL. O visualizador vem pronto: Node é necessário somente para recompilá-lo. As fontes locais de evidências ficam em `evidence/` junto ao grafo.

## Preparar análise e embeddings

Prefira Python 3.12 compatível com PyTorch na sua plataforma:

```sh
python3.12 scripts/prepare_environment.py --venv .venv
.venv/bin/python scripts/prepare_environment.py --check
```

O preparo usa um ambiente isolado, instala a especificação base e registra as versões resolvidas. Há um lock testado para macOS arm64/Python 3.12 em `references/requirements-macos-arm64-python312.lock.txt`, selecionável com `--requirements`. Não utilize esse lock como garantia para outras plataformas.

Embeddings exigem um modelo local; o primeiro uso pode baixar pesos públicos. O fluxo padrão consulta a Wikipédia enviando rótulos de entidades, sem transmitir o corpus nem os embeddings. Falhas de rede e falta de correspondência são registradas. Nenhum link é forçado.

## Formato de saída

- `graph.json`: fontes e bibliografia em mapas; entidades e relações em listas.
- `coverage.json` e `provenance.json`: cobertura e evidências detalhadas.
- `MODEL.md`: decisões de modelagem e vocabulário.
- `embeddings/`: vetores, IDs alinhados e manifesto do modelo/revisão.
- Relatórios da Wikipédia: candidatos, decisões e auditoria.
- `layout.json`, quando exportado: posições editoriais e hash dos dados.

A leitura complementar não muda as definições nem as evidências do corpus. A disposição gráfica não mede similaridade semântica.

## Scripts e documentação

| Script | Função |
|---|---|
| `prepare_environment.py` | Preparar ambiente e verificar imports reais |
| `extract_corpus.py` | Extrair texto de TXT, Markdown, Quarto, HTML, PDF textual, DOCX e EPUB |
| `validate_graph.py` | Validar contrato e layout |
| `analyze_graph.py` | Métricas e candidatos por similaridade |
| `generate_embeddings.py` | Inferência local, chunking e manifesto |
| `enrich_wikipedia.py` | Descobrir artigos e aplicar correspondências revisadas |
| `start_viewer.py` | Servir o visualizador com o grafo indicado |

Veja [SKILL.md](SKILL.md), [comandos de execução](references/running.md), [contrato](references/graph-contract.md), [ambiente Python](references/python-and-embeddings.md) e [fluxo da Wikipédia](references/wikipedia.md).

## Desenvolvimento e testes

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 -m compileall -q scripts
npm ci --ignore-scripts --prefix assets/viewer
npm run build --prefix assets/viewer
```

Node 22.12+ ou outra versão suportada pelo Vite 7 é necessário para compilar. As fontes ficam em `assets/viewer/src/`; o build e as fontes, incluindo licenças, são distribuídos juntos. O CI executa testes offline dos scripts e compila o visualizador. Testes reais de modelos e de rede devem ser executados separadamente para não depender de downloads e serviços externos a cada commit.

## Licença e atribuição

Este projeto é distribuído sob [CC BY-SA 4.0](LICENSE.md), preservando a licença do projeto de referência. O visualizador deriva de **grafo-do-livro**, de **Jackson Gomes**, no projeto uft-cc-dwm; adaptações estão registradas em [ATTRIBUTION.md](assets/viewer/ATTRIBUTION.md). As dependências conservam suas próprias licenças, incluídas em `assets/viewer/THIRD_PARTY_LICENSES/`.
