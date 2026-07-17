from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from .providers.openai import OpenAIGradingProvider
from .schemas import GradingResult


class OpenAIProviderTests(TestCase):
    @override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-5.6")
    @patch("ai_engine.providers.openai.OpenAI")
    def test_provider_requests_and_returns_structured_grading(self, openai_class):
        result = GradingResult(
            suggested_score=85,
            confidence=0.9,
            feedback="Good explanation.",
        )
        response = SimpleNamespace(
            output_parsed=result,
            usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            id="response-test",
        )
        openai_class.return_value.responses.parse.return_value = response

        provider = OpenAIGradingProvider()
        grade = provider.grade(question="What is a variable?", answer="It stores a value.", rubric=[])

        self.assertEqual(grade.result.suggested_score, 85)
        self.assertEqual(grade.input_tokens, 10)
        openai_class.return_value.responses.parse.assert_called_once()
        self.assertEqual(
            openai_class.return_value.responses.parse.call_args.kwargs["text_format"],
            GradingResult,
        )
