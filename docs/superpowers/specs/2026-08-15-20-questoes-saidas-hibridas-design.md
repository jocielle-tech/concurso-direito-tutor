# 20 questões e saídas híbridas — design

## Objetivo

Atualizar a skill `concurso-direito-tutor` para testar cada sessão com exatamente 20 questões apresentadas de uma vez, corrigidas somente após as 20 respostas, e reorganizar os materiais persistidos em uma estrutura híbrida pesquisável por assunto e por tipo. Cada trilha deve produzir Markdown, HTML interativo e PDF bem formatado.

## Decisões pedagógicas

- Usar 20 questões no total por sessão, mesmo quando a sessão abranger mais de um tópico.
- Apresentar as 20 questões juntas, sem gabarito ou correção intermediária.
- Aguardar as 20 respostas. Se houver respostas ausentes, indicar os números pendentes. Se o aluno abandonar explicitamente o restante, corrigir apenas o que foi respondido, manter a sessão `in_progress` e não elevar o progresso; a sessão só poderá ser concluída após as 20 respostas.
- Distribuir as questões entre todos os tópicos da sessão segundo relevância, dificuldade e desempenho anterior. Testar cada tópico listado ao menos uma vez.
- Após as respostas, registrar feedback individual das questões 1 a 20, desempenho por tópico e diagnóstico agregado.

## Manifesto e compatibilidade

Novas sessões incluirão `question_target: 20`. Cada feedback incluirá `Tópico: <topic_id>`, usando um ID presente em `session.topic_ids`.

Para uma sessão concluída com `question_target`, o validador exigirá:

- exatamente o total declarado;
- cabeçalhos sequenciais `### Questão 1` até `### Questão 20`, sem lacunas ou duplicações;
- os campos já obrigatórios de feedback e o novo campo `Tópico`;
- pelo menos uma questão vinculada a cada tópico da sessão;
- diagnóstico agregado posterior a todas as questões.

Sessões antigas sem `question_target` continuarão válidas pelas regras legadas. O schema permanece na versão 1; a extensão é opcional para leitura e obrigatória na criação de novas sessões pela skill.

## Estrutura canônica

```text
estudos/<trilha>/
├── trilha.json
├── painel/
│   ├── indice.md
│   ├── progresso.md
│   └── agenda-de-revisoes.md
├── modulos/
│   └── 01-<modulo>/
│       └── topicos/
│           └── 01-<topico>/
│               ├── sessoes/
│               │   └── 001-<sessao>.md
│               ├── resumo.md
│               ├── mapa-mental.md
│               └── questoes.md
├── materiais/
│   ├── resumos.md
│   ├── mapas-mentais.md
│   └── caderno-de-questoes.md
├── revisoes/
│   └── agenda.md
├── apostila/
│   ├── apostila.md
│   ├── apostila.html
│   └── apostila.pdf
└── backups/
```

`trilha.json` permanece como fonte estrutural. Os arquivos em `modulos/.../sessoes/` são as fontes pedagógicas. Resumos, mapas, questões, painéis, agendas e apostilas são derivados e recebem aviso de geração automática.

Os diretórios de módulos e tópicos usam prefixos ordinais estáveis e slugs sanitizados. O manifesto registra o caminho canônico de cada sessão. Reordenações posteriores não renomeiam diretórios já existentes automaticamente.

## Materiais derivados

- `painel/indice.md`: links para módulos, tópicos, sessões e materiais.
- `painel/progresso.md`: progresso global e por módulo/tópico.
- `painel/agenda-de-revisoes.md` e `revisoes/agenda.md`: próximas revisões ordenadas por data e prioridade.
- Arquivos por tópico: extrações de resumo, mapa mental e questões das sessões daquele tópico.
- `materiais/*.md`: consolidações globais por tipo.
- `apostila/apostila.md`: conteúdo completo em ordem do manifesto.

Uma sessão ligada a vários tópicos permanece em um único caminho canônico, definido pelo primeiro tópico listado. Os materiais derivados dos demais tópicos incluem links para essa sessão, evitando duplicar a fonte.

## HTML interativo

`apostila/apostila.html` será autocontido, sem CDN, e terá:

- índice fixo à esquerda em telas grandes e recolhível em telas pequenas;
- âncoras determinísticas para módulos, tópicos e sessões;
- rolagem suave ao clicar no índice;
- destaque do tópico ativo por `IntersectionObserver` durante a rolagem;
- fallback de links navegáveis sem JavaScript;
- links internos verificados e links externos sanitizados;
- atributos de acessibilidade, foco visível e indicação textual além de cor;
- CSS de impressão que remove controles laterais.

## PDF

`apostila/apostila.pdf` será gerado com ReportLab, declarado como dependência obrigatória. `pypdf` e `pdfplumber` serão dependências de validação. O PDF terá capa, sumário com links internos, cabeçalho, rodapé, paginação, hierarquia visual consistente, mapas coloridos, questões, feedbacks, fontes e links clicáveis.

