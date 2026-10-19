import os
os.environ.setdefault('OPENAI_API_KEY','test-no-network')
import unittest
from unittest.mock import patch, MagicMock
from openai import APITimeoutError
import httpx
from utils.llm_client import LLMClient
from web.routes.positions import api_analyze_position, PositionAnalyzeRequest
from fastapi import HTTPException

class LLMTimeoutTests(unittest.TestCase):
    def test_explicit_bounded_timeout_and_no_hidden_retries(self):
        with patch('utils.llm_client.OpenAI') as factory:
            LLMClient()
            self.assertEqual(factory.call_args.kwargs['timeout'],60.0)
            self.assertEqual(factory.call_args.kwargs['max_retries'],0)

    def test_timeout_becomes_actionable_api_error(self):
        failure=APITimeoutError(request=httpx.Request('POST','https://example.invalid/v1/chat/completions'))
        with patch('web.routes.positions.analyze_position',side_effect=failure):
            with self.assertRaises(HTTPException) as caught:
                api_analyze_position(PositionAnalyzeRequest(title='test'),MagicMock())
            self.assertEqual(caught.exception.status_code,504)
            self.assertIn('模型',caught.exception.detail)

    def test_reload_preserves_imported_singleton(self):
        import utils.llm_client as module
        imported=module.llm
        old_settings = imported._settings
        try:
            with patch('utils.llm_client.OpenAI'), patch.dict(os.environ,{'OPENAI_MODEL':'changed-model'}):
                imported.reload()
            self.assertIs(module.llm,imported)
            self.assertEqual(imported.model,'changed-model')
        finally:
            imported._settings = old_settings
