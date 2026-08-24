---
name: Concurso Direito Tutor
description: Um caderno de aprovação digital que transforma cada sessão guiada em conhecimento revisável.
colors:
  institutional-indigo: "#3730A3"
  orientation-blue: "#075985"
  action-violet: "#635BFF"
  study-blue: "#0284C7"
  link-blue: "#175CD3"
  legal-ink: "#101828"
  supporting-ink: "#475467"
  paper: "#FFFFFF"
  desk-canvas: "#F4F7FB"
  quiet-border: "#D0D5DD"
  success: "#15803D"
  warning: "#B45309"
  danger: "#B42318"
  focus-on-paper: "#344054"
  focus-on-hero: "#FFFFFF"
typography:
  display:
    fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "clamp(1.75rem, 4vw, 2.7rem)"
    fontWeight: 700
    lineHeight: 1.12
  headline:
    fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "1.65rem"
    fontWeight: 700
    lineHeight: 1.2
  title:
    fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "0.82rem"
    fontWeight: 700
    lineHeight: 1.35
rounded:
  compact: "0.65rem"
  control: "0.75rem"
  panel: "0.85rem"
  card: "1rem"
  hero: "1.5rem"
  pill: "999px"
  circle: "50%"
spacing:
  micro: "0.2rem"
  compact: "0.55rem"
  cluster: "0.8rem"
  control: "1rem"
  card: "1.15rem"
  page: "1.5rem"
  section: "2.6rem"
components:
  hero:
    backgroundColor: "{colors.institutional-indigo}"
    textColor: "{colors.paper}"
    typography: "{typography.body}"
    rounded: "{rounded.hero}"
    padding: "2.2rem 1.5rem 1.5rem"
  metric-card:
    textColor: "{colors.paper}"
    rounded: "{rounded.panel}"
    padding: "{spacing.control}"
  study-card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.legal-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.card}"
    padding: "{spacing.card}"
  status-chip:
    textColor: "{colors.institutional-indigo}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0.2rem 0.55rem"
  question-card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.legal-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "{spacing.control}"
  close-button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.legal-ink}"
    rounded: "{rounded.circle}"
    height: "2.4rem"
    width: "2.4rem"
---

# Design System: Concurso Direito Tutor

## Overview

**Creative North Star: "Caderno de Aprovação"**

O sistema visual deve parecer um caderno de estudo cuidadosamente organizado que ganhou orientação, memória e progresso. Sua hierarquia é calma e previsível: o aluno entende onde está, lê por longos períodos e reconhece a próxima ação sem disputar atenção com ornamentos. Índigo institucional transmite rigor; azul orienta; superfícies claras preservam a sensação de papel.

A interface é clara, confiável e estimulante, com densidade compatível com conteúdo jurídico extenso. Ela rejeita explicitamente a aparência de uma plataforma jurídica burocrática, densa ou intimidadora. O progresso pode ter energia; a leitura deve permanecer silenciosa.

**Key Characteristics:**

- Hierarquia editorial calma e imediatamente escaneável.
- Papel branco sobre uma mesa azul-acinzentada suave.
- Índigo para autoridade, azul para orientação e cores semânticas para diagnóstico.
- Progresso sempre visível, mas nunca mais importante que o conteúdo.
- Componentes arredondados e familiares, com estados de foco inequívocos.
- Continuidade visual entre HTML navegável, impressão e PDF.

**The Next Action Rule.** Toda tela deve tornar localização, progresso e próxima ação compreensíveis antes de exigir leitura detalhada.

## Colors

A paleta combina autoridade institucional com a serenidade de um caderno digital, reservando as cores mais intensas para orientação e estado.

### Primary

- **Índigo Institucional** (`institutional-indigo`): ancora o cabeçalho, títulos de sessão e superfícies de alta autoridade.
- **Violeta de Ação** (`action-violet`): inicia progressos, marca questões e identifica ações ou estruturas de estudo.

### Secondary

- **Azul de Orientação** (`orientation-blue`): conclui o gradiente do cabeçalho e cria direção sem competir com o índigo.
- **Azul de Estudo** (`study-blue`): identifica conteúdo teórico, estrutura e etapas de aprendizagem.
- **Azul de Link** (`link-blue`): reservado a destinos navegáveis e referências acionáveis.

