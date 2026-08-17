# Preparação teórica obrigatória antes das questões

## Objetivo

Toda nova sessão principal começa com uma aula teórica detalhada e adaptativa, exibida sem questões. O aluno precisa confirmar a leitura antes de receber as 20 questões juntas. Correção, diagnóstico, revisão e geração dos materiais continuam somente após as 20 respostas.

## Contrato pedagógico

- Ao iniciar a preparação, registrar a sessão como `in_progress`, sem aumentar o progresso.
- Persistir `question_target: 20` e `theory_briefing_version: 1` nas novas sessões.
- Planejar internamente a cobertura conceitual das 20 questões antes de redigir a aula, sem revelar questões ou gabaritos.
- Usar `## Conteúdo principal` como fonte única da aula, com subtítulos para objetivos, essencial para a prova, fundamentos, regras, exemplos e checklist.
- Esperar confirmação inequívoca de leitura. Dúvidas durante essa pausa são respondidas sem liberar as questões; não há opção de pular a preparação.
- Depois da confirmação, apresentar exatamente 20 questões juntas, aguardar todas as respostas e só então corrigir.

## Persistência e compatibilidade

O marcador `theory_briefing_version` é opcional para preservar sessões legadas. Quando tiver o valor inteiro `1`, sessões `in_progress` ou `completed` precisam conter a preparação estruturada. Valores diferentes são inválidos. Sessões antigas sem o campo continuam válidas e não exigem migração.

A preparação integra a sessão canônica, os resumos por tópico, `materiais/resumos.md` e as apostilas Markdown, HTML e PDF antes das questões. `## Resumo estratégico` permanece uma recapitulação curta de 5 a 8 itens.

## Qualidade e segurança jurídica

A extensão é adaptativa. A teoria deve cobrir todos os conhecimentos avaliados, distinguir regra, exceção, controvérsia e estratégia de prova, citar fontes oficiais e declarar limitações. Não pode antecipar enunciados, gabaritos ou correspondências entre conteúdo e número de questão.
