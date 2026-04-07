import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import mock_open, patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import evaluator  # noqa: E402


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        return self._response


class RecordingClient(FakeClient):
    def __init__(self, response):
        super().__init__(response)
        self.calls = []

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class SequenceClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeHTTPError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


class EvaluatorTests(unittest.TestCase):
    def test_api_connection_rejects_sse_error_payload(self):
        client = FakeClient(
            'event: error\ndata: {"error":{"message":"AppChatRev unavailable"}}'
        )

        with redirect_stdout(io.StringIO()):
            ok = evaluator._test_api_connection(client)

        self.assertFalse(ok)

    def test_evaluate_project_returns_none_for_error_payload(self):
        client = FakeClient(
            'event: error\ndata: {"error":{"message":"AppChatRev unavailable"}}'
        )

        project = {
            "full_name": "openclaw/openclaw",
            "description": "demo",
            "language": "Python",
            "stars": 1,
            "contributors": 1,
            "release_count": 0,
            "has_ci": True,
            "pushed_at": "2026-04-07T00:00:00Z",
            "topics": [],
            "source_samples": [],
        }

        with redirect_stdout(io.StringIO()):
            result = evaluator.evaluate_project(client, project)

        self.assertIsNone(result)

    def test_evaluate_project_fills_missing_total_from_scores(self):
        client = FakeClient(
            """
            {
              "scores": {
                "code_quality": 8,
                "maintainability": 7,
                "robustness": 6,
                "sustainability": 5,
                "portability": 7,
                "extensibility": 9
              }
            }
            """
        )

        project = {
            "full_name": "openclaw/openclaw",
            "description": "demo",
            "language": "Python",
            "stars": 1,
            "contributors": 1,
            "release_count": 0,
            "has_ci": True,
            "pushed_at": "2026-04-07T00:00:00Z",
            "topics": [],
            "source_samples": [],
        }

        with redirect_stdout(io.StringIO()):
            result = evaluator.evaluate_project(client, project)

        self.assertIsNotNone(result)
        self.assertEqual(result["total"], 7.0)

    def test_main_exits_when_api_precheck_fails(self):
        with (
            patch.object(evaluator, "DATA_DIR", "C:\\fake-data"),
            patch.object(evaluator.os.path, "exists", return_value=True),
            patch("builtins.open", mock_open(read_data='{"projects": []}')),
            patch.object(evaluator, "OpenAI", return_value=object()),
            patch.object(evaluator, "_test_api_connection", return_value=False),
        ):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    evaluator.main()

        self.assertEqual(exc.exception.code, 1)

    def test_grok_models_force_non_stream_and_disable_reasoning(self):
        project = {
            "full_name": "openclaw/openclaw",
            "description": "demo",
            "language": "Python",
            "stars": 1,
            "contributors": 1,
            "release_count": 0,
            "has_ci": True,
            "pushed_at": "2026-04-07T00:00:00Z",
            "topics": [],
            "source_samples": [],
        }
        client = RecordingClient(
            """
            {
              "scores": {
                "code_quality": 8,
                "maintainability": 7,
                "robustness": 6,
                "sustainability": 5,
                "portability": 7,
                "extensibility": 9
              },
              "total": 7.0
            }
            """
        )

        with patch.object(evaluator, "LLM_MODEL", "grok-4.20-beta"):
            with redirect_stdout(io.StringIO()):
                result = evaluator.evaluate_project(client, project)

        self.assertIsNotNone(result)
        self.assertEqual(len(client.calls), 1)
        request = client.calls[0]
        self.assertFalse(request["stream"])
        self.assertEqual(request["reasoning_effort"], "none")

    def test_non_grok_models_do_not_send_reasoning_effort(self):
        client = RecordingClient("OK")

        with patch.object(evaluator, "LLM_MODEL", "gpt-4o-mini"):
            with redirect_stdout(io.StringIO()):
                evaluator._test_api_connection(client)

        self.assertEqual(len(client.calls), 1)
        request = client.calls[0]
        self.assertFalse(request["stream"])
        self.assertNotIn("reasoning_effort", request)

    def test_api_connection_retries_transient_gateway_errors(self):
        client = SequenceClient(
            [
                FakeHTTPError(502, "Bad gateway"),
                "OK",
            ]
        )

        with patch.object(evaluator.time, "sleep") as sleep_mock:
            with redirect_stdout(io.StringIO()):
                ok = evaluator._test_api_connection(client)

        self.assertTrue(ok)
        self.assertEqual(len(client.calls), 2)
        sleep_mock.assert_called_once()

    def test_evaluate_project_retries_transient_gateway_errors(self):
        project = {
            "full_name": "openclaw/openclaw",
            "description": "demo",
            "language": "Python",
            "stars": 1,
            "contributors": 1,
            "release_count": 0,
            "has_ci": True,
            "pushed_at": "2026-04-07T00:00:00Z",
            "topics": [],
            "source_samples": [],
        }
        client = SequenceClient(
            [
                FakeHTTPError(502, "Bad gateway"),
                """
                {
                  "scores": {
                    "code_quality": 8,
                    "maintainability": 7,
                    "robustness": 6,
                    "sustainability": 5,
                    "portability": 7,
                    "extensibility": 9
                  },
                  "total": 7.0
                }
                """,
            ]
        )

        with patch.object(evaluator.time, "sleep") as sleep_mock:
            with redirect_stdout(io.StringIO()):
                result = evaluator.evaluate_project(client, project)

        self.assertIsNotNone(result)
        self.assertEqual(len(client.calls), 2)
        sleep_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
