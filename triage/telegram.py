"""Private-chat Telegram adapter; all case behavior lives in Application."""
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from .gitlab import NoRedirect


class TelegramError(ValueError):
    pass


class TelegramAPI:
    def __init__(self, token):
        if not token:
            raise TelegramError('TELEGRAM_BOT_TOKEN تنظیم نشده است.')
        self._root = 'https://api.telegram.org/bot' + token + '/'
        self._file_root = 'https://api.telegram.org/file/bot' + token + '/'
        self.opener = build_opener(NoRedirect())

    def call(self, method, payload):
        request = Request(self._root + method, data=json.dumps(payload).encode(),
                          headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with self.opener.open(request, timeout=40) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise TelegramError('پاسخ Telegram بیش از حد بزرگ است.')
            result = json.loads(raw)
            if not result.get('ok'):
                raise TelegramError('عملیات Telegram ناموفق بود؛ تنظیمات bot را بررسی کنید.')
            return result['result']
        except (HTTPError, URLError, OSError, ValueError, KeyError):
            # urllib exception strings include token-bearing URLs. Never log/return them.
            raise TelegramError('ارتباط Telegram ناموفق بود؛ توکن و شبکه را بررسی کنید.') from None

    def download_photo(self, file_id, max_bytes):
        info = self.call('getFile', {'file_id': file_id})
        path = info.get('file_path', '')
        if not path.startswith('photos/') or '..' in path or '\\' in path or '?' in path:
            raise TelegramError('مسیر فایل Telegram مجاز نیست.')
        if info.get('file_size', 0) > max_bytes:
            raise TelegramError('عکس از حد مجاز بزرگ‌تر است.')
        try:
            with self.opener.open(self._file_root + path, timeout=30) as response:
                content = response.read(max_bytes + 1)
        except (HTTPError, URLError, OSError):
            raise TelegramError('دریافت عکس Telegram ناموفق بود.') from None
        if len(content) > max_bytes:
            raise TelegramError('عکس از حد مجاز بزرگ‌تر است.')
        return content

    def send(self, chat_id, text):
        # Plain text avoids interpreting ticket/report content as Telegram markup.
        for start in range(0, len(text), 3000):
            self.call('sendMessage', {'chat_id': chat_id, 'text': text[start:start+3000]})


class TelegramBot:
    def __init__(self, application, api=None):
        self.app = application
        if not application.settings.telegram_users:
            raise TelegramError('TELEGRAM_ALLOWED_USER_IDS باید شناسه عددی کاربران مجاز را مشخص کند.')
        self.api = api or TelegramAPI(application.settings.telegram_token)

    def dispatch(self, update):
        update_id = update['update_id']
        message = update.get('message')
        if not message:
            self.app.store.finish_update(update_id, '')
            return
        user = message.get('from', {}).get('id')
        chat = message.get('chat', {})
        if user not in self.app.settings.telegram_users or chat.get('type') != 'private':
            # Do not expose case state or process attachments for unauthorised/group input.
            self.app.store.finish_update(update_id, '')
            return
        first, previous = self.app.store.reserve_update(update_id)
        if not first:
            response = previous or 'پردازش قبلی ممکن است قطع شده باشد. /status را ببینید؛ انتشار دوباره انجام نشد.'
        else:
            actor = f'telegram:{user}'
            try:
                if message.get('photo'):
                    if not self.app.store.active(actor):
                        if not message.get('caption'):
                            raise ValueError('ابتدا شرح مشکل را با /new بفرستید، سپس عکس را ضمیمه کنید.')
                        self.app.handle(actor, '/new ' + message['caption'])
                    photo = message['photo'][-1]
                    content = self.api.download_photo(photo['file_id'], self.app.settings.max_photo_bytes)
                    response = self.app.attach_photo(actor, content)
                elif any(key in message for key in ('voice', 'video', 'video_note', 'audio', 'document', 'animation', 'sticker')):
                    response = 'فقط متن فارسی و عکس به‌عنوان ضمیمه پذیرفته می‌شود؛ تحلیل تصویر، صدا یا ویدئو نداریم.'
                elif message.get('text'):
                    response = self.app.handle(actor, message['text'])
                else:
                    response = 'پیام متنی یا عکس بفرستید.'
            except (ValueError, PermissionError, KeyError) as exc:
                response = str(exc)
        # Store result before sending: duplicate delivery never repeats domain actions.
        self.app.store.save_update_response(update_id, response)
        self.api.send(chat['id'], response)
        self.app.store.finish_update(update_id, response)

    def run(self):
        print('Telegram polling started. Private allowlisted chats only. Ctrl-C to stop.')
        while True:
            try:
                updates = self.api.call('getUpdates', {'offset': self.app.store.offset(), 'timeout': 25,
                                                      'allowed_updates': ['message']})
                for update in updates:
                    self.dispatch(update)
            except TelegramError as exc:
                print(str(exc), flush=True)
                time.sleep(3)
