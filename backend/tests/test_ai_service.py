import unittest
from unittest.mock import Mock, patch

from flask import Flask, g

from app.services.ai import AIServiceError, completion, completion_stream


class AIServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            GROQ_API_KEY="test-key",
            GROQ_MODEL="openai/gpt-oss-20b",
        )
        self.context = self.app.test_request_context("/")
        self.context.push()
        g.request_id = "request-123"

    def tearDown(self):
        self.context.pop()

    @staticmethod
    def provider_error(status_code, detail="provider response details"):
        error = RuntimeError(detail)
        error.status_code = status_code
        return error

    def mock_client(self, error):
        client = Mock()
        client.chat.completions.create.side_effect = error
        return client

    def test_completion_maps_provider_statuses_to_actionable_safe_errors(self):
        cases = [
            (401, "Verify GROQ_API_KEY"),
            (403, "not permitted to use model"),
            (404, "could not find model"),
            (413, "request is too large"),
            (429, "rate limit or usage quota"),
            (400, "Groq rejected the request"),
            (503, "temporarily unavailable"),
        ]
        for status_code, expected_message in cases:
            with self.subTest(status_code=status_code):
                client = self.mock_client(self.provider_error(status_code))
                with patch("app.services.ai._client", return_value=client):
                    with self.assertLogs(self.app.logger, level="ERROR") as logs:
                        with self.assertRaises(AIServiceError) as raised:
                            completion([{"role": "user", "content": "hello"}])

                self.assertIn(expected_message, str(raised.exception))
                self.assertNotIn("provider response details", str(raised.exception))
                self.assertIn("request_id=request-123", "\n".join(logs.output))

    def test_streaming_completion_maps_timeout_without_exposing_provider_details(self):
        timeout = type("APITimeoutError", (RuntimeError,), {})("provider response details")
        client = self.mock_client(timeout)
        with patch("app.services.ai._client", return_value=client):
            with self.assertRaises(AIServiceError) as raised:
                list(completion_stream([{"role": "user", "content": "hello"}]))

        self.assertIn("request timed out", str(raised.exception))
        self.assertNotIn("provider response details", str(raised.exception))
