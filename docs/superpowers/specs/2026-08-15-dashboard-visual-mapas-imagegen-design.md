# Dashboard visual e mapas algorítmicos com geração nativa

Data: 2026-08-15  
Status: aprovado em conversa, aguardando revisão do documento

## Objetivo

Elevar a qualidade visual das apostilas HTML e PDF e gerar automaticamente um mapa mental algorítmico ilustrado para cada tópico concluído. A imagem deve ser produzida pela ferramenta `imagegen` nativa do Codex, sem solicitar API key, serviço de imagem ou ferramenta externa ao usuário.

O material textual validado continua sendo a fonte jurídica oficial. A imagem é uma representação didática complementar, nunca a única fonte do conteúdo.

## Decisões aprovadas

- Gerar uma imagem por tópico concluído, e não por sessão ou por solicitação avulsa.
- Usar fluxograma algorítmico com textos curtos, em vez de mapa radial.
- Adotar a identidade visual **Dashboard Moderno**: violeta, azul, cartões, gradientes discretos e hierarquia clara.
- Produzir PNG horizontal com composição-alvo 1536 × 1024 (proporção 3:2).
- Ampliar a imagem em modal no HTML e ajustá-la sem corte à página A4 no PDF.
- Reutilizar a imagem enquanto o conteúdo-fonte não mudar.
- Manter fallback determinístico quando `imagegen` estiver indisponível ou produzir conteúdo incorreto.
- Preservar abaixo da imagem uma versão textual completa, pesquisável e acessível.

## Fora de escopo

- Chamar uma API de imagens por chave do usuário.
- Exigir instalação de gerador gráfico externo.
- Gerar imagens em dúvidas rápidas, sessões incompletas ou tópicos ainda não concluídos.
- Substituir o texto jurídico pela imagem.
- Regenerar imagens durante cada execução do build.
- Inserir CDN, fonte web ou dependência remota no HTML.

## Arquitetura

### Separação de responsabilidades

1. A sessão canônica contém o mapa textual e validável.
2. Um utilitário determinístico da skill agrega os mapas das sessões concluídas ligadas ao tópico, na ordem do manifesto, normaliza o conteúdo, calcula seu hash e prepara o prompt visual, o texto alternativo e o caminho final.
3. O agente que usa a skill chama `imagegen` em modo nativo e copia a imagem selecionada para a trilha.
4. O build nunca chama um modelo de imagem. Ele apenas valida, incorpora ou aplica fallback.
5. HTML e PDF são derivados determinísticos das fontes textuais e dos bytes da imagem já persistida.

Essa fronteira preserva o build reproduzível e permite que a ferramenta nativa seja usada sem acoplar Python a uma API ou credencial.

### Fluxo de fechamento

Ao concluir as 20 respostas e fechar uma sessão:

1. Validar o mapa textual e os feedbacks.
2. Para cada tópico que passou a `completed`, calcular o material visual esperado.
3. Se o PNG do hash atual existir e for válido, reutilizá-lo.
4. Se não existir, chamar obrigatoriamente a skill `imagegen` em modo nativo.
5. Inspecionar visualmente o resultado contra o mapa textual.
6. Se houver erro, fazer uma única nova tentativa com correção direcionada.
7. Persistindo o erro, não salvar a imagem incorreta; registrar o visual como pendente e usar fallback determinístico.
8. Executar o build transacional das apostilas e demais derivados.

## Fonte algorítmica

O título da seção canônica continua sendo `## Mapa mental`, preservando compatibilidade. Para novas sessões, o conteúdo deve ser redigido como fluxo de decisão com no máximo três níveis e com as categorias jurídicas atuais:

```markdown
## Mapa mental
- [conceito] ENTRADA: existe caso concreto?
  - [regra] SE SIM: usar controle difuso
    - [regra] ENTÃO: verificar reserva de plenário
  - [excecao] SE NÃO: avaliar controle concentrado
    - [jurisprudencia] RESULTADO: identificar ação e efeitos
- [pegadinha] ALERTA: órgão fracionário não declara inconstitucionalidade livremente
```

