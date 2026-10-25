# Enriquecimento padrão com Wikipédia

Execute em toda criação e atualização do grafo, mesmo se o usuário pedir apenas os dados. A etapa é obrigatória; um link para cada entidade não é. O campo `wikipedia` permanece ausente se não houver correspondência segura. Sites e exemplos locais não precisam de um artigo artificialmente associado.

## 1. Descobrir candidatos

```sh
python3 "$SKILL_DIR/scripts/enrich_wikipedia.py" discover "/destino" --report "/destino/wikipedia-candidates.json"
```

O script usa apenas a biblioteca padrão do Python e a API oficial MediaWiki. Consulta português e inglês, resolve redirecionamentos, exclui páginas ausentes, fora do namespace de artigos e de desambiguação. Primeiro busca o título; quando não encontra artigo válido, pesquisa até três candidatos naquele idioma. Não atribui links automaticamente pelo nome. O relatório inclui rótulo/resumo local, título e introdução dos candidatos, URL canônica, pageid e revisão.

Somente o rótulo da entidade é enviado nas consultas; o script não envia o corpus, resumos ou embeddings. Respeite restrições explícitas do usuário sobre rede ou confidencialidade. As consultas são sequenciais, com User-Agent identificável, maxlag, timeout, cache de 24 horas e até três tentativas para falhas transitórias. Pode-se ajustar `--user-agent`, `--delay`, `--timeout` e `--cache`. O padrão consulta ambos os idiomas para permitir ao agente comparar sentidos; a preferência de seleção é português.

Use relatório novo a cada descoberta; o cache pode ser reaproveitado. Uma falha de rede fica registrada por entidade/idioma e retorna código 3, mantendo o relatório para retomada. Não transforme falha de consulta em prova de inexistência de artigo.

## 2. Revisar o sentido — tarefa do agente

Leia o conteúdo original da entidade e compare com título/introdução dos candidatos. Consulte mais do artigo quando a introdução não resolver a ambiguidade. Nenhum score ou igualdade de nomes substitui essa revisão.

Crie `wikipedia-decisions.json` como objeto indexado por **todos** os IDs de nós. Decisões são feitas pelo agente como parte do trabalho, sem pedir ao usuário para aprovar artigo por artigo. `pageid` e `language` de uma seleção devem estar no relatório. Em caso de homônimo errado, artigo demasiado amplo ou evidência insuficiente, rejeite. Prefira português; inglês é aceito quando a edição portuguesa não trouxer correspondência adequada. Justifique cada escolha e rejeição.

```json
{
  "internet": {
    "pageid": 1008,
    "language": "pt",
    "reason": "A introdução descreve a infraestrutura global de redes interligadas, no mesmo sentido do corpus."
  },
  "exemplo-local": {
    "pageid": null,
    "reason": "Exemplo criado pelo material; os candidatos se referem a outros assuntos."
  }
}
```

O exemplo é apenas ilustrativo: use os IDs e resultados efetivos, nunca copie um pageid por memória. Uma `note` opcional explica ao leitor se o artigo cobre um contexto mais amplo. O script de descoberta não usa aliases auxiliares; se o rótulo não produzir candidato, pesquise o nome alternativo com ferramentas disponíveis, ajuste o rótulo apenas se semanticamente correto ou amplie o script de forma testada. Não aprove um artigo diferente só para eliminar uma pendência.

## 3. Verificar e aplicar

```sh
python3 "$SKILL_DIR/scripts/enrich_wikipedia.py" apply "/destino" \
  --report "/destino/wikipedia-candidates.json" \
  --decisions "/destino/wikipedia-decisions.json" \
  --audit "/destino/wikipedia-audit.json"
```

A aplicação exige uma decisão justificada por nó e confere o hash da exportação e o fingerprint dos Markdown da descoberta. Consulta novamente cada pageid selecionado, sem usar cache, para verificar existência, URL canônica, namespace, desambiguação e revisão. Se o artigo mudou, exige nova descoberta e revisão. Só então grava title, url, language e verifiedAt, além de note quando fornecida. Não altera definições, relações ou fontes originais.

Links anteriores também passam pelo fluxo: uma decisão nula os remove do registro resultante. Na base Markdown, omita --output: o script atualiza o campo wikipedia dos documentos, com journal recuperável, e reconstrói o índice e a exportação. Relatório e auditoria devem ser arquivos novos. Falha de verificação interrompe a gravação. Para JSON legado, --output continua obrigatório e preserva a entrada. A auditoria registra escolhas, rejeições, revisões e hashes. Uma decisão sem link com falha de rede na descoberta fica marcada como bloqueada, não como busca concluída.

Depois de aplicar, valide a base. O JSON e o layout são reconstruídos a partir dos documentos; não copie um JSON sobre os Markdown. Os vetores existentes continuam válidos se o hash semântico não mudou; reexecute generate_embeddings.py na pasta gerenciada para reaproveitá-los e atualizar o manifesto. O visualizador já mostra esses links como Leitura complementar, sem consultar a Wikipédia durante a navegação.

## Limites e referências

A revisão semântica depende do agente; o script verifica as condições técnicas e executa decisões explícitas, não compreende sozinho todos os domínios. Com rede indisponível ou correspondências não resolvidas, entregue cobertura parcial declarada. Não force um link nem marque o enriquecimento como completo.

As introduções armazenadas são trechos curtos de consulta; preserve a atribuição à Wikipédia e às URLs correspondentes ao distribuir relatórios. O texto do artigo não deve substituir a evidência do corpus.

Documentação primária usada:
- Busca: https://www.mediawiki.org/wiki/API:Search
- Propriedades e desambiguação: https://www.mediawiki.org/wiki/API:Pageprops
- Uso responsável da API: https://www.mediawiki.org/wiki/API:Etiquette
