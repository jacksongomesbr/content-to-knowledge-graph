# Protocolo de scripts para agentes

Todos os comandos operacionais aceitam --json e --debug. Esses sinalizadores podem aparecer antes ou depois do subcomando; use -- para encerrar o processamento de opções quando um valor posicional coincidir com um sinalizador. Os módulos auxiliares e testes não são comandos operacionais.

Sem --json, a saída de uso manual é preservada. Com --json, stdout contém um objeto JSON por comando finito, em uma única linha. Logs, avisos de dependências e progresso ficam em stderr. Não analise mensagens humanas como protocolo.

```json
{
  "schemaVersion": 1,
  "ok": true,
  "status": "success",
  "data": {"valid": true},
  "error": null
}
```

Em erro:

```json
{
  "schemaVersion": 1,
  "ok": false,
  "status": "error",
  "data": null,
  "error": {"code": "usage_error", "message": "Parâmetro obrigatório ausente."}
}
```

O envelope é comum. data depende do comando e conserva objetos/listas de resultado: busca retorna lista, build retorna caminhos/contadores, extração retorna caminhos/totais e a verificação de ambiente retorna diagnósticos por pacote. Um ambiente incompleto pode devolver data com os diagnósticos e error ao mesmo tempo.

## Estados e códigos de saída

| Código | Estado | Interpretação |
|---|---|---|
| 0 | success | Operação concluída |
| 1 | error | Falha operacional, dados inválidos ou dependências ausentes |
| 2 | error | Uso incorreto da CLI/argumentos |
| 3 | partial | Artefatos entregues com cobertura parcial registrada |
| 130 | error | Interrupção pelo usuário |

ok é false para partial: o agente deve ler o relatório, declarar os limites e decidir a retomada. Código 3 é usado, por exemplo, na extração de arquivos sem texto legível e em consultas incompletas da Wikipédia. Falta de correspondência sem falha de consulta não é um erro operacional.

error.code é uma categoria textual, como usage_error, operation_failed, missing_dependency, not_found, invalid_data, index_error, subprocess_failed, io_error, internal_error ou interrupted. Algumas validações com contexto específico usam operation_failed e explicam o problema em message. Mensagens são diagnósticos, não um contrato para parsing. --debug acrescenta traceback em stderr, sem alterar o envelope.

--help --json escreve a ajuda legível em stderr e retorna um envelope de sucesso com data.help: true. Para apenas ler a ajuda, omita --json.

## Servidor persistente

```sh
python <skill>/scripts/start_viewer.py <base> --no-open --json
```

Esse comando é a exceção explícita ao resultado único: emite eventos JSONL. O primeiro tem status ready e data.url, data.graph, data.host e data.port. Mantenha o processo ativo e abra a URL se houver browser disponível. Ctrl+C encerra o servidor e produz status stopped. Erros posteriores ao início também podem gerar um evento error. Não espere o processo terminar para obter a URL e não confunda ready com encerramento.

## Exemplos

```sh
python <skill>/scripts/knowledge.py build <base> --json
python <skill>/scripts/knowledge.py search <base> "consulta" --kind entity --json
python <skill>/scripts/prepare_environment.py --check --profile core --json
python <skill>/scripts/validate_graph.py <base> --json
```

Os comandos não concedem permissões além das do host. Preserve as restrições de rede e filesystem e não exponha localhost publicamente. O protocolo não oferece RPC, autenticação remota ou um servidor MCP.
