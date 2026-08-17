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

Ao começar uma sessão nova, usar `status: "in_progress"`, `question_target: 20`, `theory_briefing_version: 1` e caminho canônico:

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
      "status": "in_progress",
      "sessions": ["s001"]
    }]
  }],
  "sessions": [{
    "id": "s001",
    "title": "Controle difuso",
    "date": "<AAAA-MM-DD>",
    "status": "in_progress",
    "module_id": "constitucional",
    "topic_ids": ["controle-difuso"],
    "question_target": 20,
    "theory_briefing_version": 1,
    "file": "modulos/01-direito-constitucional/topicos/01-controle-difuso/sessoes/001-controle-difuso.md"
  }]
}
```

Sessões legadas sem `question_target` continuam legíveis. Sessões legadas sem `theory_briefing_version` também continuam válidas e não precisam de migração; não adicionar esses campos retroativamente. Sem edital, usar `source: "provisional"`; quando ele chegar, recalibrar módulos e pesos sem apagar sessões ou estados.

## Contrato da sessão principal

1. Anunciar a preparação teórica obrigatória, as 20 questões, os materiais organizados, o progresso e as três apostilas: Markdown, HTML interativo e PDF.
2. Definir ou retomar a sessão como `in_progress`, com `question_target: 20` e `theory_briefing_version: 1`, abrangendo cada ID em `topic_ids` ao menos uma vez. Não elevar o progresso.
3. Planejar uma matriz interna de cobertura para as 20 questões e redigir uma preparação teórica detalhada, adaptada ao nível e à complexidade do tema.
4. Exibir somente a preparação teórica. Ela deve ensinar todo o substrato necessário e não revelar enunciados, alternativas ou gabaritos, nem associar conteúdo a números de questões.
5. Esperar confirmação explícita de leitura. Responder dúvidas sem avançar e pedir a confirmação novamente; não permitir que uma sessão principal pule essa etapa.
6. Após a confirmação, apresentar exatamente as **20 questões, de 1 a 20, em uma única prática**, sem gabarito, justificativa de alternativa ou correção intermediária.
7. Esperar as 20 respostas. Se faltarem itens, informar apenas os números pendentes e esperar. Se o aluno abandonar explicitamente o restante, corrigir somente as respostas recebidas, manter `in_progress`, não concluir tópicos e não aumentar o progresso.
8. Depois das 20 respostas, registrar feedbacks sequenciais de 1 a 20, um diagnóstico agregado posterior e a próxima revisão; então reconstruir todas as saídas e marcar a sessão como `completed`.

Para sessão concluída, usar o formato abaixo. Todo `Tópico` deve ser um ID de `session.topic_ids`; cada tópico da sessão precisa aparecer em pelo menos uma questão.

```markdown
# <sessions[].title>

## Conteúdo principal

### Objetivos de aprendizagem
<o que o candidato dominará ao terminar a leitura>

### Essencial para a prova
<núcleo de maior incidência e distinções indispensáveis>

### Fundamentos e conceitos
<conceitos, base normativa e vocabulário técnico>

### Regras, requisitos e efeitos
<regra, elementos, competências, procedimentos, prazos e efeitos aplicáveis>

<!-- Acrescentar exceções, controvérsias, jurisprudência e aprofundamento quando pertinentes. -->

### Exemplos e pegadinhas
<casos concretos, confusões previsíveis e estratégia de prova>

### Checklist antes das questões
<itens verificáveis que cobrem a matriz interna sem antecipar respostas>

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

Quando `theory_briefing_version` for `1`, os seis subtítulos centrais acima são obrigatórios, precisam estar nessa ordem e ter conteúdo. A extensão é adaptativa; os blocos adicionais de exceções, controvérsias, jurisprudência e aprofundamento entram quando forem pertinentes. O mesmo `Conteúdo principal` alimenta a tela, o arquivo canônico, os resumos por tópico e as três apostilas.

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
├── assets/mapas/<topico>-<hash>/<source_hash>.png
└── backups/
```

Após um fechamento concluído, executar:

```bash
python3 <skill-dir>/scripts/build_trilha.py <trail_dir>
```

Isso gera as três leituras da mesma fonte: `apostila.md` para versionamento e leitura rápida; `apostila.html` autocontida, com índice lateral sincronizado à rolagem, navegação sem JavaScript e estilos de impressão; e `apostila.pdf` paginada para estudo/impressão. O build é transacional: se uma saída falhar, preservar as versões anteriores.

## Mapa algorítmico nativo

O mapa textual em `## Mapa mental` é a fonte jurídica verificável; o PNG é um complemento visual. Apenas tópicos `completed` com sessões concluídas e mapa textual participam da geração. Sessões `not_started` ou `in_progress` nunca geram imagem.

Para cada tópico recém-concluído:

1. Executar `python3 <skill-dir>/scripts/prepare_visual_map.py <trail_dir> --topic <topic_id>`.
2. Se `status` for `ready`, reutilizar o PNG em cache e não chamar geração.
3. Se `status` for `missing` ou `invalid`, usar **REQUIRED SUB-SKILL: imagegen** em modo nativo com o `prompt` retornado.
4. Inspecionar a imagem contra `algorithm_lines` e `alt_text`: fluxograma em português, paisagem 3:2 aproximada, composição Dashboard Moderno e rótulos jurídicos concisos e verbatim. Aceitar somente PNG legível e sem conteúdo inventado, marca-d’água ou texto ilegível. Repetir uma vez somente para corrigir erro concreto.
5. Copiar o PNG aprovado para `expected_path`; nunca deixar asset referenciado apenas no diretório global de imagens geradas.
6. Não usar fallback CLI, não solicitar `OPENAI_API_KEY` e não chamar serviço externo.
7. Se a ferramenta nativa estiver indisponível ou a segunda imagem continuar incorreta, não salvar a imagem e executar o build com fallback determinístico.

O utilitário retorna um `expected_path` relativo, como `assets/mapas/<topico-normalizado>-<hash-curto>/<source_hash>.png`. O `source_hash` inclui o tópico, a versão visual, a proporção 3:2 e o mapa textual agregado das sessões concluídas: mesma fonte reutiliza cache; alteração do conteúdo cria novo arquivo sem apagar caches anteriores. A versão `dashboard-modern-v3` cria uma chave nova sem remover a v2. O título atual do tópico é renderizado fora dos pixels pelo HTML/PDF e não entra no prompt nem no hash, portanto renomeá-lo não gera imagem nova.

Preservar os marcadores algorítmicos no mapa textual para orientar a imagem e o fallback: `ENTRADA`, `SE`, `ENTÃO`, `SENÃO`, `RESULTADO` e `ALERTA`. O HTML autocontido incorpora PNG aprovado em Base64, mantém alternativa textual verificável e oferece ampliação; o PDF usa os mesmos bytes, preserva o algoritmo pesquisável e aplica o fluxo textual quando não houver imagem válida.

## Sem filesystem

Aplicar a mesma sequência no chat, declarar que não houve persistência e não alegar atualização de trilha, progresso ou apostila.
