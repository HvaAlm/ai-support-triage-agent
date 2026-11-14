from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from triage.application import Application
from triage.config import Settings
from triage.telegram import TelegramBot, TelegramError


class FakeTelegram:
    def __init__(self): self.sent = []; self.downloaded = []
    def send(self, chat_id, text): self.sent.append((chat_id, text))
    def download_photo(self, file_id, max_bytes):
        self.downloaded.append(file_id)
        return b'\xff\xd8\xffphoto'


class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.settings = Settings(database=root/'cases.db', attachments=root/'photos', telegram_users=frozenset({11,22}))
        self.app = Application(self.settings)
        self.api = FakeTelegram()
        self.bot = TelegramBot(self.app, self.api)

    def update(self, update_id, text=None, user=11, chat_type='private', **other):
        message = {'from': {'id': user}, 'chat': {'id': user, 'type': chat_type}, **other}
        if text: message['text'] = text
        return {'update_id': update_id, 'message': message}

    def test_private_allowlist_and_owner_isolation(self):
        self.bot.dispatch(self.update(1, '/new احساس اشتباه', user=33))
        self.bot.dispatch(self.update(2, '/new احساس اشتباه', chat_type='group'))
        self.assertEqual(self.api.sent, [])
        self.bot.dispatch(self.update(3, '/new احساس اشتباه'))
        case = self.app.store.active('telegram:11')
        self.bot.dispatch(self.update(4, '/use ' + case['case_id'], user=22))
        self.assertIn('صاحب پرونده', self.api.sent[-1][1])

    def test_duplicate_updates_do_not_advance_questions_twice_after_restart(self):
        self.bot.dispatch(self.update(10, '/new احساس اشتباه'))
        update = self.update(11, '1')
        self.bot.dispatch(update)
        self.bot = TelegramBot(Application(self.settings), self.api)
        self.bot.dispatch(update)
        data = self.bot.app.store.active('telegram:11')['data']
        self.assertEqual(data['scenario'], 'wrong_sentiment')
        self.assertEqual(data['answers'], {})
        self.assertEqual(self.bot.app.store.offset(), 12)

    def test_interrupted_update_does_not_replay_domain_action(self):
        self.app.store.reserve_update(9)
        self.bot.dispatch(self.update(9, '/new احساس اشتباه'))
        self.assertIsNone(self.app.store.active('telegram:11'))
        self.assertIn('/status', self.api.sent[-1][1])

    def test_photo_attachment_only_and_unsupported_media(self):
        self.bot.dispatch(self.update(1, '/new خلاصه اشتباه'))
        self.bot.dispatch(self.update(2, photo=[{'file_id': 'photo'}]))
        self.assertEqual(self.api.downloaded, ['photo'])
        self.assertEqual(len(self.app.store.active('telegram:11')['data']['attachments']), 1)
        self.assertIsNone(self.app.store.active('telegram:11')['data']['investigation'])
        self.bot.dispatch(self.update(3, voice={'file_id': 'voice'}))
        self.assertEqual(self.api.downloaded, ['photo'])
        self.assertIn('صدا', self.api.sent[-1][1])

    def test_allowlist_required(self):
        with self.assertRaises(TelegramError):
            TelegramBot(Application(replace(self.settings, telegram_users=frozenset())), self.api)

    def test_send_failure_replays_response_not_case_creation(self):
        update = self.update(10, '/new احساس اشتباه')
        original_send = self.api.send
        self.api.send = lambda *a: (_ for _ in ()).throw(TelegramError('send failed'))
        with self.assertRaises(TelegramError): self.bot.dispatch(update)
        self.assertEqual(self.app.store.offset(), 0)
        self.api.send = original_send
        self.bot.dispatch(update)
        self.assertEqual(len(self.app.store.list_cases('telegram:11')), 1)
        self.assertEqual(self.app.store.offset(), 11)

    def test_older_duplicate_does_not_move_offset_backwards(self):
        self.bot.dispatch(self.update(1, '/new احساس اشتباه'))
        self.bot.dispatch(self.update(2, '1'))
        self.bot.dispatch(self.update(1, '/new احساس اشتباه'))
        self.assertEqual(self.app.store.offset(), 3)
