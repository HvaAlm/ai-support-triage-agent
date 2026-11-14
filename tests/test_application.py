from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from triage.application import Application
from triage.config import Settings
from triage.publication import Publication
from triage.scenarios import FEATURES, SCENARIOS, questions


class RecordingPublisher:
    def __init__(self): self.calls = []
    def publish(self, case_id, draft):
        self.calls.append((case_id, draft))
        return Publication('published', 'FIXTURE-1', 'https://fixture.invalid/1')


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(database=Path(self.temp.name)/'cases.db', attachments=Path(self.temp.name)/'photos')
        self.app = Application(self.settings)
        self.actor = 'cli:owner'

    def ready(self, feature=FEATURES[0], scenario='1'):
        self.app.handle(self.actor, '/new مشکل در ' + feature)
        self.app.handle(self.actor, scenario)
        case = self.app.current(self.actor)
        for key, _ in questions(case['data']):
            self.app.handle(self.actor, 'پاسخ آزمایشی ' + key)
        return self.app.current(self.actor)

    def test_both_features_and_every_scenario(self):
        for feature in FEATURES:
            for scenario in SCENARIOS[feature]:
                case = self.ready(feature, scenario)
                self.assertIn('/investigate', self.app.handle(self.actor, '/status'))
                self.assertIsNone(case['data']['investigation'])
                self.app.handle(self.actor, '/investigate')
                preview_text = self.app.handle(self.actor, '/preview')
                self.assertIn('OFFLINE MOCK', preview_text)
                preview = self.app.store.publications.preview(case['case_id'], self.actor)
                result = self.app.handle(self.actor, f"/confirm {case['case_id']} {preview['revision']}")
                self.assertIn('No Jira issue was created.', result)
                self.assertIsNone(self.app.store.publications.preview(case['case_id'], self.actor)['publication']['issue_key'])

    def test_ambiguous_feature_asks_instead_of_guessing(self):
        self.app.handle(self.actor, '/new احساس و خلاصه هر دو مشکل دارند')
        self.assertIsNone(self.app.current(self.actor)['data']['feature'])
        self.app.handle(self.actor, '۲')
        self.assertEqual(self.app.current(self.actor)['data']['feature'], FEATURES[1])

    def test_restart_preserves_followup_answers_and_history(self):
        self.app.handle(self.actor, '/new تحلیل احساسات اشتباه است')
        self.app.handle(self.actor, '1')
        self.app.handle(self.actor, 'این محصول خوب است')
        self.app = Application(self.settings)
        self.assertIn('خروجی واقعی', self.app.handle(self.actor, '/status'))
        self.assertEqual(self.app.current(self.actor)['data']['answers']['input'], 'این محصول خوب است')
        self.assertGreater(len(self.app.current(self.actor)['data']['messages']), 3)

    def test_investigation_never_publishes_and_edits_invalidate_preview(self):
        publisher = RecordingPublisher()
        self.app = Application(self.settings, publisher=publisher)
        case = self.ready()
        self.app.handle(self.actor, '/investigate')
        self.app.handle(self.actor, '/preview')
        revision = self.app.store.publications.preview(case['case_id'], self.actor)['revision']
        self.assertEqual(publisher.calls, [])
        self.app.handle(self.actor, '/answer actual خروجی اصلاح‌شده')
        with self.assertRaises(KeyError):
            self.app.handle(self.actor, f"/confirm {case['case_id']} {revision}")
        self.assertEqual(publisher.calls, [])

    def test_owner_authorization(self):
        case = self.ready()
        with self.assertRaises(PermissionError):
            self.app.handle('telegram:2', '/use ' + case['case_id'])
        self.assertEqual(self.app.store.list_cases('telegram:2'), [])

    def test_photos_are_opaque_and_invalidate_preview(self):
        case = self.ready()
        self.app.handle(self.actor, '/investigate')
        self.app.handle(self.actor, '/preview')
        content = b'\x89PNG\r\n\x1a\nopaque-image'
        self.app.attach_photo(self.actor, content, '../../photo.png')
        case = self.app.current(self.actor)
        self.assertEqual(case['data']['attachments'][0]['name'], 'photo.png')
        self.assertEqual(Path(case['data']['attachments'][0]['reference']).read_bytes(), content)
        with self.assertRaises(KeyError):
            self.app.store.publications.preview(case['case_id'], self.actor)
        with self.assertRaises(ValueError):
            self.app.attach_photo(self.actor, b'voice data')

    def test_failed_live_investigation_does_not_fallback_to_mock(self):
        class Broken:
            def investigate(self, data): raise ValueError('GitLab unavailable')
        self.settings = replace(self.settings, mode='live')
        self.app = Application(self.settings, investigator=Broken(), publisher=RecordingPublisher())
        self.ready()
        self.assertIn('GitLab unavailable', self.app.handle(self.actor, '/investigate'))
        self.assertIsNone(self.app.current(self.actor)['data']['investigation'])
        with self.assertRaises(ValueError): self.app.handle(self.actor, '/preview')
        self.assertTrue(self.app.current(self.actor)['data']['answers'])

    def test_concurrent_save_cannot_overwrite_new_state_or_preview(self):
        case = self.ready()
        stale = self.app.store.get(case['case_id'], self.actor)
        self.app.store.save(case)
        with self.assertRaises(ValueError): self.app.store.save(stale)
        with self.assertRaises(ValueError):
            self.app.store.publications.prepare(case['case_id'], self.actor,
                {'title': 'stale', 'description': 'stale'}, expected_session_version=stale['version'])

    def test_offline_settings_reject_real_publisher(self):
        with patch.dict('os.environ', {'APP_MODE': 'mock', 'TICKET_PUBLISHER': 'skill'}):
            with self.assertRaises(ValueError): Settings.from_env()
