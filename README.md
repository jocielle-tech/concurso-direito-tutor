# Concurso Direito Tutor

<p align="center">
  <img src="assets/readme/hero.png" alt="Mesa contemporânea de estudos jurídicos com notebook exibindo uma trilha visual de aprendizagem" width="100%">
</p>

<p align="center">
  <a href="https://github.com/jocielle-tech/concurso-direito-tutor"><img src="https://img.shields.io/badge/skill-Codex-111827" alt="Skill para Codex"></a>
  <img src="https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white" alt="Python 3">
  <img src="https://img.shields.io/badge/depend%C3%AAncias-biblioteca%20padr%C3%A3o-16A34A" alt="Biblioteca padrão do Python">
  <img src="https://img.shields.io/badge/idioma-portugu%C3%AAs-2563EB" alt="Português">
</p>

Uma skill para transformar a preparação para concursos públicos de Direito em uma trilha de estudo persistente, auditável e visual. Ela organiza sessões, questões, feedbacks, revisões, fontes e uma apostila cumulativa — sem perder de vista o que realmente importa para a prova.

> O conteúdo é orientado ao estudo para concursos brasileiros. A confirmação de legislação, jurisprudência, súmulas, editais e regras de banca deve sempre priorizar fontes oficiais atualizadas.

## Por que usar

Em vez de acumular anotações soltas, cada sessão principal passa a deixar um registro útil para a revisão:

- trilha com módulos, tópicos ponderados e progresso global;
- explicação focada em regra, exemplo, exceção e pegadinha;
- questões originais com correção e feedback individual;
- mapa mental colorido, com categorias consistentes;
- índice clicável e régua percentual da trilha;
- apostila em Markdown e HTML, reconstruída de forma determinística.

## O resultado

Esta é uma captura de uma apostila HTML gerada por uma trilha de exemplo: há índice, progresso, legenda colorida do mapa mental, sessão de estudo e feedbacks.

<p align="center">
  <img src="assets/readme/apostila-preview.png" alt="Prévia de apostila de Direito Constitucional com índice clicável, progresso de 70%, legenda de mapa mental e conteúdo da sessão" width="100%">
</p>

## Instalação

Clone o repositório e coloque a pasta da skill no diretório de skills do Codex:

```bash
git clone https://github.com/jocielle-tech/concurso-direito-tutor.git
mkdir -p ~/.codex/skills
cp -R concurso-direito-tutor ~/.codex/skills/concurso-direito-tutor
```

Em instalações que definem `CODEX_HOME`, use o respectivo diretório `skills` dessa instalação. Reinicie ou recarregue o ambiente do Codex para que a skill seja descoberta.

## Como usar

No Codex, inicie uma conversa com um pedido concreto. A skill coleta apenas as informações que realmente alteram a estratégia — cargo, banca, edital, nível, tempo disponível e objetivo.

```text
Use $concurso-direito-tutor para criar uma trilha de Direito Constitucional
para Analista Jurídico. Tenho 6 horas por semana e ainda não tenho edital.
```

Para começar uma sessão principal:

```text
Vamos estudar controle difuso. Explique o núcleo de prova, faça três questões
no estilo Cebraspe e espere minhas respostas antes de corrigir.
```

Para uma dúvida pontual, basta perguntar. Dúvidas rápidas são respondidas no chat e não criam nem encerram sessões artificialmente.

### Exemplo de fechamento de sessão

Após a prática e a correção, a sessão registra um diagnóstico que pode ser revisitado:

```text
Acertos: 2 de 3 (67%)
Padrão de erro: reserva de plenário
Prioridade: diferenciar competência do juiz e do tribunal
Próxima revisão: em 7 dias, refazer 3 questões sobre o ponto fraco
```

Cada questão recebe fundamento, alternativas úteis, tipo de erro, prevenção, fonte e indicação de revisão. Os tipos de erro padronizados são: conceito, exceção, leitura, desatualização e estratégia.

## O que a skill gera

Ao iniciar uma trilha persistente, a estrutura fica em `estudos/<slug>/`:

```text
estudos/direito-constitucional/
├── trilha.json
├── sessoes/
│   └── 001-controle-difuso.md
├── apostila.md
└── apostila.html
```

| Arquivo | Finalidade |
| --- | --- |
| `trilha.json` | Fonte de verdade da trilha: módulos, tópicos, pesos, estado e sessões. |
| `sessoes/*.md` | Conteúdo da sessão, resumo estratégico, mapa mental, questões, feedbacks, fontes e revisão. |
| `apostila.md` | Versão cumulativa em Markdown, ideal para versionamento e leitura rápida. |
| `apostila.html` | Versão visual e imprimível, com índice, barra de progresso e cores do mapa mental. |

O gerador local valida o manifesto e produz as duas versões da apostila:

```bash
python3 scripts/build_trilha.py estudos/direito-constitucional
```

Para validar uma trilha sem escrever ou modificar a apostila:

```bash
python3 scripts/build_trilha.py --check estudos/direito-constitucional
```

## Progresso que mostra o que falta

O progresso é ponderado: cada tópico possui um peso positivo, e somente tópicos concluídos contam na porcentagem. A apostila mostra a régua global e o progresso por módulo.

```text
Progresso global: 70%
Régua de progresso: 70% ███████░░░
```

Se a trilha nasceu sem edital, ela pode começar como provisória. Quando o edital chegar, os módulos e pesos são recalibrados, sem apagar sessões, arquivos ou estados já registrados.

## Mapa mental com leitura rápida

As categorias do mapa mental são deliberadamente limitadas para que o material seja escaneável em revisão:

| Categoria | Cor | Uso |
| --- | --- | --- |
| Conceito | Azul `#2563EB` | Ideia central do tema. |
| Regra | Verde `#16A34A` | Aplicação principal cobrada. |
| Exceção | Amarelo `#D97706` | Limite ou ressalva relevante. |
| Pegadinha | Vermelho `#DC2626` | Confusão previsível de prova. |
| Jurisprudência | Roxo `#7C3AED` | Tese, precedente ou orientação importante. |

## Personalização e segurança do estudo

- Ajuste módulos, tópicos e pesos no `trilha.json` conforme o edital e a banca.
- Mantenha IDs e vínculos entre tópicos e sessões consistentes; o comando `--check` aponta inconsistências antes da geração.
- Conclua uma sessão apenas depois de ensinar, praticar e registrar o feedback; tópicos em andamento não aumentam a porcentagem.
- Use links diretos para as fontes que sustentam atualizações relevantes.

## Fontes jurídicas e limites

A skill deve diferenciar texto legal, jurisprudência, doutrina e estratégia de prova. Para informação atual, priorize fontes como [Planalto](https://www.planalto.gov.br/), [STF](https://portal.stf.jus.br/) e [STJ](https://www.stj.jus.br/). Cite a fonte junto da afirmação relevante, com a data de consulta quando aplicável.

Ela não substitui a conferência da fonte oficial nem oferece aconselhamento jurídico individual. Quando não houver fonte oficial acessível ou houver divergência, isso deve ser declarado em vez de apresentar memória como certeza.

## Desenvolvimento

O gerador utiliza apenas a biblioteca padrão do Python. Para executar a suíte de testes:

```bash
python3 -B -m unittest discover -s tests -v
```

O manifesto também pode ser validado sem gerar arquivos, com `--check`, como mostrado acima.
