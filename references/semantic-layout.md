# Embeddings e geometria do grafo

Execute no perfil Python de análise, após `generate_embeddings.py`:

```sh
python scripts/semantic_layout.py --graph DESTINO --json
python scripts/start_viewer.py DESTINO --no-open --json
```

A projeção é salva em `.generated/semantic-layout.json` e `layout.json`. O build e o servidor reutilizam a projeção somente se os textos semânticos e o arquivo de vetores ainda coincidirem. Mudanças de relações e metadados sem mudança semântica permitem reaproveitar posições. Texto/vetores alterados exigem regeneração. O core pode servir a projeção pronta sem carregar NumPy/sklearn.

O método padrão é t-SNE de três dimensões, distância cosseno, seed 42, 1500 iterações e perplexidade `min(10, (n-1)/3)`, com escala uniforme de raio 450. Exige quatro entidades. Não usa tema, IDs ou arestas para atrair conceitos. Versão sklearn e parâmetros acompanham a saída. Mesmo seed não garante identidade entre versões/plataformas; preserve ambiente e vetores para reprodução.

As métricas têm papéis distintos:

- neighborRecall: fração dos k vizinhos originais preservados na projeção; k até 10, ajustado ao tamanho da base.
- trustworthiness: penaliza vizinhos visualmente próximos que estavam distantes nos vetores; 1 é o máximo.
- distanceSpearman: concordância da ordenação das distâncias globais; t-SNE pode preservar vizinhanças e ter concordância global moderada.

Essas métricas avaliam fidelidade aos vetores, não verdade semântica. Antes delas, revise exemplos de proximidade, polissemia e definições; uma projeção perfeita de vetores ruins continua ruim. Use comparações de domínio e documente os exemplos que motivaram correções, sem apresentá-los como avaliação independente. Para objetivos de distância global, compare MDS/PCA em vez de supor que t-SNE representa uma escala métrica universal.

`semantic_description` é um campo opcional textual no frontmatter de entidades Markdown. Quando presente, label + descrição formam a entrada do embedding. Sem o campo, preserva-se label, aliases, resumo, matemática e corpo. A busca textual e o conteúdo exibido continuam usando os textos originais. Uma descrição deve esclarecer o sentido com suporte nas referências existentes. Regenerar embeddings também atualiza hashes e cache. Fontes não são copiadas.

Referências: [modelo multilíngue](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), [t-SNE](https://scikit-learn.org/stable/modules/generated/sklearn.manifold.TSNE.html), [trustworthiness](https://scikit-learn.org/stable/modules/generated/sklearn.manifold.trustworthiness.html).

## Validação separada e comparação de modelos

Congele uma lista JSON `{"protocol":"...", "comparisons":[{"anchor":"id", "closer":"id", "farther":"id"}]}` antes de obter os resultados. Separe exemplos que motivaram correções dos usados para avaliação; registre a assinatura SHA-256. Não edite descrições com base na amostra de avaliação e continue chamando-a independente. Os julgamentos são preferências de domínio, podem conter ambiguidades e não medem recall de toda a semântica.

```sh
python scripts/evaluate_semantics.py --graph DESTINO --embeddings DESTINO/.generated/embeddings --benchmark AMOSTRA.json --output RESULTADO.json --json
```

O script valida atualidade e integridade dos vetores, registra revisão e prefixo do modelo, pontua comparações e informa intervalo de Wilson. O intervalo é descritivo: a amostra não é aleatória e comparações podem compartilhar conceitos. Se escolher o modelo pelos resultados, essa amostra passa a ser de seleção; use outra para estimar generalização. Não conclua superioridade universal com poucos exemplos.

Para modelos que exigem prefixos, `generate_embeddings.py` aceita `--prefix 'query: '` e `--query-prefix 'query: '`. O prefixo consome tokens em todos os chunks e faz parte da assinatura do cache; a busca respeita o prefixo registrado. O E5 recomenda query: em tarefas simétricas de similaridade, enquanto recuperação pode usar passage: para documentos e query: para consultas. Siga o model card da revisão selecionada. Nunca compare um modelo sem seu formato de entrada exigido.

`semantic_layout.py --perplexity 20` permite avaliar outra escala de vizinhança sem alterar textos nem vetores; o padrão continua 10, limitado pelo tamanho do corpus. Compare preservação local e distâncias globais e registre parâmetros por base, em vez de impor a escolha de uma base a todos os domínios.
