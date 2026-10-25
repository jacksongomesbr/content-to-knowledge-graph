# Compatibilidade com agentes

O contrato principal é Agent Skills: uma pasta com SKILL.md, scripts/, references/ e assets/. O núcleo não depende de Codex, de um SDK de LLM ou de nomes de ferramentas de um host. A compatibilidade depende de o agente conseguir ler a skill, acessar arquivos e executar Python com as permissões necessárias.

## Instalação neutra

Clone ou copie **a pasta completa**, preservando seu nome, para um diretório que o host configure como raiz de skills:

```sh
git clone https://github.com/jacksongomesbr/content-to-knowledge-graph.git /caminho/de/skills/content-to-knowledge-graph
```

O caminho exato e a descoberta automática são definidos pelo host. Consulte sua documentação em vez de presumir ~/.codex/skills, ~/.claude/skills ou outro diretório universal. Se a skill já existir, preserve alterações locais antes de substituir. Em instalações por clone, use pull --ff-only para atualizar sem sobrescrever commits locais.

Para hosts sem carregamento de Agent Skills, forneça explicitamente SKILL.md como instrução e a raiz da pasta para localizar as referências. Isso permite uso manual, mas não cria descoberta automática.

Invocação em linguagem natural:

```text
Use a skill content-to-knowledge-graph.
Origem: /caminho/do/conteudo
Destino: /caminho/da/base
```

Prefixos como $ ou comandos de barra são convenções do host, não requisitos da skill. agents/openai.yaml é metadado opcional de interface para produtos OpenAI; pode ser ignorado pelos demais hosts.

## Requisitos e capacidades

- Python 3.11/3.12 recomendado. Perfil core: PyYAML e SQLite com FTS5.
- Perfil de análise: leitores de documentos, NumPy, NetworkX, Sentence Transformers/PyTorch e dependências declaradas.
- Acesso de escrita apenas ao destino e ao espaço temporário autorizado.
- Rede para consultas da Wikipédia e download inicial de modelos, conforme as restrições do usuário/host. Inferência de texto é local.
- Node apenas para recompilar o visualizador. O bundle pronto é servido por Python.
- Browser é opcional para o host: em ambiente sem interface, use --no-open e entregue a URL do servidor. Não presuma ferramentas de navegador específicas.

Resolva os scripts a partir da pasta da skill que foi carregada. PYTHON indica o executável real do ambiente selecionado; SKILL_DIR é um placeholder para essa pasta, não uma variável fornecida universalmente pelos hosts. No Windows, adapte o caminho do venv para Scripts/python.exe e a sintaxe de variáveis ao shell usado.

## Consumo eficiente de contexto

Leia SKILL.md e somente as referências relevantes. Para uma base já gerada, comece por .generated/INDEX.md ou .generated/llms.txt. Use busca/percursos e leia os documentos selecionados, em vez de concatenar a base inteira. O SQLite é reconstruível e não é o documento autoral.

Para automação, use --json e o protocolo cli-protocol.md. Não extraia resultados por regex de mensagens humanas nem trate logs como dados. Os scripts não fazem chamadas a um provedor de LLM para decidir fatos; a análise semântica e a revisão dos candidatos continuam a cargo do agente.

## Agentes distintos e concorrência

Portabilidade entre hosts não significa coordenação de escritas simultâneas. Para vários agentes atuando ao mesmo tempo, use destinos/checkouts separados ou serialize as edições e o build de cada base. O SQLite tem transações e há detecção de alterações, mas a skill não implementa um coordenador distribuído para editar Markdown.

## Papéis dos arquivos

- SKILL.md: executar a tarefa e aplicar seus critérios.
- AGENTS.md: manter o repositório e testar alterações; não duplica o fluxo inteiro da skill.
- llms.txt: mapa curto da documentação; não instala a skill, concede permissões nem garante leitura por todos os clientes.
- .generated/INDEX.md e catálogos: navegação reconstruível da base de conhecimento.

O llms.txt do repositório usa links relativos, úteis em clones e em acesso ao arquivo bruto. O índice de uma base usa links de filesystem para seus Markdown; não é publicado automaticamente no servidor do visualizador. Publicação web exige uma configuração explícita com URLs resolvíveis. Não geramos llms-full.txt: a recuperação seletiva evita duplicação e consumo desnecessário de contexto.

Referências dos formatos:
- https://agentskills.io/specification
- https://agents.md/
- https://llmstxt.org/

## Validação do pacote

Execute `python scripts/validate_skill.py <pasta-da-skill> --json`. O validador local cobre o contrato de frontmatter de Agent Skills, incluindo compatibility e license. Validadores antigos de um host podem rejeitar campos aceitos pela especificação atual; isso não comprova, por si só, incompatibilidade do runtime. Confirme a descoberta no cliente efetivamente utilizado. A validação de formato não equivale a teste de comportamento em todos os agentes.