### Tertiary

- **Verde de Domínio** (`success`): conteúdo concluído e resultado positivo.
- **Âmbar de Atenção** (`warning`): sessão em andamento, ressalva ou exceção.
- **Vermelho de Risco** (`danger`): erro, pegadinha, alerta ou consequência crítica.

### Neutral

- **Tinta Jurídica** (`legal-ink`): texto principal, títulos e estado ativo.
- **Tinta de Apoio** (`supporting-ink`): legendas, metadados e explicações secundárias.
- **Papel** (`paper`): superfície principal de leitura.
- **Mesa Serena** (`desk-canvas`): fundo que separa o material de estudo da janela.
- **Divisor Silencioso** (`quiet-border`): contornos estruturais sem peso burocrático.
- **Foco sobre Papel** (`focus-on-paper`): contorno de teclado em superfícies claras.
- **Foco sobre Hero** (`focus-on-hero`): contorno de teclado sobre fundos institucionais.

**The Quiet Canvas Rule.** Papel e Mesa Serena devem ocupar a maior parte da tela; acentos saturados são sinais, não decoração contínua.

**The Semantic Integrity Rule.** Verde, âmbar e vermelho nunca são decorativos: sempre comunicam conclusão, atenção ou risco.

## Typography

**Display Font:** System UI, com `-apple-system`, BlinkMacSystemFont e Segoe UI como fallbacks.
**Body Font:** System UI, com `-apple-system`, BlinkMacSystemFont e Segoe UI como fallbacks.

**Character:** Uma única família sans-serif nativa mantém carregamento imediato, familiaridade e legibilidade entre plataformas. Peso, escala e espaço — não uma troca ornamental de fonte — estabelecem a hierarquia.

### Hierarchy

- **Display** (700, fluido de `1.75rem` a `2.7rem`, 1.12): título único do dashboard e capa da trilha.
- **Headline** (700, `1.65rem`, 1.2): módulos e grandes mudanças de contexto.
- **Title** (700, `1rem`, 1.35): títulos de sessão, seção teórica e questão.
- **Body** (400, `1rem`, 1.55): explicação jurídica e leitura prolongada; limitar parágrafos de abertura a aproximadamente 56rem.
- **Label** (700, `0.82rem`, 1.35): métricas, chips, estados e micro-hierarquia.

**The Reading First Rule.** Nunca comprima o corpo para acomodar mais interface; a apostila existe para leitura prolongada, não para maximizar cartões por viewport.

**The One Voice Rule.** Use a família nativa em toda a interface. Diferencie níveis por peso e escala antes de introduzir qualquer nova fonte.

## Elevation

O sistema é plano na leitura e elevado apenas onde a separação funcional precisa permanecer visível. Cartões e índice usam uma sombra ambiente baixa; o diálogo usa elevação forte porque muda o modo de interação. No PDF e na impressão, as sombras desaparecem e a estrutura passa a depender de espaço, tonalidade e linhas finas.

### Shadow Vocabulary

- **Elevação de Caderno** (`0 10px 30px rgba(16, 24, 40, 0.08)`): índice fixo, cartões de estudo e mapas visuais sobre a Mesa Serena.
- **Elevação de Foco** (`0 24px 70px rgba(16, 24, 40, 0.35)`): exclusivamente para o diálogo ampliado do mapa mental.

**The Structural Shadow Rule.** Sombra só pode explicar separação, fixação ou mudança de modo. Se ela apenas “embelezar” uma superfície, remova-a.

**The Print Becomes Paper Rule.** Em impressão, remova sombras e fundos decorativos; preserve hierarquia, links úteis, quebras e legibilidade.

## Components

### Buttons

Controles são diretos e silenciosos; o rótulo deve explicar a ação sem depender de ícone.

- **Shape:** suavemente arredondada (`0.75rem`) para controles comuns; circular (`50%`) apenas no fechamento do diálogo.
- **Primary:** o botão que abre o mapa ocupa toda a largura da figura, usa fundo transparente e preserva a imagem como conteúdo principal.
- **Hover / Focus:** cursor coerente com a ação e contorno externo sólido de `3px`, com deslocamento de `3px`; use Foco sobre Papel ou Foco sobre Hero conforme a superfície.
- **Mobile index:** “Índice” aparece somente abaixo de `800px` quando JavaScript está disponível e controla o painel lateral por `aria-expanded`.