Os marcadores `ENTRADA`, `SE`, `ENTÃO`, `SENÃO`, `RESULTADO` e `ALERTA` orientam formas e conectores do fluxograma. Mapas legados sem esses marcadores continuam válidos e usam a renderização hierárquica atual.

## Arquivos, cache e descoberta

As imagens ficam sob a trilha, separadas dos derivados textuais:

```text
estudos/<trilha>/
└── assets/
    └── mapas/
        └── <topic_id>/
            └── <sha256-do-conteudo>.png
```

O hash inclui conteúdo normalizado de todas as sessões concluídas do tópico, `topic_id`, versão do template visual e proporção-alvo. Alterar qualquer desses elementos muda o caminho esperado e força nova geração. Renomear títulos sem alterar o conteúdo ou o `topic_id` não deve regenerar a imagem.

Um utilitário público deve fornecer, em saída legível por máquina:

- `topic_id`;
- `source_hash`;
- `expected_path`;
- `prompt`;
- `alt_text`;
- estado `ready`, `missing` ou `invalid`.

O build descobre a imagem pelo mesmo cálculo. Imagens antigas deixam de ser referenciadas, mas não são apagadas automaticamente.

## Contrato da geração nativa

A skill deve declarar `imagegen` como sub-skill obrigatória somente quando houver tópico recém-concluído ou mapa atual sem imagem válida.

O prompt usa a taxonomia `infographic-diagram` e inclui:

- uso: mapa algorítmico de estudo jurídico;
- composição horizontal 3:2, desenhada para um canvas-alvo de 1536 × 1024;
- identidade Dashboard Moderno;
- nós e conectores claros;
- texto curto fornecido verbatim;
- paleta semântica das categorias;
- proibição de logos, marcas-d'água, artigos ou precedentes adicionais;
- fundo limpo, contraste alto e margens seguras.

A skill deve usar a ferramenta nativa, que não requer `OPENAI_API_KEY`. O fallback CLI não será usado automaticamente. Se a ferramenta nativa não estiver disponível, o fluxo segue para o fallback determinístico sem bloquear o fechamento.

## Validação da imagem

Antes de incorporar um PNG:

- confirmar assinatura PNG, orientação horizontal e proporção próxima de 3:2; a ferramenta nativa não expõe controle rígido de pixels, portanto o layout de consumo deve ajustar a imagem ao quadro visual equivalente a 1536 × 1024 sem cortar ou distorcer;
- garantir que o caminho calculado permaneça contido na trilha;
- inspecionar visualmente legibilidade, contraste e composição;
- comparar os rótulos essenciais com a fonte;
- rejeitar texto jurídico inventado, marca-d'água, logotipo ou decoração confusa;
- limitar a uma regeneração direcionada por fechamento.

Uma imagem rejeitada nunca substitui a última imagem válida nem entra em HTML/PDF.

## HTML — Dashboard Moderno

O HTML permanece autocontido, sem CDN e com fallback sem JavaScript.

### Estrutura visual

- fundo claro com gradiente violeta/azul discreto;
- cabeçalho com título, percentual global, sessões concluídas e próxima revisão;
- índice lateral agrupado por módulo e tópico;
- tópico ativo com marcador forte e estado textual acessível;
- cartões para resumo, regras, exceções, jurisprudência e pegadinhas;
- barras e indicadores de progresso global, por módulo e por tópico;
- questões em cartões numerados com chips de tópico e resultado;
- mapa algorítmico em cartão de largura total;
- modal de ampliação acessível por clique, teclado e botão de fechar;
- texto alternativo e versão textual do algoritmo logo após o visual;
- layout responsivo, foco visível, contraste AA e `prefers-reduced-motion`;
- impressão limpa sem controles interativos.

### Incorporação

O PNG é convertido em data URI Base64 durante o build. Assim, `apostila.html` permanece um único arquivo portátil. O fallback determinístico usa os mesmos nós, cores e rótulos em HTML/CSS, sem exigir imagem.

## PDF — Dashboard Moderno

O PDF mantém A4 e bytes determinísticos depois que as fontes e a imagem estão persistidas.