Blocos importantes não devem ser cortados de forma ilegível entre páginas. A validação extrairá texto e metadados com `pypdf` ou `pdfplumber`; a verificação visual renderizará páginas com Poppler quando disponível.

`--check` não exigirá ReportLab porque não gera arquivos. O build normal verificará a dependência antes de substituir qualquer saída e apresentará um comando de instalação quando ela estiver ausente. A geração usará o modo invariável do ReportLab e metadados estáveis para preservar determinismo byte a byte.

## Migração segura

O CLI ganhará `--migrate <trail_dir>`. A skill o executará automaticamente após informar o usuário quando `--check` detectar uma trilha legada.

Fluxo:

1. Ler e validar o formato antigo sem escrita.
2. Criar `backups/migracao-<data-hora>.zip` com manifesto, sessões e outputs anteriores.
3. Montar a nova árvore em diretório temporário dentro da trilha.
4. Atualizar caminhos no manifesto, sem alterar IDs, estados ou conteúdo das sessões.
5. Gerar e validar todos os derivados.
6. Publicar a nova estrutura somente quando todas as etapas passarem.
7. Em falha, remover apenas temporários e manter a estrutura original.

A migração será idempotente: repetir o comando não duplicará sessões, materiais ou backups quando nenhuma migração for necessária.

## Escrita transacional e erros

Markdown, HTML e PDF serão preparados em temporários. Nenhum output anterior será substituído se validação, renderização, PDF ou migração falhar. Mensagens de erro serão controladas, sem traceback para erros de entrada, e identificarão arquivo, sessão e requisito violado.

Links com esquemas inseguros continuarão sem ativação. Todo caminho deverá ser relativo e permanecer contido na trilha.

## Interface CLI

```text
python3 scripts/build_trilha.py [--check | --migrate] <trail_dir>
```

- sem flag: validar e reconstruir todos os derivados;
- `--check`: somente validar, sem criar, migrar ou alterar arquivos;
- `--migrate`: migrar formato legado e reconstruir os derivados.

Em uma trilha legada estruturalmente válida, `--check` retornará código 3 e a mensagem estável `MIGRATION_REQUIRED`, permitindo que a skill diferencie migração de manifesto inválido. Em uma trilha já migrada e válida, retornará zero.

## Atualização da skill e documentação

- Atualizar a descrição do frontmatter de `SKILL.md` com gatilhos de descoberta para 20 questões, organização de materiais, PDF e HTML interativo, sem resumir o fluxo completo no metadata.
- Atualizar o corpo de `SKILL.md` e `references/trilha-e-apostila.md` com a sequência de 20 questões, espera pelas respostas, novo campo de tópico e nova árvore.
- Atualizar `agents/openai.yaml` para apresentar as novas funcionalidades no `short_description` e no `default_prompt`.
- Atualizar README com uma seção visível de novidades, estrutura de pastas, instalação das dependências de PDF e exemplos de uso.
- Mostrar claramente ao usuário, no início ou retomada de uma trilha, que estão disponíveis 20 questões por sessão, materiais organizados, Markdown, HTML interativo e PDF.
- Manter a orientação jurídica de fontes oficiais e feedback individual.

## Estratégia de testes

### RED documental

Executar um cenário com a skill anterior em contexto limpo e registrar que ela não garante 20 questões, espera pelas 20 respostas, nova árvore, PDF ou índice lateral sincronizado.

### Testes automatizados

- exatamente 20 questões e numeração sequencial;
- rejeição de total, lacuna, duplicação ou tópico inválido;
- cobertura de todos os tópicos da sessão;
- compatibilidade de sessão legada sem `question_target`;
- geração da árvore híbrida e avisos de arquivo derivado;
- links e âncoras válidos no Markdown e HTML;
- presença e comportamento do índice lateral e do script de scrollspy;
- geração de PDF, texto extraível, paginação e links;
- `--check` sem escrita;
- migração sem perda, rollback e idempotência;
- outputs byte a byte determinísticos, exceto o backup datado criado apenas na migração.

### Validação integrada

Criar uma trilha temporária, executar uma sessão com 20 respostas, gerar todos os outputs, testar o HTML em navegador, renderizar o PDF em imagens e inspecionar páginas representativas. Executar também a migração de uma cópia da estrutura legada.

## Critérios de aceite

- Nova sessão não pode ser concluída com quantidade diferente de 20 questões.
- Não há correção antecipada sem abandono explícito do restante pelo aluno.
- Todo tópico listado é testado e diagnosticado.
- Materiais são localizáveis por assunto e por tipo sem duplicar fontes canônicas.
- Markdown, HTML e PDF são gerados juntos e permanecem consistentes.
- O HTML possui índice lateral funcional e tópico ativo sincronizado com a rolagem.
- Trilhas antigas migram sem perda e continuam recuperáveis pelo backup.
- Testes, validação da skill e inspeções visuais passam antes da publicação.

## Fora de escopo

- Aplicação web hospedada ou servidor permanente.
- Banco de dados, autenticação ou sincronização em nuvem.
- Editor visual dentro do HTML.
- Alteração automática de conteúdos jurídicos já registrados.
