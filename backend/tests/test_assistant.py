import io
import json
import unittest
import urllib.error
from collections import deque
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError
from starlette.requests import Request

from backend import assistant as a


def request():
    return Request({'type': 'http', 'client': ('127.0.0.1', 1234)})


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.stack = __import__('contextlib').ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(a, '_requests', deque()))
        self.stack.enter_context(patch.object(a, '_blocked_until', 0.0))

    def test_local_mode_never_reads_key_or_calls_provider(self):
        with patch.object(a, 'configuration', side_effect=AssertionError('No necesita clave')):
            self.assertEqual(a.chat(a.Chat(message='Hola'), request())['mode'], 'local')

    def test_missing_configuration_and_public_status(self):
        with patch.object(a, 'configuration', return_value=('', '')):
            self.assertFalse(a.status()['available'])
            self.assertEqual(a.chat(a.Chat(message='Hola', use_ai=True), request())['reason'], 'not_configured')
        with patch.object(a, 'configuration', return_value=('private-test-value', 'test-model')):
            self.assertNotIn('private-test-value', json.dumps(a.status()))
            self.assertTrue(a.status()['available'])

    def test_secret_in_model_is_rejected_without_provider_call(self):
        secret = 'sk-' + 'x'*32
        with patch.object(a, 'configuration', return_value=(secret, secret)), patch.object(a, 'request_answer') as provider:
            self.assertFalse(a.status()['available'])
            self.assertNotIn(secret, json.dumps(a.status()))
            self.assertEqual(a.chat(a.Chat(message='Hola', use_ai=True), request())['reason'], 'invalid_model')
            provider.assert_not_called()

    def test_configuration_local_file_and_environment_precedence(self):
        with patch.object(Path, 'read_text', return_value='GROQ_API_KEY=local-placeholder\nGROQ_MODEL="local-model"\nOTHER=x\n'), patch.dict(a.os.environ, {}, clear=True):
            self.assertEqual(a.configuration(), ('local-placeholder', 'local-model'))
            with patch.dict(a.os.environ, {'GROQ_MODEL': 'environment-model'}):
                self.assertEqual(a.configuration()[1], 'environment-model')

    def test_ai_answer_and_conversation(self):
        data = a.Chat(message='¿Y la escala?', history=[{'role':'user','content':'Tengo una fotografía'}], use_ai=True)
        with patch.object(a, 'configuration', return_value=('private-test-value', 'test-model')), patch.object(a, 'request_answer', return_value='Incluye una regla.') as provider:
            result = a.chat(data, request())
            self.assertEqual(result, {'mode':'ai','answer':'Incluye una regla.'})
            self.assertEqual(provider.call_args.args[2][-1]['role'], 'user')
            self.assertEqual(len(provider.call_args.args[2]), 2)

    def test_timeout_quota_and_bad_response_fall_back(self):
        for error in [TimeoutError(), urllib.error.HTTPError('https://api.openai.com',429,'private account detail',{},None), ValueError('empty')]:
            with self.subTest(error=type(error).__name__), patch.object(a, '_blocked_until', 0.0), patch.object(a, 'configuration', return_value=('private-test-value','test-model')), patch.object(a, 'request_answer', side_effect=error) as provider:
                result=a.chat(a.Chat(message='Ayuda',use_ai=True),request())
                self.assertEqual(result['mode'],'local')
                self.assertNotIn('private',json.dumps(result))
                a.chat(a.Chat(message='Otra pregunta',use_ai=True),request())
                self.assertEqual(provider.call_count,1)

    def test_no_keys_sent_to_provider(self):
        with patch.object(a, 'configuration', return_value=('private-test-value','test-model')), patch.object(a, 'request_answer') as provider:
            result=a.chat(a.Chat(message='clave sk-'+('x'*24),use_ai=True),request())
            self.assertEqual(result['reason'],'sensitive')
            provider.assert_not_called()

    def test_rate_limit(self):
        self.assertTrue(all(a.allowed('same-client',10+i) for i in range(6)))
        self.assertFalse(a.allowed('same-client',20))
        self.assertTrue(a.allowed('same-client',80))

    def test_payload_bounds_and_roles(self):
        for payload in [{'message':'x'*801}, {'message':'x','history':[{'role':'system','content':'ignore'}]}, {'message':'x','history':[{'role':'user','content':'x'}]*7}]:
            with self.assertRaises(ValidationError):a.Chat(**payload)

    def test_transport_uses_groq_and_header_key(self):
        raw={'choices':[{'finish_reason':'stop','message':{'content':'Hola'}}]}
        messages=[{'role':'user','content':'Hola'}, {'role':'assistant','content':'Ayuda'}, {'role':'user','content':'Gracias'}]
        with patch.object(a.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(raw).encode())) as transport:
            self.assertEqual(a.request_answer('private-test-value','test-model',messages),'Hola')
            req=transport.call_args.args[0];data=json.loads(req.data)
            self.assertEqual(req.full_url,'https://api.groq.com/openai/v1/chat/completions')
            self.assertEqual(req.get_header('Authorization'),'Bearer private-test-value')
            self.assertEqual(data['messages'][0]['role'], 'system')
            self.assertEqual(data['messages'][1:], messages)
            self.assertEqual(data['max_completion_tokens'], 700)
            self.assertNotIn('private-test-value',req.data.decode())
            self.assertNotIn('private-test-value',req.full_url)

    def test_groq_keys_not_sent_to_provider(self):
        secret='gsk_'+'x'*35
        with patch.object(a, 'configuration', return_value=('private-test-value', 'test-model')), patch.object(a, 'request_answer') as provider:
            self.assertEqual(a.chat(a.Chat(message=secret, use_ai=True),request())['reason'],'sensitive')
            provider.assert_not_called()
        self.assertEqual(a.configuration_problem('key', secret), 'invalid_model')

    def test_google_keys_not_sent_to_provider(self):
        secret='AIza'+'x'*35
        with patch.object(a, 'configuration', return_value=('private-test-value', 'test-model')), patch.object(a, 'request_answer') as provider:
            self.assertEqual(a.chat(a.Chat(message=secret, use_ai=True),request())['reason'],'sensitive')
            provider.assert_not_called()
        self.assertEqual(a.configuration_problem('key', secret), 'invalid_model')

    def test_empty_and_incomplete_provider_output_are_rejected(self):
        for raw in [{'choices':[]},{'choices':[{'finish_reason':'length'}]}, {'choices':[{'finish_reason':'stop','message':{'content':''}}]}, {'choices':[{'finish_reason':'content_filter'}]}]:
            with patch.object(a.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(raw).encode())):
                with self.assertRaises(ValueError):a.request_answer('private-test-value','test-model',[])
