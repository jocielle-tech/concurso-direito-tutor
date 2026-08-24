import struct
import zlib


def png_bytes(width=1536, height=1024, rgb=(99, 91, 255)):
    """Return a minimal valid RGB PNG fixture without external dependencies."""
    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, level=9))
        + chunk(b"IEND", b"")
    )


def question_feedback(number, topic_id="controle", include_content=False):
    content = ""
    if include_content:
        content = f"""
#### Pergunta

Qual regra jurídica se aplica à situação {number}?

#### Alternativas

- A) Aplica-se a regra constitucional indicada.
- B) Afasta-se toda competência constitucional.
- C) A decisão independe de fundamento normativo.
- D) O controle é sempre administrativo.
- E) Não existe revisão possível.

#### Resposta e feedback
"""
    return f"""### Questão {number}
- Tópico: {topic_id}
{content}
- Resposta: alternativa A
- Resultado: correta; gabarito A
- Fundamento: Constituição Federal.
- Alternativas úteis: B ignora a competência.
- Tipo de erro: nenhum
- Prevenção: manter a revisão.
- Fonte: https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm
- Revisão: em sete dias.
"""


def feedback_section(count=20, topic_ids=("controle",), include_content=False):
    blocks = [
        question_feedback(n, topic_ids[(n - 1) % len(topic_ids)], include_content)
        for n in range(1, count + 1)
    ]
    blocks.append("""### Diagnóstico agregado
- Acertos: 20/20 (100%).
- Padrões de erro: nenhum.
- Prioridade: consolidar competência.
- Próxima revisão: em sete dias.
""")
    return "\n".join(blocks)
