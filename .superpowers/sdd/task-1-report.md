# Task 1 — Relatório do gerador cumulativo

## Escopo entregue

- `tests/test_build_trilha.py`: suíte `unittest` de integração do CLI.
- `scripts/build_trilha.py`: validador e gerador determinístico de `apostila.md` e `apostila.html`.

O gerador aceita `python3 scripts/build_trilha.py [--check] <trail_dir>`. Ele valida o manifesto schema v1, IDs, referências, pesos, caminhos de sessão e a estrutura de sessões concluídas antes de renderizar. A renderização gera índice, progresso global/por módulo, régua Markdown, legenda acessível das cinco categorias do mapa, HTML com CSS embutido e estilos de impressão. A saída HTML escapa conteúdo bruto e somente ativa links `http`, `https` e `mailto`.

## TDD — RED registrado

Após criar `tests/test_build_trilha.py` e antes de existir qualquer código de produção, executei:

```text
$ python3 -m unittest discover -s tests -v
test_build_creates_accessible_index_legend_and_printable_outputs (...) ... FAIL
test_check_validates_without_creating_or_changing_outputs (...) ... FAIL
test_escapes_raw_html_and_disables_javascript_links (...) ... FAIL
test_invalid_manifests_leave_existing_outputs_untouched (...) ... ok
test_provisional_manifest_calculates_weighted_progress (...) ... FAIL
test_recalibrated_edital_trail_is_identified (...) ... FAIL
test_same_input_produces_byte_identical_outputs (...) ... FAIL

AssertionError: 2 != 0 : ... can't open file '.../scripts/build_trilha.py': [Errno 2] No such file or directory

Ran 7 tests in 0.395s
FAILED (failures=6)
```

Esse era o resultado esperado: o CLI de produção ainda não existia. O único caso `ok` era o de entradas inválidas, pois a ausência do executável também não altera as saídas-sentinela; os demais casos falharam por ausência do recurso solicitado.

## Implementação

Criei `scripts/build_trilha.py` após o RED. Pontos principais:

- validação total antes de renderizar/escrever e uso de arquivo temporário no mesmo diretório para cada substituição de saída;
- `--check` faz somente a validação e não toca nos artefatos;
- cálculo ponderado do progresso e ordem de sessões preservada a partir do manifesto;
- validação de seis seções obrigatórias, 5–8 itens no resumo e mapa com categorias permitidas e no máximo três níveis;
- HTML sem injeção de tags brutas e sem `href` ativo para `javascript:`.

## GREEN e verificações finais

Executei:

```text
$ git diff --check && python3 -m py_compile scripts/build_trilha.py && python3 -m unittest discover -s tests -v
test_build_creates_accessible_index_legend_and_printable_outputs (...) ... ok
test_check_validates_without_creating_or_changing_outputs (...) ... ok
test_escapes_raw_html_and_disables_javascript_links (...) ... ok
test_invalid_manifests_leave_existing_outputs_untouched (...) ... ok
test_provisional_manifest_calculates_weighted_progress (...) ... ok
test_recalibrated_edital_trail_is_identified (...) ... ok
test_same_input_produces_byte_identical_outputs (...) ... ok

Ran 7 tests in 0.839s
OK
```

`git diff --check` e `py_compile` também concluíram sem saída/erros.

## Cobertura dos requisitos

1. Progresso provisório ponderado 1 + 3 com um tópico concluído: 25%.
2. `--check` não cria artefatos ausentes nem altera artefatos existentes.
3. Saídas incluem índice, régua Markdown, atributos ARIA, CSS/print e cinco cores/categorias rotuladas.
4. Dois builds com a mesma entrada produzem bytes idênticos.
5. JSON inválido, peso não positivo, ID duplicado, referência inexistente, seção ausente e categoria inválida retornam erro e preservam saídas válidas.
6. Tags HTML brutas são escapadas e links `javascript:` não são `href` ativos.
7. Trilhas de edital recalibradas mostram `Trilha recalibrada`.

## Self-review

Revisei o fluxo de escrita: validação e geração de ambas as strings ocorrem antes de qualquer substituição das saídas; cada escrita passa por temporário no diretório da trilha. Revisei referências em ambos os sentidos (sessão→módulo/tópico e tópico→sessão), contenção de caminhos via `resolve`/`relative_to`, e a sanitização de HTML/URLs. Não identifiquei problemas bloqueadores no escopo da Task 1.

