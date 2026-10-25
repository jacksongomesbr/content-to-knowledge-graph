# Explorador do grafo

O padrão é uma aplicação local com dados separados da apresentação. Para corpus pequeno, HTML estático pode bastar; para grafos maiores, use um projeto com build e dependências registradas. Determine se o usuário precisa abrir por arquivo ou por servidor local, e forneça instruções coerentes. Não afirme que uma aplicação com fetch local funciona por file:// sem testar.

## Comportamentos essenciais

- Mostrar grafo e catálogo textual de entidades e relações.
- Buscar por nome e resumo; filtrar por tipo e tema. Busca por aliases exige adaptação explícita: a ferramenta original não lê os aliases auxiliares.
- Selecionar entidade e ler definição, relações direcionadas e fontes.
- Selecionar relação e ler a proposição, evidências e eventual inferência.
- Inspecionar vizinhos e restaurar a visão global.
- Abrir as fontes quando acessíveis; para arquivos não publicados, mostrar caminho e localizador sem fabricar URL pública.
- Preservar seleção por fragmento ou mecanismo equivalente quando viável.
- Oferecer uso por teclado, foco visível, contraste e layout que funcione em telas estreitas. O catálogo deve continuar utilizável se a renderização gráfica falhar.

Layout 2D ou 3D é decisão de apresentação, não semântica. Não representar distância como similaridade, causalidade ou relevância sem método documentado. Prefira posições reproduzíveis quando isso facilitar comparação entre versões. Para grafos grandes, carregue subconjuntos e mantenha filtros e catálogo responsivos.

Não dependa de APIs externas durante a navegação para mostrar definições. Escape texto e valide esquemas de URL antes de renderizar conteúdo de documentos. No enriquecimento padrão da Wikipédia, confira o destino e o sentido; marque-os como leitura complementar, separados da evidência do corpus.

## Verificação observável

Teste uma busca por nome ou resumo (e por alias apenas se implementada), um filtro sem resultados, uma entidade com múltiplas fontes e uma relação com direção identificável. Confira navegação por teclado, tela estreita e acesso textual quando o desenho falhar. Teste caminho de publicação relativo apenas se essa forma de distribuição fizer parte do pedido.

Automatize validação dos dados e os fluxos críticos na escala adequada ao aplicativo. Registre comandos e resultados no relatório de entrega.
