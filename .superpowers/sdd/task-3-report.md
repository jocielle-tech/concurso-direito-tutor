# Task 3 — Validação integrada e refinamento

## Escopo entregue

- `tests/test_build_trilha.py`: teste de regressão para índice clicável com âncoras determinísticas de módulo e sessão em Markdown e HTML.
- `scripts/build_trilha.py`: renderização do índice como links e destinos estáveis, preservando a ordem do manifesto e escapando IDs arbitrários em fragmentos de URL.

## RED → GREEN

Antes de alterar o gerador, acrescentei `test_index_links_to_deterministic_module_and_session_anchors` e executei apenas esse teste:

```text
$ python3 -m unittest tests.test_build_trilha.BuildTrilhaTests.test_index_links_to_deterministic_module_and_session_anchors
FAIL
AssertionError: '[Direito Constitucional](#modulo-constitucional)' not found
```

O índice existente continha apenas texto, sem links ou âncoras. Em seguida, o gerador passou a produzir:

- Markdown: links `[Módulo](#modulo-<id>)` e `[Sessão](#sessao-<id>)`, com destinos `<a id="..."></a>`;
- HTML: links `href="#..."`, título do módulo com `id` e título da sessão com `id`;
- fragmentos determinísticos por `anchor_id()`, que preserva IDs usuais e faz percent-encoding de caracteres inseguros.

O mesmo teste então passou. A hierarquia HTML agora é `h2` para módulo, `h3` para sessão e `h4` para as seções internas da sessão.

## Cenário integrado em diretório temporário

Usei a skill atualizada e sua referência em `/tmp/task-3-trilha-validation` (fora do repositório). O cenário começou como trilha provisória de Direito Constitucional, com uma sessão concluída sobre controle difuso e três questões respondidas.

Verificações confirmadas após build e `--check`:

1. Foram criados `trilha.json`, `sessoes/001-controle-difuso.md`, `apostila.md` e `apostila.html`.
2. O resumo tem 6 itens; o mapa contém as cinco categorias permitidas.
3. As três seções `Questão 1` a `Questão 3` contêm feedback individual; há `Diagnóstico agregado` com 2/3 (67%).
4. Índice, progresso global e progresso de módulo constam da apostila; no estado provisório o valor ponderado é 38%.
5. Os links e destinos do índice estão presentes nos dois artefatos.

Para a dúvida rápida, a simulação respondeu somente no chat e comparou o hash do manifesto e o total de sessões: permaneceram dois registros, incluindo a sessão `s001` concluída, sem duplicação. `--check` continuou válido.

Depois, simulei a chegada do edital, alterando apenas origem, identificação do concurso/banca, pesos e `recalibrated: true`. Um novo build e `--check` confirmaram que `s001`, seu estado e seu arquivo permaneceram exatamente os mesmos (hash `ad6bcd5c...e271469`), enquanto a apostila exibiu o banner `Trilha recalibrada` e o progresso passou para 70%.

## Verificações finais

```text
$ python3 /Users/testes/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
Skill is valid!

$ python3 -B -m py_compile scripts/build_trilha.py tests/test_build_trilha.py
(sem erros)

$ python3 -B -m unittest discover -s tests -v
Ran 13 tests in 1.304s
OK

$ git diff --check
(sem saída)
```

Também executei `scripts/build_trilha.py` e `scripts/build_trilha.py --check` tanto antes quanto depois da recalibração no diretório temporário.

## Self-review

Revisei que os destinos de módulo não dependem de título humano (portanto não mudam por tradução ou título duplicado) e os de sessão dependem do ID único já validado. O percent-encoding evita que um ID com espaço ou caractere reservado quebre o atributo HTML ou o fragmento; títulos continuam escapados na saída HTML. As sessões seguem a ordem do manifesto dentro do respectivo módulo. Não identifiquei bloqueadores no escopo.

Limitação consciente: o manifesto não registra a contagem esperada de questões, então o validador não pode inferir se faltou feedback para uma questão que não está escrita no arquivo. O cenário integrado conferiu explicitamente as três questões solicitadas e o diagnóstico; tornar essa contagem uma regra geral exigiria ampliar o schema, fora do escopo desta task.
