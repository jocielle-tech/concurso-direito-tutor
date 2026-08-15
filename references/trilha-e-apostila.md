# Trilha, sessão de 20 questões e apostila

## Criar, retomar e migrar

Criar `estudos/<slug>/` com `trilha.json` schema v1. Usar IDs únicos, pesos positivos, `source` `provisional` ou `edital`, estados `not_started`, `in_progress` e `completed`, e vínculos nos dois sentidos entre sessão, módulo e tópico.

Para retomar, executar primeiro:

```bash
python3 <skill-dir>/scripts/build_trilha.py --check <trail_dir>
```

Se stderr for exatamente `MIGRATION_REQUIRED`, explicar que a trilha antiga será reorganizada com backup e executar:

```bash
python3 <skill-dir>/scripts/build_trilha.py --migrate <trail_dir>
```

Só continuar após a migração terminar. Ela preserva IDs, estados e conteúdo, cria ZIP em `backups/` e é idempotente. Qualquer outro erro de `--check` exige correção antes de escrever arquivos.

Use, para sessão nova, um manifesto com `question_target: 20` e caminho canônico:

```json
{
  "schema_version": 1,
  "title": "Trilha de Direito Constitucional",
  "slug": "direito-constitucional",
  "source": "provisional",
  "exam": null,
  "banca": null,
  "recalibrated": false,
  "modules": [{
    "id": "constitucional",
    "title": "Direito Constitucional",
    "topics": [{
      "id": "controle-difuso",
      "title": "Controle difuso",
      "weight": 1,
      "status": "not_started",
      "sessions": ["s001"]
    }]
  }],
  "sessions": [{
    "id": "s001",
    "title": "Controle difuso",
    "date": "<AAAA-MM-DD>",
    "status": "not_started",
    "module_id": "constitucional",
    "topic_ids": ["controle-difuso"],
    "question_target": 20,
    "file": "modulos/01-direito-constitucional/topicos/01-controle-difuso/sessoes/001-controle-difuso.md"
  }]
}
```

Sessões legadas sem `question_target` continuam legíveis; não adicionar o campo retroativamente fora da migração. Sem edital, usar `source: "provisional"`; quando ele chegar, recalibrar módulos e pesos sem apagar sessões ou estados.

## Contrato da sessão principal

1. Anunciar as 20 questões, os materiais organizados, o progresso e as três apostilas: Markdown, HTML interativo e PDF.
2. Definir ou criar uma sessão com `question_target: 20`, abrangendo cada ID em `topic_ids` ao menos uma vez.
3. Ensinar o núcleo e apresentar exatamente as **20 questões, de 1 a 20, em uma única prática**, sem gabarito, justificativa de alternativa ou correção intermediária.
4. Esperar as 20 respostas. Se faltarem itens, informar apenas os números pendentes e esperar. Não encerrar nem publicar diagnóstico antecipado.
5. Se o aluno abandonar explicitamente o restante, corrigir somente as respostas recebidas, registrar a sessão como `in_progress`, não concluir tópicos e não aumentar o progresso. A sessão só vira `completed` com as 20 respostas.
6. Depois das 20 respostas, registrar feedbacks sequenciais de 1 a 20, um diagnóstico agregado posterior e a próxima revisão; então reconstruir todas as saídas.

Para sessão concluída, usar o formato abaixo. Todo `Tópico` deve ser um ID de `session.topic_ids`; cada tópico da sessão precisa aparecer em pelo menos uma questão.

```markdown
# <sessions[].title>

## Conteúdo principal
<explicação, lei seca, exemplos e pegadinhas>

## Resumo estratégico
- <5 a 8 itens>

## Mapa mental
- [conceito] <ideia central>
  - [regra] <aplicação>
    - [excecao] <limite>
- [pegadinha] <erro previsível>
- [jurisprudencia] <precedente>

## Questões e feedback
### Questão 1
- Tópico: <topic_id>
- Resposta: <resposta do aluno>
- Resultado: <correta/incorreta e gabarito>
- Fundamento: <regra, dispositivo ou precedente>
- Alternativas úteis: <por que as opções relevantes acertam ou erram>
- Tipo de erro: <conceito/exceção/leitura/desatualização/estratégia>
- Prevenção: <ação verificável>
- Fonte: <link oficial>
- Revisão: <data ou intervalo>

<!-- repetir, sem lacunas, até ### Questão 20 -->

### Diagnóstico agregado
- Acertos: <quantidade, total e percentual>
- Padrões de erro: <padrões observados>
- Prioridade: <tema ou habilidade prioritária>
- Próxima revisão: <data ou intervalo e tarefa>

## Fontes
- <fonte oficial, link e data de consulta>

## Próxima revisão
<data ou intervalo e tarefa>
```

Usar no máximo três níveis no mapa e somente: `conceito` azul `#2563EB`, `regra` verde `#16A34A`, `excecao` amarelo `#D97706`, `pegadinha` vermelho `#DC2626` e `jurisprudencia` roxo `#7C3AED`.

## Árvore híbrida e saídas

`trilha.json` e `modulos/.../sessoes/*.md` são fontes canônicas. Painéis, materiais, agendas e apostilas são derivados; não editá-los manualmente. Uma sessão multi-tópico tem uma só fonte no primeiro tópico; os demais tópicos apontam para ela, sem duplicá-la.

```text
estudos/<trilha>/
├── trilha.json
├── painel/{indice,progresso,agenda-de-revisoes}.md
├── modulos/01-<modulo>/topicos/01-<topico>/
│   ├── sessoes/001-<sessao>.md
│   ├── resumo.md
│   ├── mapa-mental.md
│   └── questoes.md
├── materiais/{resumos,mapas-mentais,caderno-de-questoes}.md
├── revisoes/agenda.md
├── apostila/{apostila.md,apostila.html,apostila.pdf}
└── backups/
```

Após um fechamento concluído, executar:

```bash
python3 <skill-dir>/scripts/build_trilha.py <trail_dir>
```

Isso gera as três leituras da mesma fonte: `apostila.md` para versionamento e leitura rápida; `apostila.html` autocontida, com índice lateral sincronizado à rolagem, navegação sem JavaScript e estilos de impressão; e `apostila.pdf` paginada para estudo/impressão. O build é transacional: se uma saída falhar, preservar as versões anteriores.

## Sem filesystem

Aplicar a mesma sequência no chat, declarar que não houve persistência e não alegar atualização de trilha, progresso ou apostila.
