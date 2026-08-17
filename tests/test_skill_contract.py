import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    @staticmethod
    def read(relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_skill_requires_theory_reading_gate_before_twenty_questions(self):
        skill = self.read("SKILL.md")

        for required in (
            "theory_briefing_version: 1",
            "não apresentar nenhuma questão na mesma resposta",
            "aguardar uma confirmação explícita de leitura",
            "Não permitir pular a preparação",
            "matriz interna de cobertura",
        ):
            self.assertIn(required, skill)
        self.assertLess(
            skill.index("aguardar uma confirmação explícita de leitura"),
            skill.index("Apresentar então as 20 questões"),
        )

    def test_reference_defines_versioned_theory_structure_and_legacy_policy(self):
        reference = self.read("references/trilha-e-apostila.md")

        self.assertIn('"theory_briefing_version": 1', reference)
        for heading in (
            "### Objetivos de aprendizagem",
            "### Essencial para a prova",
            "### Fundamentos e conceitos",
            "### Regras, requisitos e efeitos",
            "### Exemplos e pegadinhas",
            "### Checklist antes das questões",
        ):
            self.assertIn(heading, reference)
        self.assertIn("Sessões legadas sem `theory_briefing_version`", reference)
        self.assertIn("não revelar enunciados, alternativas ou gabaritos", reference)

    def test_public_metadata_and_readme_present_the_new_workflow_and_outputs(self):
        metadata = self.read("agents/openai.yaml")
        readme = self.read("README.md")

        self.assertIn("preparação teórica", metadata)
        self.assertIn("preparação teórica detalhada", readme)
        self.assertIn("confirme que terminou a leitura", readme)
        self.assertIn("aula teórica, 20 questões e feedbacks", readme)
        self.assertIn("preparação completa e o resumo estratégico", readme)


if __name__ == "__main__":
    unittest.main()
