def question_feedback(number, topic_id="controle"):
    return f"""### Questão {number}
- Tópico: {topic_id}
- Resposta: alternativa A
- Resultado: correta; gabarito A
- Fundamento: Constituição Federal.
- Alternativas úteis: B ignora a competência.
- Tipo de erro: nenhum
- Prevenção: manter a revisão.
- Fonte: https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm
- Revisão: em sete dias.
"""


def feedback_section(count=20, topic_ids=("controle",)):
    blocks = [question_feedback(n, topic_ids[(n - 1) % len(topic_ids)]) for n in range(1, count + 1)]
    blocks.append("""### Diagnóstico agregado
- Acertos: 20/20 (100%).
- Padrões de erro: nenhum.
- Prioridade: consolidar competência.
- Próxima revisão: em sete dias.
""")
    return "\n".join(blocks)
