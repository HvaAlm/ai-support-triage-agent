import json
import subprocess
import unittest
from unittest.mock import patch
from triage.skill_publisher import SkillPublisher


class SkillAdapterTests(unittest.TestCase):
    def setUp(self):
        self.draft = dict(title='Confirmed title', description='Confirmed description',
                          project='TEST', issue_type='Bug')
        self.publisher = SkillPublisher()

    @patch('triage.skill_publisher.subprocess.run')
    def test_documented_cli_and_actual_response(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, json.dumps({
            'confirmed': True, 'issue': {'key': 'REAL-7', 'url': 'https://returned.example/ticket/7'}}))
        result = self.publisher.publish('case', self.draft)
        self.assertEqual(result.status, 'published')
        self.assertEqual(result.issue_key, 'REAL-7')
        self.assertEqual(result.jira_url, 'https://returned.example/ticket/7')
        args, kwargs = run.call_args
        self.assertIn('create_issue', args[0])
        self.assertIn('--confirm', args[0])
        self.assertEqual(kwargs['env']['JIRA_MAX_RETRIES'], '0')
        self.assertFalse(kwargs.get('shell', False))
        run.assert_called_once()

    @patch('triage.skill_publisher.subprocess.run')
    def test_unsupported_inputs_never_invoke_skill(self, run):
        for extra in ({'attachments': [{'name': 'evidence'}]}, {'team': 'backend'}, {'project': ''}):
            self.assertEqual(self.publisher.publish('case', dict(self.draft, **extra)).status, 'pending')
        run.assert_not_called()

    @patch('triage.skill_publisher.subprocess.run')
    def test_declined_confirmation_and_ambiguous_error_are_not_retried(self, run):
        for payload, expected in [({'requires_confirmation': True}, 'pending'),
                                  ({'error': {'message': 'Connection lost'}}, 'unknown'),
                                  ({'confirmed': True, 'issue': {'key': 'TEST-1'}}, 'unknown')]:
            run.reset_mock()
            run.return_value = subprocess.CompletedProcess([], 0, json.dumps(payload))
            self.assertEqual(self.publisher.publish('case', self.draft).status, expected)
            run.assert_called_once()

    @patch('triage.skill_publisher.subprocess.run')
    def test_unrelated_credentials_are_not_forwarded_to_jira_runtime(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, json.dumps({'requires_confirmation': True}))
        with patch.dict('os.environ', {'GITLAB_READ_TOKEN': 'gitlab-secret', 'TELEGRAM_BOT_TOKEN': 'telegram-secret'}):
            self.publisher.publish('case', self.draft)
        env = run.call_args.kwargs['env']
        self.assertNotIn('GITLAB_READ_TOKEN', env)
        self.assertNotIn('TELEGRAM_BOT_TOKEN', env)
