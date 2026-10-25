# Contrato padrão: grafo-do-livro v1

Este é o contrato da **exportação** `.generated/graph.json`; a fonte canônica é Markdown, conforme knowledge-format.md. Gere `graph.json` compatível com `GraphData` da ferramenta grafo-do-livro. A referência original foi inspecionada em `uft-cc-dwm/grafo-do-livro/src/model.ts` em 25/10/2026. O caminho original é referência histórica, não dependência para executar esta skill. Se o usuário indicar outra versão da ferramenta, confira seu modelo e validadores antes de gerar.

## Campos do JSON

Raiz: `schemaVersion: 1`, `bookUrl: string`, `bibliography: objeto`, `sources: objeto`, `nodes: lista`, `edges: lista`.

`bibliography` é um mapa de chave bibliográfica para `{label, path, anchor}`, todos strings. Use `{}` se não houver citações bibliográficas. Cada item citado em `sources[*].citations` precisa existir neste mapa. Não invente autor, ano ou referência para satisfazer o formato.

`sources` é um mapa de identificador para:
- `kind`: opcional, apenas `book` ou `bibliography`; omita quando não houver correspondência honesta.
- `title`: string opcional.
- `chapter`: número; para material sem capítulo, use `0` como convenção técnica documentada em MODEL.md, sem apresentá-lo como capítulo real.
- `path`: caminho ou URL da representação consultável.
- `sourceFile`: caminho do arquivo original ou identificador resolvível da origem.
- `section`: seção ou localizador legível (página, timestamp, registro).
- `anchor`: âncora real da representação consultável; use string vazia quando não existir.
- `citations`: lista de chaves presentes em `bibliography`; pode ser vazia.

Cada nó tem `id`, `label`, `type`, `theme`, `summary`, `detail` (strings), e `sources` (lista não vazia de chaves do mapa). Campos opcionais: `math` (string), `wikipedia` (`title`, `url`, `language`, `verifiedAt`, `note` opcional). A busca e revisão na Wikipédia são etapas padrão obrigatórias. O campo permanece opcional porque entidades sem correspondência ficam sem link. Wikipédia é leitura complementar: só inclua após verificar destino e sentido; idiomas aceitos pela ferramenta são `pt` e `en`, URL HTTPS na edição correspondente e data ISO YYYY-MM-DD.

Cada aresta tem `id`, `source`, `target`, `label`, `summary` (strings) e `sources` (lista não vazia de chaves). `source` e `target` são IDs de nós. `label` é o predicado legível e `summary` explica a proposição no contexto.

IDs precisam ser únicos inclusive entre nós e arestas: o validador original usa o mesmo conjunto para ambas as coleções. Preserve os IDs em atualizações. Arestas distintas entre o mesmo par podem existir; use IDs sem colisões.

Não use `sourceIds`, listas para `sources`, nem substitua os campos da raiz por `metadata`. Guarde aliases, evidências por trecho e classificação das relações nos Markdown. O compilador exporta informações adicionais para provenance.json; metadados de vetores ficam no manifesto dos embeddings. A ferramenta atual não lê esses campos e não busca por aliases. Não anuncie funcionalidades que dependem de adaptação do aplicativo.

## Tipos e temas

O aplicativo possui catálogos estáticos em `src/model.ts`. Tipos originais: `concept`, `person`, `place`, `method`, `software`, `format`, `application`. Atenção: `place` é exibido como instituição, `format` como artefato, `application` como plataforma e `method` como estratégia. Não classifique lugares geográficos ou eventos nesses tipos apenas para passar no teste.

Temas originais: `navegacao`, `formularios`, `arquitetura`, `contrato`, `linguagem`, `interfaces`, `adaptacao`, `fundamentos`, `react`, `ambiente`, `git`, `web`, `estrategias`, `tecnologias`, `produto`, `processo`.

Se o conteúdo couber nesses catálogos, use-os. Para outros domínios, mantenha a estrutura JSON e gere uma proposta de catálogos adequada; compatibilidade imediata com o aplicativo original exige atualizar `types`, `themes` e os centros do gerador de layout na cópia de destino. Não altere a instalação original sem fazer parte do pedido. Se o usuário pedir somente JSON para a ferramenta sem alterações, explique qualquer impossibilidade de classificação sem distorcer o conteúdo. Diferencie compatibilidade estrutural de compatibilidade com o catálogo concreto.

## Fontes para qualquer origem

A ferramenta resolve links com `new URL(path, bookUrl)` e acrescenta `#anchor`. Portanto `bookUrl` precisa ser uma URL absoluta válida, terminada em `/` quando representar uma pasta. Use endereço real fornecido ou determinado pelo projeto; para visualização local, registre a base do servidor local usada nas instruções.

Para documentos sem representação web, gere páginas HTML locais de evidências no destino, com âncoras estáveis e trechos curtos/paráfrases e localizadores originais; aponte `path` para essas páginas. Para referências bibliográficas, gere uma página de referências com as respectivas âncoras quando necessário. Não invente URLs públicas e não dependa de abrir caminhos de filesystem a partir de um site HTTP.

## Exemplo mínimo

O arquivo `evidence/manual.html` deve existir no resultado e conter a âncora `web-internet`; a linha original precisa sustentar a proposição.

```json
{
  "schemaVersion": 1,
  "bookUrl": "http://localhost:5173/",
  "bibliography": {},
  "sources": {
    "manual-web": {
      "title": "Manual", "chapter": 0,
      "path": "evidence/manual.html", "sourceFile": "manual.md",
      "section": "Web e Internet, linha 12", "anchor": "web-internet", "citations": []
    }
  },
  "nodes": [
    {"id": "web", "label": "Web", "type": "concept", "theme": "web", "summary": "Sistema que utiliza a infraestrutura da Internet.", "detail": "Definição limitada ao trecho consultado.", "sources": ["manual-web"]},
    {"id": "internet", "label": "Internet", "type": "concept", "theme": "web", "summary": "Infraestrutura utilizada pela Web.", "detail": "Definição limitada ao trecho consultado.", "sources": ["manual-web"]}
  ],
  "edges": [
    {"id": "web-uses-internet", "source": "web", "target": "internet", "label": "utiliza a infraestrutura da", "summary": "A Web utiliza a infraestrutura da Internet.", "sources": ["manual-web"]}
  ]
}
```

## Layout e validação de integração

O aplicativo importa `src/data/graph.json` e `src/data/layout.json`. O layout tem `method`, `graphSha256` e `positions`, mapa de ID do nó para `{x,y,z}` numéricos finitos. `graphSha256` é SHA-256 dos bytes exatos de graph.json, incluindo formatação e newline. Não reutilize layout depois de reformatar o JSON.

Na cópia do aplicativo de destino, use o gerador existente em vez de reconstruir seu algoritmo:

```sh
npm run layout
npm test
npm run build
```

Execute também os fluxos de navegador pertinentes se o aplicativo mudar. O gerador original usa centros por tema e não produz posição para tema desconhecido; alterações de catálogo precisam refletir nesses centros. O layout editorial não usa embeddings e suas distâncias não significam similaridade.

Para saída somente de dados, entregue a base Markdown e graph.json em .generated/ e, quando houver cópia da ferramenta autorizada e disponível, gere layout com seus scripts. Se não puder executar a ferramenta, declare que a integração não foi testada; nunca alegue compatibilidade completa só porque o JSON abre.

Registre coverage.json e MODEL.md no projeto. Os Markdown guardam os atributos canônicos; provenance.json é gerado e não deve ser editado. Revise tanto os invariantes estruturais quanto a fidelidade semântica das afirmações.
