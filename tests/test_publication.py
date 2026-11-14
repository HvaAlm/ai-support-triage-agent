from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from triage.publication import Cases, Publication, DryRunPublisher, configured_publisher


class FakePublisher:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result or Publication('published', 'TEST-42', 'https://jira.example/browse/TEST-42')
        self.error = error

    def publish(self, case_id, draft):
        self.calls.append((case_id, draft))
        if self.error:
            raise self.error
        return self.result


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'cases.sqlite3'
        self.cases = Cases(self.path)
        self.draft = {'title': 'Failure', 'description': 'Observed failure', 'attachments': [
            {'name': 'log.txt', 'reference': 'evidence/log.txt', 'sha256': 'a' * 64}]}
        self.revision = self.cases.prepare('case-1', 'owner', self.draft)
        self.publisher = FakePublisher()

    def confirm(self, **kwargs):
        options = dict(case_id='case-1', actor='owner', revision=self.revision,
                       publisher=self.publisher, confirmed=True)
        options.update(kwargs)
        return self.cases.confirm(**options)

    def test_prepare_and_preview_do_not_publish(self):
        self.assertEqual(self.cases.preview('case-1', 'owner')['draft'], self.draft)
        self.assertEqual(self.publisher.calls, [])

    def test_owner_and_explicit_confirmation(self):
        with self.assertRaises(PermissionError):
            self.confirm(actor='someone-else')
        with self.assertRaises(ValueError):
            self.confirm(confirmed=False)
        with self.assertRaises(PermissionError):
            self.cases.prepare('case-1', 'other', self.draft)
        self.assertEqual(self.publisher.calls, [])

    def test_stale_confirmation_including_reverted_draft(self):
        self.cases.prepare('case-1', 'owner', dict(self.draft, title='Changed'))
        self.cases.prepare('case-1', 'owner', self.draft)
        with self.assertRaises(ValueError):
            self.confirm()
        self.assertEqual(self.publisher.calls, [])

    def test_persists_actual_result_and_deduplicates_after_restart(self):
        result = self.confirm()
        self.cases = Cases(self.path)
        self.assertEqual(self.confirm(), result)
        self.assertEqual(self.publisher.calls, [('case-1', self.draft)])
        saved = self.cases.preview('case-1', 'owner')['publication']
        self.assertEqual(saved['issue_key'], 'TEST-42')
        self.assertEqual(saved['jira_url'], 'https://jira.example/browse/TEST-42')
        with self.assertRaises(ValueError):
            self.cases.prepare('case-1', 'owner', self.draft)

    def test_concurrent_confirmation_calls_publisher_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.confirm(), range(8)))
        self.assertEqual(len(self.publisher.calls), 1)
        self.assertTrue(all(r.status in {'unknown', 'published'} for r in results))
        self.assertEqual(self.confirm().status, 'published')

    def test_timeout_is_unknown_and_not_retried(self):
        self.publisher.error = TimeoutError('secret runtime details')
        self.assertEqual(self.confirm().status, 'unknown')
        self.confirm()
        self.assertEqual(len(self.publisher.calls), 1)
        self.assertEqual(self.cases.preview('case-1', 'owner')['draft'], self.draft)

    def test_process_interruption_leaves_reservation(self):
        self.publisher.error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.confirm()
        self.cases = Cases(self.path)
        self.assertEqual(self.confirm().status, 'unknown')
        self.assertEqual(len(self.publisher.calls), 1)

    def test_partial_creation_preserves_mapping_and_errors(self):
        self.publisher.result = Publication('failed', 'TEST-42', 'https://jira.example/browse/TEST-42',
                                            ('Attachment upload failed',))
        self.assertEqual(self.confirm(), self.publisher.result)
        self.assertEqual(self.confirm(), self.publisher.result)
        self.assertEqual(len(self.publisher.calls), 1)

    def test_success_without_actual_result_is_unknown(self):
        self.publisher.result = Publication('published')
        self.assertEqual(self.confirm().status, 'unknown')

    def test_dry_run_saves_draft_and_never_returns_fake_jira(self):
        result = self.confirm(publisher=DryRunPublisher())
        self.assertEqual(result.status, 'dry-run')
        self.assertIsNone(result.issue_key)
        self.assertIsNone(result.jira_url)
        self.assertIn('No Jira issue was created.', result.errors)
        self.assertEqual(Cases(self.path).preview('case-1', 'owner')['draft'], self.draft)

    def test_skill_pending_and_configuration(self):
        with patch.dict(os.environ, {'TICKET_PUBLISHER': 'skill'}):
            result = self.confirm(publisher=configured_publisher())
        self.assertEqual(result.status, 'pending')
        self.assertIsNone(result.issue_key)
        with patch.dict(os.environ, {'TICKET_PUBLISHER': 'invalid'}):
            with self.assertRaises(ValueError):
                configured_publisher()

    def test_invalid_draft(self):
        for draft in ({}, {'title': 'X', 'description': 'Y', 'attachments': ['file']}):
            with self.assertRaises(ValueError):
                self.cases.prepare('other', 'owner', draft)


if __name__ == '__main__':
    unittest.main()