Limitação consciente: o renderizador HTML é um conversor Markdown mínimo, voltado à estrutura determinística exigida (títulos, parágrafos, itens e links seguros); ele não pretende implementar todo o padrão Markdown.

## Correção pós-revisão — pesos e escape de URLs

### RED registrado

Foram adicionados, antes de qualquer alteração em `scripts/build_trilha.py`, três testes de regressão: pesos finitos de `1e308` devem gerar 50%; `NaN`, `Infinity` e `-Infinity` devem ser rejeitados preservando as saídas; e o query string `?a=1&b=2` deve aparecer em um `href` com um único escape de `&`.

```text
$ python3 -m unittest -v tests.test_build_trilha.BuildTrilhaTests.test_extreme_finite_weights_calculate_progress_without_overflow tests.test_build_trilha.BuildTrilhaTests.test_nonfinite_json_weights_are_rejected_without_changing_outputs tests.test_build_trilha.BuildTrilhaTests.test_html_url_query_escapes_ampersand_once
test_extreme_finite_weights_calculate_progress_without_overflow (...) ... FAIL
test_nonfinite_json_weights_are_rejected_without_changing_outputs (...) ... FAIL
test_html_url_query_escapes_ampersand_once (...) ... FAIL

ValueError: cannot convert float NaN to integer
AssertionError: 'peso deve ser finito' not found in traceback/output anterior
AssertionError: 'href="https://exemplo/?a=1&amp;b=2"' not found; saída continha '&amp;amp;'

Ran 3 tests in 0.365s
FAILED (failures=5; os três subcasos não finitos falharam)
```

### Implementação e GREEN

- O parser JSON agora usa `parse_float=Decimal`, preservando pesos decimais grandes sem overflow binário, e recusa constantes JSON não finitas por `parse_constant`.
- A validação aceita somente `int` ou `Decimal` finito, positivo e não booleano.
- `safe_inline` agora encontra links no texto bruto, escapa texto/rótulo/URL separadamente e só então monta a âncora. Isso evita reescapar `&amp;`.

```text
$ python3 -m unittest -v [os 3 testes de regressão]
Ran 3 tests in 0.393s
OK

$ git diff --check && python3 -B -m py_compile scripts/build_trilha.py && python3 -B -m unittest discover -s tests -v
Ran 10 tests in 1.115s
OK
```

`git diff --check` e `py_compile` não emitiram erros. A suíte completa inclui os três regressivos e os sete testes originais.

### Self-review da correção

Revisei que `Decimal` é introduzido já no parse, portanto `1e308 + 1e308` não usa soma `float`; para o caso coberto, o cálculo ponderado fica exato e retorna 50%. `NaN`, `Infinity` e `-Infinity` são interceptados antes da validação/renderização, preservando as saídas existentes. No escape de links, cada fragmento é escapado uma única vez, e protocolos não permitidos continuam sem âncora ativa. Não identifiquei pendências bloqueadoras.

## Correção pós-revisão — tipo estrito de `schema_version`

Foram criados, antes da alteração de produção, testes separados para `schema_version: true` e `schema_version: 1.0`.

```text
$ python3 -m unittest -v tests.test_build_trilha.BuildTrilhaTests.test_boolean_schema_version_is_rejected tests.test_build_trilha.BuildTrilhaTests.test_decimal_schema_version_is_rejected
test_boolean_schema_version_is_rejected (...) ... FAIL
test_decimal_schema_version_is_rejected (...) ... FAIL

AssertionError: 0 == 0

Ran 2 tests in 0.147s
FAILED (failures=2)
```

A validação agora exige `type(schema_version) is int` antes de comparar o valor a `1`; isso exclui explicitamente `bool` e o `Decimal` que representa o número JSON `1.0`.

```text
$ python3 -B -m unittest -v [2 testes focados]
Ran 2 tests in 0.103s
OK

$ git diff --check && python3 -B -m py_compile scripts/build_trilha.py && python3 -B -m unittest discover -s tests -v
Ran 12 tests in 1.202s
OK
```

`git diff --check` e `py_compile` concluíram sem erros. Self-review: `type(...) is int` é intencionalmente mais estrito que `isinstance(..., int)`, pois `bool` é subclasse de `int` em Python; nenhuma outra versão do schema passa pela igualdade numérica implícita.
