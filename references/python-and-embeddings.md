# Ambiente Python de análise e embeddings

## Ambiente padrão do fluxo

Use os comandos de `running.md` e os scripts incluídos; use o ambiente já selecionado pelo usuário se for adequado. Registre `sys.executable`, versão, sistema e arquitetura; verifique imports e versões com `importlib.metadata`. Sem ambiente adequado, crie `.venv` no destino usando uma versão Python suportada pelas dependências (prefira 3.11 ou 3.12 quando disponíveis e compatíveis). Não troque silenciosamente o interpretador global. O Python gerenciado pelo sistema ou pelo app pode não ter pip ou pacotes de ML; não use `--break-system-packages` nem sudo pip.

O conjunto base está em `requirements-analysis.txt`, nesta pasta. Ele é uma especificação inicial, não um lock universal. Instale com o Python do ambiente selecionado; após resolver e testar, registre as versões efetivas num lock do projeto. Para PyTorch, confira a distribuição apropriada ao SO/CPU/GPU antes da instalação. CPU é suficiente para o caminho padrão; GPU é opcional. Não instale CUDA em macOS. Não exija treinamento nem um banco vetorial.

Exemplo para ambiente novo na raiz do destino, adaptando `python3` se necessário:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r /caminho/da/skill/references/requirements-analysis.txt
.venv/bin/python -m pip check
.venv/bin/python -m pip freeze > requirements-analysis.lock.txt
```

Copie a especificação para o projeto se isso facilitar a reprodução. Caminhos Windows usam `Scripts/python.exe`. Respeite limites de escrita e conectividade do ambiente. Instalações de pacotes e download de pesos podem precisar de autorização do host; não presuma que carregar esta skill concede acesso adicional.

## Ferramentas por função

- `numpy`: vetores, persistência e álgebra.
- `scipy`, `scikit-learn`: similaridade por cosseno, vizinhos e análise exploratória.
- `networkx`: componentes, conectividade e métricas estruturais.
- `jsonschema`, `PyYAML`: validação e leitura de configuração.
- `sentence-transformers`, `torch`: inferência de embeddings locais de texto.
- `pypdf`, `python-docx`, `beautifulsoup4`: extração inicial de PDF textual, DOCX e HTML.

EPUB, PDF escaneado, imagens e áudio exigem ferramentas adicionais conforme a entrada. Não anuncie OCR ou transcrição como disponíveis só porque os pacotes base foram instalados. Evite acrescentar todas as dependências multimodais a cada execução.

## Geração de embeddings

1. Escolha um modelo de sentença compatível com os idiomas e o domínio. Consulte seu model card: licença, tamanho, revisão, limites de tokens, instruções/prefixos e dimensão. Use revisão imutável quando possível. Não habilite `trust_remote_code` por conveniência. Pesos baixados não são dados do usuário enviados a um serviço; uma API remota de embeddings, por outro lado, transmite textos e só deve ser usada quando escolhida pelo usuário.
2. Defina unidades estáveis do corpus e textos canônicos dos nós. Preserve ponteiros à fonte e offsets/linhas/páginas nos chunks. Separe conjuntos de vetores de chunks e de entidades. Faça chunking dentro do limite do modelo, considerando os tokens efetivos; não deixe truncamento silencioso substituir cobertura. Registre estratégia, sobreposição e agregação quando usada.
3. Gere em lotes ajustados à memória, com hashes do texto + modelo/revisão + parâmetros para rastreabilidade. O script incluído não implementa cache incremental de vetores; não afirme reutilização de inferência sem adicioná-la e testá-la. Escolha CPU por padrão; MPS/CUDA somente se disponível e testado. Use `SentenceTransformer.encode` para representações simétricas ou `encode_document`/`encode_query` quando o modelo e a tarefa pedirem recuperação assimétrica. Registre normalização, precisão e prefixos aplicados.
4. Salve `embeddings/entities.npy` e, se utilizados, `embeddings/chunks.npy`, sem pickle. Grave IDs na mesma ordem em arquivos JSON e `embeddings/manifest.json` com modelo, revisão resolvida, versão da biblioteca, dimensão, dtype, normalização, hashes de texto, parâmetros, data e hash/versão do corpus. Não misture vetores de modelos ou revisões diferentes num mesmo índice.
5. Use vizinhos por cosseno para sugerir duplicatas, relações ou grupos a revisar, não para aprovar automaticamente fatos. Calibre qualquer limiar em exemplos do corpus e registre a decisão. Preserve divergências e homônimos. Layout editorial, cluster semântico e grafo de relações são objetos diferentes.

## Smoke tests e limites

Execute imports de todos os pacotes base, `pip check`, uma análise pequena de componentes com NetworkX e uma geração real com dois textos curtos. Valide forma esperada, dimensão, valores finitos, normas quando houver normalização e similaridade calculável. O modelo deve ser carregado e executado: um import bem-sucedido não prova disponibilidade de pesos ou funcionamento da inferência.

Depois valide todo o artefato: uma linha por ID, IDs únicos, nenhuma dimensão divergente, nenhum vetor inválido e nenhuma reutilização de cache de texto alterado. Não coloque vetores no graph.json: o visualizador atual não os consome. Quando houver impedimento de instalação ou download, informe o que passou, o que falta e o impacto; não invente embeddings ou chame hash/TF-IDF de embedding neural.

## Referências de manutenção

Confira estas fontes ao atualizar o ambiente, não fixe versões obsoletas por memória:
- Sentence Transformers: https://sbert.net/docs/installation.html
- Python Packaging / ambientes virtuais: https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/
- PyTorch / distribuições por plataforma: https://pytorch.org/get-started/locally/
