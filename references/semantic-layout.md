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
