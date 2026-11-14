import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CLITests(unittest.TestCase):
    def test_real_offline_cli_processes_persist_and_publish_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, APP_MODE='mock', TICKET_PUBLISHER='dry-run',
                       CASE_DATABASE=str(Path(directory)/'cases.db'), ATTACHMENT_DIR=str(Path(directory)/'photos'))
            def run(*args, input=None):
                return subprocess.run([sys.executable, '-m', 'triage', *args], input=input, env=env,
                                      capture_output=True, text=True, check=True).stdout
            self.assertIn('OFFLINE MOCK', run('new', 'خلاصه‌سازی خروجی نادرست دارد'))
            run('say', '1')
            for answer in ('متن ورودی', 'خروجی نادرست', 'عبارت اشتباه', 'خلاصه درست', 'ارسال متن', 'نسخه تست', 'نامشخص'):
                run('say', answer)
            self.assertIn('/investigate', run('status'))
            run('investigate')
            preview = run('preview')
            confirm = next(line for line in preview.splitlines() if line.startswith('/confirm '))
            _, case_id, revision = confirm.split()
            result = run('confirm', case_id, revision, input='CONFIRM\n')
            self.assertIn('No Jira issue was created.', result)
            self.assertIn('dry-run', run('status'))
            self.assertIn(case_id, run('cases'))
            self.assertIn('خروجی نادرست', run('handoff'))
            self.assertIn('No Jira issue was created.', run('confirm', case_id, revision, input='CONFIRM\n'))
