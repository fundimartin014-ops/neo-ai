import unittest

from core.evaluator import Evaluator


class EvaluatorTests(unittest.TestCase):
    def test_evaluate_preserves_valid_unicode_text(self):
        result = Evaluator().evaluate(
            {"answer": "Réponse suffisamment longue pour être évaluée correctement."}
        )

        self.assertTrue(result["answer"].startswith("Réponse"))
        self.assertAlmostEqual(result["confidence"], 0.7)

    def test_evaluate_penalizes_control_characters(self):
        result = Evaluator().evaluate({"answer": "A" * 55 + "\x00"})

        self.assertAlmostEqual(result["confidence"], 0.2)

    def test_evaluate_rejects_invalid_result_shape(self):
        with self.assertRaises(TypeError):
            Evaluator().evaluate(None)

    def test_evaluate_rejects_non_string_answer(self):
        with self.assertRaises(TypeError):
            Evaluator().evaluate({"answer": 42})


if __name__ == "__main__":
    unittest.main()