- capa com faixa violeta/azul, título e indicadores da trilha;
- sumário visual com módulos e tópicos;
- tipografia e espaçamentos reforçados;
- cabeçalhos, rodapés e números de página refinados;
- cartões semânticos para regras, exceções, jurisprudência e pegadinhas;
- mapa PNG em bloco horizontal proporcional, sem corte ou distorção;
- fallback desenhado com elementos ReportLab quando o PNG faltar;
- versão textual do algoritmo abaixo da imagem;
- questões e feedbacks agrupados, evitando títulos órfãos e quebras ruins;
- links internos, links oficiais e outline preservados.

## Estados de falha

| Condição | Comportamento |
| --- | --- |
| Imagem válida do hash atual | Reutilizar sem nova chamada |
| Imagem ausente | Chamar `imagegen` nativa no fechamento |
| `imagegen` indisponível | Gerar apostilas com fallback e registrar pendência |
| Primeira imagem incorreta | Regenerar uma vez com correção direcionada |
| Segunda imagem incorreta | Rejeitar e usar fallback |
| PNG inválido ou proporção inadequada | Não incorporar; usar fallback e manter o visual pendente |
| Falha do build | Restaurar todos os derivados anteriores |

## Compatibilidade

- Trilhas antigas sem `assets/mapas/` continuam construindo normalmente.
- Mapas hierárquicos existentes continuam válidos.
- O schema v1 não ganha campo obrigatório novo.
- Sessões incompletas não exigem imagem.
- A migração legada não cria imagens; apenas o fechamento ou comando explícito de regeneração pode fazê-lo.
- HTML e PDF antigos são substituídos apenas quando o novo bundle inteiro estiver pronto.

## Atualizações da skill e documentação

Atualizar:

- `SKILL.md`, mantendo-o conciso;
- `references/trilha-e-apostila.md`, com contrato, algoritmo, fluxo nativo e fallback;
- `agents/openai.yaml`, mencionando mapas visuais nativos;
- `README.md`, com novidades, exemplo, paths e ausência de chave externa;
- captura real do HTML Dashboard Moderno;
- árvore documentada para incluir `assets/mapas/`.

O forward-test deve usar uma instância nova do Codex e verificar que ela:

1. chama `imagegen` nativa ao concluir tópico sem cache;
2. não solicita chave de API nem ferramenta externa;
3. reutiliza imagem quando o hash não muda;
4. usa fallback sem bloquear a sessão quando a ferramenta não está disponível;
5. não gera imagem para sessão incompleta.

## Estratégia de testes

### Utilitário e cache

- hash estável para o mesmo conteúdo;
- hash diferente quando conteúdo ou versão visual muda;
- path traversal rejeitado;
- detecção de PNG, dimensão e status;
- reutilização sem regeneração.

### HTML

- data URI incorporada e arquivo autocontido;
- modal acessível e operável por teclado;
- alt text e fallback textual;
- Dashboard Moderno, responsividade, impressão, contraste e movimento reduzido;
- todos os fragmentos internos válidos e sem IDs duplicados.

### PDF

- imagem proporcional sem corte;
- fallback ReportLab;
- texto do algoritmo pesquisável;
- links, outline, paginação e determinismo;
- inspeção renderizada das páginas com mapa e questões.

### Regressão

- 20 questões e correção posterior preservadas;
- migração, rollback e paths canônicos preservados;
- trilhas sem imagem continuam válidas;
- build transacional não publica parte dos formatos.

## Critérios de aceite

1. Um tópico recém-concluído recebe no máximo uma imagem válida do conteúdo atual.
2. Nenhuma chave, API ou ferramenta de geração externa é solicitada.
3. HTML e PDF exibem o mesmo mapa e mantêm a versão textual.
4. HTML autocontido funciona em desktop, móvel, impressão e sem JavaScript.
5. PDF não corta o mapa e preserva links e texto pesquisável.
6. Falha de imagem não bloqueia o estudo nem publica conteúdo incorreto.
7. O cache impede chamadas desnecessárias.
8. Trilhas legadas permanecem compatíveis.
9. A skill, README e metadados apresentam claramente a nova funcionalidade.
