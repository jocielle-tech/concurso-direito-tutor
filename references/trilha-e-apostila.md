# Trilha, sessões e apostila

## Criar ou retomar

1. Criar automaticamente `estudos/<slug>/`, com `trilha.json` schema v1 e `sessoes/`, ao iniciar uma trilha persistente. Usar slug estável, minúsculo e separado por hífens.
2. Antes de retomar ou considerar arquivos existentes válidos, executar `python3 <skill-dir>/scripts/build_trilha.py --check <trail_dir>` e ler `trilha.json`. Corrigir a trilha somente após entender manifesto, módulos, tópicos, sessões e estados.
3. Sem edital, criar `source: "provisional"` e pesos por relevância geral. Quando chegar o edital, recalibrar para `source: "edital"`, ajustar módulos, tópicos e pesos, definir `recalibrated: true` e preservar sessões, arquivos e seus estados já registrados.

Criar o manifesto mínimo abaixo e criar também o arquivo indicado em `file`; ele é válido para uma sessão ainda não iniciada:

```json
{
  "schema_version": 1,
  "title": "Trilha de Direito Constitucional",
  "slug": "direito-constitucional",
  "source": "provisional",
  "exam": null,
  "banca": null,
  "recalibrated": false,
  "modules": [
    {
      "id": "constitucional",
      "title": "Direito Constitucional",
      "topics": [
        {
          "id": "controle-difuso",
          "title": "Controle difuso",
          "weight": 1,
          "status": "not_started",
          "sessions": ["s001"]
        }
      ]
    }
  ],
  "sessions": [
    {
      "id": "s001",
      "title": "Controle difuso",
      "date": "2026-08-10",
      "status": "not_started",
      "module_id": "constitucional",
      "topic_ids": ["controle-difuso"],
      "file": "sessoes/001-controle-difuso.md"
    }
  ]
}
```

Manter IDs de módulos, tópicos e sessões únicos. Usar somente estados `not_started`, `in_progress` e `completed`, pesos numéricos positivos e `source` `provisional` ou `edital`. Manter referências nos dois sentidos: cada `session.module_id` deve existir; cada item de `session.topic_ids` deve pertencer a esse módulo e listar o ID da sessão em `topic.sessions`; e cada ID em `topic.sessions` deve existir em `sessions`. Manter `file` relativo, contido na trilha e existente.

## Sessão principal

Tratar pergunta pontual como dúvida rápida: responder no chat sem criar arquivo, sessão ou progresso. Tratar bloco de estudo como sessão principal. Somente ao seu fechamento marcar sessão e tópicos como `completed`; sessões `not_started` ou `in_progress` não elevam progresso.

Para cada sessão concluída, criar/atualizar uma única entrada em `sessions`, vinculá-la aos tópicos correspondentes e usar exatamente este formato:

```markdown
# <sessions[].title>

## Conteúdo principal
<explicação, lei seca, exemplos e pegadinhas>

## Resumo estratégico
- <item 1>
- <item 2>
- <item 3>
- <item 4>
- <item 5>

## Mapa mental
- [conceito] <ideia central>
  - [regra] <aplicação>
    - [excecao] <limite>
- [pegadinha] <erro previsível>
- [jurisprudencia] <precedente>

## Questões e feedback
### Questão 1
- Resposta: <resposta do aluno>
- Resultado: <correta/incorreta e gabarito>
- Fundamento: <regra, dispositivo ou precedente>
- Alternativas úteis: <por que as opções relevantes acertam ou erram>
- Tipo de erro: <conceito/exceção/leitura/desatualização/estratégia>
- Prevenção: <ação verificável>
- Fonte: <link oficial>
- Revisão: <data ou intervalo>

### Questão N
- Resposta: <resposta do aluno>
- Resultado: <correta/incorreta e gabarito>
- Fundamento: <regra, dispositivo ou precedente>
- Alternativas úteis: <por que as opções relevantes acertam ou erram>
- Tipo de erro: <conceito/exceção/leitura/desatualização/estratégia>
- Prevenção: <ação verificável>
- Fonte: <link oficial>
- Revisão: <data ou intervalo>

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

Repetir o bloco `### Questão N` para cada questão respondida antes de escrever o diagnóstico agregado. Manter 5–8 itens em **Resumo estratégico**. Limitar o mapa a três níveis e usar somente as categorias/paleta: `conceito` azul `#2563EB`, `regra` verde `#16A34A`, `excecao` amarelo `#D97706`, `pegadinha` vermelho `#DC2626`, `jurisprudencia` roxo `#7C3AED`.

No fechamento, acrescentar no chat o diagnóstico do bloco: acertos, padrões de erro, prioridade e próxima revisão. Então executar `python3 <skill-dir>/scripts/build_trilha.py <trail_dir>` depois de cada sessão concluída. A apostila deve reunir as sessões na ordem do manifesto, ter índice clicável, progresso global e por módulo, fontes e todos os feedbacks.

## Sem filesystem

Entregar o mesmo fechamento no chat, declarar explicitamente que não houve persistência e não alegar atualização de trilha, progresso ou apostila.
