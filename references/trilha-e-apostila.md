# Trilha, sessões e apostila

## Criar ou retomar

1. Criar automaticamente `estudos/<slug>/`, com `trilha.json` schema v1 e `sessoes/`, ao iniciar uma trilha persistente. Usar slug estável, minúsculo e separado por hífens.
2. Antes de retomar ou considerar arquivos existentes válidos, executar `python3 <skill-dir>/scripts/build_trilha.py --check <trail_dir>` e ler `trilha.json`. Corrigir a trilha somente após entender manifesto, módulos, tópicos, sessões e estados.
3. Sem edital, criar `source: "provisional"` e pesos por relevância geral. Quando chegar o edital, recalibrar para `source: "edital"`, ajustar módulos, tópicos e pesos, definir `recalibrated: true` e preservar sessões, arquivos e seus estados já registrados.

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
- Resposta: <resposta do aluno>
- Resultado: <correta/incorreta e gabarito>
- Fundamento: <regra, dispositivo ou precedente>
- Alternativas úteis: <por que as opções relevantes acertam ou erram>
- Tipo de erro: <conceito/exceção/leitura/desatualização/estratégia>
- Prevenção: <ação verificável>
- Fonte: <link oficial>
- Revisão: <data ou intervalo>

## Fontes
- <fonte oficial, link e data de consulta>

## Próxima revisão
<data ou intervalo e tarefa>
```

Manter 5–8 itens em **Resumo estratégico**. Limitar o mapa a três níveis e usar somente as categorias/paleta: `conceito` azul `#2563EB`, `regra` verde `#16A34A`, `excecao` amarelo `#D97706`, `pegadinha` vermelho `#DC2626`, `jurisprudencia` roxo `#7C3AED`.

No fechamento, acrescentar no chat o diagnóstico do bloco: acertos, padrões de erro, prioridade e próxima revisão. Então executar `python3 <skill-dir>/scripts/build_trilha.py <trail_dir>` depois de cada sessão concluída. A apostila deve reunir as sessões na ordem do manifesto, ter índice clicável, progresso global e por módulo, fontes e todos os feedbacks.

## Sem filesystem

Entregar o mesmo fechamento no chat, declarar explicitamente que não houve persistência e não alegar atualização de trilha, progresso ou apostila.
