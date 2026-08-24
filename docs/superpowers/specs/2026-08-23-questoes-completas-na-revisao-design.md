# Questões completas na revisão da apostila

## Objetivo

Cada correção de uma nova sessão principal deve preservar a pergunta que foi apresentada ao aluno. O enunciado integral e todas as alternativas aparecem antes da resposta e do feedback, tornando a sessão canônica, os cadernos de questões e as apostilas autossuficientes para revisão.

## Contrato pedagógico

- A preparação teórica e a confirmação de leitura continuam precedendo as 20 questões.
- As 20 questões continuam sendo apresentadas juntas e sem gabarito.
- A correção continua ocorrendo somente após o recebimento das 20 respostas, salvo abandono explícito previsto no contrato atual.
- Ao registrar cada correção, copiar fielmente o enunciado e todas as alternativas apresentadas ao aluno.
- Não modificar o texto da pergunta durante a correção. Explicações, ressalvas e atualizações pertencem ao bloco de feedback.
- O feedback continua analisando a resposta do aluno, o gabarito, o fundamento, as alternativas relevantes, o tipo de erro, a prevenção, a fonte e a revisão.

## Formato canônico

Novas sessões usam `question_content_version: 1`. Em uma sessão concluída, cada uma das 20 questões adota esta estrutura:

```markdown
### Questão 1
- Tópico: controle-difuso

#### Pergunta
<enunciado integral>

#### Alternativas
- A) <alternativa A>
- B) <alternativa B>
- C) <alternativa C>
- D) <alternativa D>
- E) <alternativa E>

#### Resposta e feedback
- Resposta: <resposta do aluno>
- Resultado: <correta/incorreta e gabarito>
- Fundamento: <regra, dispositivo ou precedente>
- Alternativas úteis: <por que as opções relevantes acertam ou erram>
- Tipo de erro: <conceito/exceção/leitura/desatualização/estratégia>
- Prevenção: <ação verificável>
- Fonte: <link oficial>
- Revisão: <data ou intervalo>
```

`Alternativas` significa todas as opções efetivamente apresentadas, sem presumir cinco itens. Questões de certo ou errado, por exemplo, registram as duas opções correspondentes. Cada alternativa precisa ter um rótulo e conteúdo não vazio.

## Validação e compatibilidade

O marcador `question_content_version` é opcional para preservar sessões legadas. Quando presente, deve ser o inteiro `1`. Em sessões `completed` com essa versão, o validador exige, em cada uma das 20 questões:

- um único subtítulo `Pergunta`, com conteúdo não vazio;
- um único subtítulo `Alternativas`, posterior à pergunta, com pelo menos duas opções rotuladas e não vazias;
- um único subtítulo `Resposta e feedback`, posterior às alternativas;
- os campos de feedback já exigidos dentro do bloco final;
- nenhuma seção estrutural duplicada ou fora da ordem.

Sessões `in_progress` podem conter somente a preparação teórica enquanto aguardam leitura ou respostas. Sessões antigas sem `question_content_version` continuam válidas e não exigem migração nem alteração retroativa.

## Fluxo de dados e saídas

O arquivo `modulos/.../topicos/.../sessoes/<sessao>.md` permanece como fonte canônica. O bloco completo de cada questão é copiado sem perda para:

- `modulos/.../topicos/.../questoes.md`;
- `materiais/caderno-de-questoes.md`;
- `apostila/apostila.md`;
- `apostila/apostila.html`;
- `apostila/apostila.pdf`.

O HTML mostra três áreas visualmente distintas dentro de cada cartão: pergunta, alternativas e resposta com feedback. O PDF mantém o título da questão junto do início do enunciado sempre que houver espaço, apresenta as alternativas em seguida e coloca a correção em um cartão destacado. O Markdown conserva a estrutura canônica legível.

Não haverá banco de questões separado, cópia manual em arquivos derivados nem dependência externa nova.

## Documentação

O `SKILL.md`, a referência da trilha, o README e os metadados públicos devem explicar:

- que novas sessões salvam pergunta e alternativas junto da correção;
- onde encontrar a revisão completa nos materiais por tópico, no caderno consolidado e nas três apostilas;
- que sessões antigas permanecem compatíveis;
- o novo marcador `question_content_version: 1` e sua finalidade.

## Testes e critérios de aceitação

- Uma sessão nova concluída sem pergunta, alternativas ou bloco de resposta é rejeitada com mensagem específica.
- Subtítulos duplicados ou fora da ordem são rejeitados.
- Alternativas vazias, sem rótulo ou em quantidade inferior a duas são rejeitadas.
- Uma sessão legada sem o marcador continua válida.
- Os 20 blocos completos aparecem nos materiais por tópico e no caderno consolidado.
- Markdown, HTML e PDF apresentam pergunta e alternativas antes da resposta e do gabarito.
- O HTML escapa conteúdo jurídico e mantém links funcionais e índice lateral.
- O texto extraído do PDF comprova a ordem pergunta → alternativas → resposta e preserva os links suportados.
- A suíte completa, a validação rápida e as verificações visuais dos exemplos precisam passar antes da publicação.