### Chips

Chips são etiquetas compactas de diagnóstico, nunca botões decorativos.

- **Style:** formato pílula (`999px`), preenchimento tonal claro, texto semântico escuro, `0.82rem` e peso 700.
- **State:** azul para estado geral, verde para concluído e âmbar para em andamento; capitalize o rótulo sem transformar todo o texto em caixa alta.

### Cards / Containers

Cartões parecem folhas ou fichas apoiadas sobre a mesa, não caixas promocionais.

- **Corner Style:** cartões principais usam `1rem`; métricas e índice usam `0.85rem`; agrupamentos internos usam `0.65rem` a `0.75rem`.
- **Background:** Papel para leitura, com tintas muito claras reservadas a teoria, pergunta, alternativas e feedback.
- **Shadow Strategy:** Elevação de Caderno somente nos contêineres de primeiro nível; blocos internos usam tonalidade ou borda.
- **Border:** Divisor Silencioso de `1px` separa superfícies sem criar grade pesada.
- **Internal Padding:** `1rem` a `1.15rem` nos cartões; `0.85rem` a `1rem` nos blocos internos.

### Navigation

O índice é uma presença estável que acompanha a leitura. No desktop, fica aderente, rolável e limitado à viewport; o tópico atual ganha Tinta Jurídica, peso 700 e o sufixo textual “— tópico atual”. Abaixo de `800px`, transforma-se em painel lateral acionado pelo botão Índice. Todos os links permanecem funcionais sem JavaScript; o realce por rolagem é um aprimoramento progressivo.

### Progress

A régua percentual usa trilho neutro, formato pílula e gradiente contínuo de Violeta de Ação para Azul de Estudo. Exiba sempre o valor percentual em texto, porque cor e extensão não podem ser a única forma de comunicar progresso.

### Question Review Card

Cada questão preserva a sequência Pergunta → Alternativas → Resposta e feedback. Os três blocos usam tons claros distintos e títulos consistentes; nenhuma resposta pode aparecer sem o enunciado e todas as alternativas na apostila de revisão.

### Visual Map Dialog

O mapa algorítmico abre em diálogo modal com imagem proporcional e fechamento explícito. Sempre mantenha o fluxo textual verificável como alternativa acessível, pesquisável e imprimível.

**The Continuous Study Rule.** Componentes devem reforçar a passagem teoria → 20 questões → correção → revisão → apostila, sem transformar essas etapas em experiências visuais desconectadas.

## Do's and Don'ts

### Do:

- **Do** mantenha localização, percentual e próxima ação visíveis antes do conteúdo detalhado.
- **Do** use Papel sobre Mesa Serena como estrutura dominante e reserve índigo, violeta e azul a autoridade, navegação e progresso.
- **Do** mantenha foco visível de `3px`, navegação completa por teclado, contraste WCAG 2.2 AA e suporte a movimento reduzido.
- **Do** preserve HTML navegável, PDF formatado e Markdown como expressões coerentes da mesma apostila.
- **Do** mantenha o índice aderente no desktop e acionável por teclado no painel móvel abaixo de `800px`.
- **Do** apresente enunciado, todas as alternativas, resposta e feedback juntos em cada questão revisável.

### Don't:

- **Don't** faça o produto parecer “uma plataforma jurídica burocrática, densa ou intimidadora”.
- **Don't** use cor semântica como decoração ou dependa apenas de cor para comunicar estado.
- **Don't** transforme cada parágrafo em cartão, pílula ou caixa; conteúdo jurídico precisa de fluxo editorial contínuo.
- **Don't** empilhe sombra, borda grossa e fundo tonal no mesmo nível de hierarquia.
- **Don't** esconda o fluxo textual do mapa mental atrás de uma imagem ou dependência externa.
- **Don't** reduza corpo, espaçamento ou contraste para exibir mais informação na primeira dobra.
- **Don't** introduza animações indispensáveis; toda transição deve respeitar `prefers-reduced-motion`.
