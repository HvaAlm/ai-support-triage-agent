from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from triage.config import Settings
from triage.investigation import CodexInvestigator, InvestigationError, validate_result


def result():
    return dict(summary='مشاهده کد، نه اثبات علت', facts=[dict(statement='تابع ورودی را برمی‌گرداند',
        path='service.py', line_start=1, line_end=2, quote='def sentiment(text):\n    return text')],
        hypotheses=[dict(cause='احتمال عبور از تحلیل', evidence_indices=[0], confidence='low', verification='مسیر فراخوانی را با لاگ بررسی کنید')],
        suggested_fixes=['پس از تأیید، مسیر تحلیل بررسی شود.'], limitations=['اجرا نشده است.'])


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'service.py').write_text('def sentiment(text):\n    return text\n')

    def test_evidence_validation_and_source_hash(self):
        validated = validate_result(result(), self.root)
        self.assertEqual(validated['mode'], 'live')
        self.assertEqual(len(validated['facts'][0]['sha256']), 64)

    def test_rejects_fabricated_quotes_paths_lines_and_unsupported_hypotheses(self):
        for key, value in [('path', '../secret.py'), ('quote', 'invented code'), ('line_end', 999)]:
            data = result(); data['facts'][0][key] = value
            with self.assertRaises(InvestigationError): validate_result(data, self.root)
        for indices in ([], [10], ['0']):
            data = result(); data['hypotheses'][0]['evidence_indices'] = indices
            with self.assertRaises(InvestigationError): validate_result(data, self.root)

    @patch('triage.gitlab.GitLabSource')
    @patch('triage.investigation.subprocess.run')
    def test_codex_receives_only_snapshot_metadata_and_no_tokens(self, run, source):
        def snapshot(destination, feature):
            (destination/'service.py').write_text('def sentiment(text):\n    return text\n')
            return dict(project='group/backend', ref='release', commit_sha='b'*40,
                        retrieved_paths=['service.py'], verified_paths=[], limitations=[])
        source.return_value.snapshot.side_effect = snapshot
        calls = []
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            if command[1:3] == ['login', 'status']:
                return subprocess.CompletedProcess(command, 0, '', 'Logged in using ChatGPT')
            output = Path(command[command.index('--output-last-message')+1])
            output.write_text(json.dumps(result()))
            return subprocess.CompletedProcess(command, 0, '', '')
        run.side_effect = execute
        settings = Settings(mode='live')
        with patch.dict('os.environ', {'GITLAB_READ_TOKEN': 'gitlab-secret', 'TELEGRAM_BOT_TOKEN': 'bot-secret', 'JIRA_PAT': 'jira-secret', 'OPENAI_API_KEY': 'api-secret'}):
            investigated = CodexInvestigator(settings).investigate(dict(report='مشکل احساسات', feature='aspect_sentiment_analysis', scenario='error', answers={}))
        command, options = calls[-1]
        self.assertEqual(command[command.index('--sandbox')+1], 'read-only')
        self.assertIn('--ignore-user-config', command)
        self.assertIn('approval_policy="never"', command)
        self.assertIn('mcp_servers={}', command)
        for secret in ('gitlab-secret', 'bot-secret', 'jira-secret', 'api-secret'):
            self.assertNotIn(secret, json.dumps(options))
        self.assertNotIn('--image', command)
        self.assertEqual(investigated['facts'][0]['commit_sha'], 'b'*40)

    @patch('triage.investigation.subprocess.run')
    def test_api_key_login_not_accepted(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, 'Logged in using an API key', '')
        with self.assertRaises(InvestigationError):
            CodexInvestigator(Settings(mode='live')).investigate({})
