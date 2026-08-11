# Task 2 — Contrato pedagógico e integração da skill

## Entrega

- Atualizei `SKILL.md` para disparar por tutoria de concursos, trilha de estudo, acompanhamento de progresso, mapas mentais e apostila. O corpo tem 464 palavras, preserva as regras pedagógicas e de fontes existentes e obriga a leitura da referência ao iniciar ou retomar trilha.
- Criei `references/trilha-e-apostila.md` com o contrato de criação/retomada, recalibração por edital, diferenciação de sessão principal e dúvida rápida, fechamento obrigatório, fallback sem filesystem e template Markdown validável pelo gerador.
- Atualizei `agents/openai.yaml` para iniciar uma trilha por `$concurso-direito-tutor` com progresso, mapas mentais e apostila.

## Baseline e forma da correção

O baseline fornecido para esta task registrava que a skill anterior não criava artefatos e omitia resumo, mapa, índice, progresso e apostila. Como a falha era de elementos obrigatórios ausentes, apliquei um contrato estrutural: a referência exige formato de sessão, manifesto, estados, diagnóstico e comandos de validação/build, em vez de lembretes soltos.

## Verificações

```text
$ python3 /Users/testes/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
Skill is valid!

$ wc -w SKILL.md
464 SKILL.md

$ rg -n -i 'TODO|TBD|FIXME|XXX|\{\{[^}]+\}\}' SKILL.md references agents
(sem ocorrências)

$ git diff --check
(sem saída)

$ python3 -B -m unittest discover -s tests -v
Ran 12 tests in 1.184s
OK
```

O scan de placeholders não encontrou marcadores pendentes. As notações `<skill-dir>` e `<trail_dir>` na referência são argumentos literais do comando exigido, não placeholders de implementação.

## Self-review

Revisei que a sessão rápida não persiste nem duplica sessão; somente a sessão fechada marca progresso. A retomada exige `--check` e leitura de `trilha.json`; a trilha provisória preserva sessões ao receber edital. O template contém exatamente título e as seis seções validadas pelo script, 5–8 itens de resumo, mapa com três níveis e as cinco categorias/cores. O fechamento exige feedback por questão, diagnóstico do bloco, fontes, revisão e build posterior; o fallback declara ausência de persistência.

Preocupação conhecida, fora do escopo permitido: o gerador atual lista o índice sem âncoras nos artefatos renderizados, embora a referência passe a exigir índice clicável. Não alterei `scripts/` ou `tests/`, conforme esta task determina; a cobertura atual do gerador permanece verde.

## Correção da revisão — manifesto e feedback por questão

Acrescentei à referência um manifesto JSON mínimo schema v1 completo, com todos os campos do manifesto, módulo, tópico e sessão. A referência agora fixa IDs únicos, estados/fontes aceitos, peso positivo, arquivo de sessão contido na trilha e as invariantes bidirecionais: sessão aponta para módulo/tópicos válidos e todo tópico devolve a referência da sessão.

Também substituí o feedback único por blocos `### Questão N` repetíveis, cada qual contendo resposta, resultado, fundamento, alternativas úteis, tipo de erro, prevenção, fonte e revisão. O template exige `### Diagnóstico agregado` somente depois de todas as questões, com acertos, padrões, prioridade e próxima revisão.

```text
$ python3 /Users/testes/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
Skill is valid!

$ wc -w SKILL.md
464 SKILL.md

$ rg -n -i 'TODO|TBD|FIXME|XXX|\{\{[^}]+\}\}' SKILL.md references agents
(sem ocorrências)

$ git diff --check
(sem saída)

$ python3 -B -m unittest discover -s tests -v
Ran 12 tests in 1.181s
OK
```

Self-review: o exemplo do manifesto mantém `topic.sessions` e `session.topic_ids` coerentes, usa uma sessão `not_started` para não exigir conteúdo concluído e instrui a criar seu arquivo referido. O `SKILL.md` não foi alterado e permanece abaixo de 500 palavras. Não alterei scripts nem testes.
