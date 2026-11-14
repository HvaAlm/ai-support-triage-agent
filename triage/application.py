"""Shared Persian case workflow for CLI and Telegram."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from .investigation import CodexInvestigator, MockInvestigator
from .publication import configured_publisher, DryRunPublisher
from .scenarios import FEATURES, SCENARIOS, classify, next_question, normalize, questions
from .store import Store

HELP = '''گزارش مشکل را به فارسی بفرستید یا از دستورها استفاده کنید:
/new شرح مشکل — پرونده جدید
/cases — پرونده‌های شما
/use شناسه — ادامه پرونده
/status — وضعیت و سؤال بعدی
/answer نام_فیلد پاسخ — اصلاح پاسخ (پیش‌نمایش قبلی باطل می‌شود)
/investigate — بررسی فقط‌خواندنی بک‌اند پس از تکمیل پرسش‌ها
/preview — پیش‌نمایش تیکت
/confirm شناسه نسخه — تأیید همان پیش‌نمایش
/handoff — خروجی کامل پرونده برای تحویل دستی
/catalog — مسیرهای کشف‌شده با شاهد و commit
عکس فقط ضمیمه است؛ تحلیل تصویر، صدا، ویدئو، فرانت‌اند و اصلاح خودکار پشتیبانی نمی‌شود.'''


def ticket_draft(case, settings):
    data = case['data']
    result = data['investigation']
    details = [f"پرونده: {case['case_id']}", f"قابلیت: {data['feature']}", f"سناریو: {data['scenario']}",
               'گزارش کاربر (تأیید فنی نشده):', data['report'], 'پاسخ‌های کاربر:',
               json.dumps(data['answers'], ensure_ascii=False, indent=2), 'خلاصه بررسی:', result['summary'],
               'شواهد کد (وجود نقل‌قول بررسی شده است، نه اثبات علت در زمان اجرا):',
               json.dumps(result['facts'], ensure_ascii=False, indent=2), 'علت‌های احتمالی — فرضیه، نه واقعیت قطعی:',
               json.dumps(result['hypotheses'], ensure_ascii=False, indent=2), 'اصلاحات پیشنهادی — اجرا نشده:',
               json.dumps(result['suggested_fixes'], ensure_ascii=False, indent=2), 'محدودیت‌ها:',
               json.dumps(result['limitations'], ensure_ascii=False, indent=2)]
    if result['mode'] == 'mock':
        details.insert(0, 'آزمایشی آفلاین / OFFLINE MOCK — هیچ کد واقعی بررسی نشده است.')
    if result.get('source'):
        details.append('منبع: ' + json.dumps(result['source'], ensure_ascii=False))
    return dict(title=f"[{data['feature']}] {data['report'].splitlines()[0][:120]}",
                description='\n\n'.join(details), project=settings.ticket_project,
                issue_type=settings.ticket_issue_type, attachments=data['attachments'])


class Application:
    def __init__(self, settings, *, investigator=None, publisher=None):
        self.settings = settings
        self.store = Store(settings.database)
        self.investigator = investigator or (MockInvestigator() if settings.mode == 'mock' else CodexInvestigator(settings))
        self.publisher = publisher or (DryRunPublisher() if settings.mode == 'mock' else configured_publisher())

    def banner(self):
        return 'آزمایشی آفلاین / OFFLINE MOCK — بررسی واقعی انجام نمی‌شود.\n' if self.settings.mode == 'mock' else ''

    def current(self, actor):
        case = self.store.active(actor)
        if not case:
            raise ValueError('ابتدا /new و شرح مشکل را بفرستید.')
        return case

    def status(self, case):
        data = case['data']
        prompt = next_question(data)
        if not prompt:
            prompt = '/preview برای پیش‌نمایش تیکت.' if data['investigation'] else 'پاسخ‌ها کامل است. /investigate برای بررسی بک‌اند.'
        fields = ', '.join(data['answers']) or '—'
        try:
            publication = self.store.publications.preview(case['case_id'], case['owner'])['publication']
        except KeyError:
            publication = None
        return (f"پرونده: {case['case_id']}\nقابلیت: {data['feature'] or 'نامشخص'}\nسناریو: {data['scenario'] or 'نامشخص'}\n"
                f"پاسخ‌های ثبت‌شده: {fields}\nضمیمه‌ها: {len(data['attachments'])}\n{prompt}" +
                ('\nنتیجه انتشار: ' + json.dumps(publication, ensure_ascii=False) if publication else '') +
                ('\nخطای بررسی: ' + data['investigation_error'] if data.get('investigation_error') else ''))

    def handle(self, actor, text):
        if not text.strip() or len(text) > 16000:
            raise ValueError('پیام باید بین ۱ و ۱۶۰۰۰ نویسه باشد.')
        response = self._handle(actor, text.strip())
        return self.banner() + response

    def _handle(self, actor, text):
        command, _, argument = text.partition(' ')
        if command in ('/start', '/help'):
            return HELP
        if command == '/catalog':
            return json.dumps(self.store.catalog(), ensure_ascii=False, indent=2) or '[]'
        if command == '/cases':
            return '\n'.join(self.store.list_cases(actor)) or 'هنوز پرونده‌ای ندارید.'
        if command == '/use':
            return self.status(self.store.select(actor, argument.strip()))
        if command == '/new' or (not text.startswith('/') and not self.store.active(actor)):
            report = argument.strip() if command == '/new' else text
            if not report:
                raise ValueError('شرح مشکل را پس از /new بنویسید.')
            case = self.store.create(actor, report, self.settings.mode)
            case['data']['feature'] = classify(report)
            case['data']['messages'].append({'role': 'assistant', 'text': next_question(case['data'])})
            self.store.save(case)
            return self.status(case)
        case = self.current(actor)
        data = case['data']
        if command == '/status':
            return self.status(case)
        if command == '/handoff':
            handoff = dict(case_id=case['case_id'], data=data)
            try:
                handoff['ticket'] = self.store.publications.preview(case['case_id'], actor)
            except KeyError:
                pass
            return json.dumps(handoff, ensure_ascii=False, indent=2)
        if command == '/confirm':
            parts = argument.split()
            if len(parts) != 2:
                raise ValueError('دستور کامل /confirm شناسه_پرونده نسخه_پیش‌نمایش را بفرستید.')
            target = self.store.get(parts[0], actor)
            if target['data']['mode'] != self.settings.mode:
                raise ValueError('حالت پرونده با حالت اجرای فعلی متفاوت است؛ انتشار انجام نشد.')
            result = self.store.publications.confirm(parts[0], actor, parts[1], self.publisher, confirmed=True)
            prefix = 'هیچ تیکت Jira ساخته نشد.\n' if result.status == 'dry-run' else ''
            return prefix + json.dumps(asdict(result), ensure_ascii=False, indent=2)
        if command == '/investigate':
            if next_question(data):
                raise ValueError('ابتدا پاسخ‌ها را کامل کنید:\n' + next_question(data))
            if data['mode'] != self.settings.mode:
                raise ValueError('حالت پرونده تغییر نمی‌کند؛ برای حالت جدید پرونده تازه بسازید.')
            # Check editability and persist the request before invoking external analysis.
            data['messages'].append({'role': 'user', 'text': text})
            self.store.save(case)
            try:
                data['investigation'] = self.investigator.investigate(data)
                data['investigation_error'] = None
            except ValueError as exc:
                data['investigation'] = None
                data['investigation_error'] = str(exc)
                self.store.save(case)
                return str(exc)
            self.store.save(case)
            return json.dumps(data['investigation'], ensure_ascii=False, indent=2) + '\n/preview برای دیدن تیکت.'
        if command == '/preview':
            if not data['investigation']:
                raise ValueError('ابتدا /investigate را انجام دهید؛ پیش‌نمایش بدون نتیجه بررسی ساخته نمی‌شود.')
            try:
                existing = self.store.publications.preview(case['case_id'], actor)
                if existing['publication']:
                    return json.dumps(existing, ensure_ascii=False, indent=2)
            except KeyError:
                pass
            draft = ticket_draft(case, self.settings)
            revision = self.store.publications.prepare(case['case_id'], actor, draft, expected_session_version=case['version'])
            return ('پیش‌نمایش — هنوز هیچ تیکتی ساخته نشده است:\n' + json.dumps(draft, ensure_ascii=False, indent=2) +
                    f"\nبرای تأیید همین نسخه دقیقاً بفرستید:\n/confirm {case['case_id']} {revision}")
        if command == '/answer':
            key, _, value = argument.partition(' ')
            if not data['scenario'] or key not in {k for k, _ in questions(data)} or not value.strip():
                raise ValueError('نام فیلد معتبر و پاسخ لازم است؛ /status نام پاسخ‌های ثبت‌شده را نشان می‌دهد.')
            data['answers'][key] = value.strip()
        elif text.startswith('/'):
            raise ValueError('دستور ناشناخته است؛ /help را ببینید.')
        elif not data['feature']:
            choice = normalize(text).translate(str.maketrans('۱۲۳۴', '1234'))
            feature = {'1': FEATURES[0], '2': FEATURES[1]}.get(choice) or classify(text)
            if not feature:
                return next_question(data)
            data['feature'] = feature
        elif not data['scenario']:
            choice = normalize(text).translate(str.maketrans('۱۲۳۴', '1234'))
            choices = SCENARIOS[data['feature']]
            selected = choices.get(choice) or next((v for v in choices.values() if choice == v[0]), None)
            if not selected:
                return next_question(data)
            data['scenario'] = selected[0]
        else:
            missing = next((key for key, _ in questions(data) if key not in data['answers']), None)
            if not missing:
                return 'پاسخ‌ها کامل است؛ برای اصلاح /answer نام_فیلد پاسخ یا برای بررسی /investigate را بفرستید.'
            data['answers'][missing] = text
        data['investigation'] = None
        data['investigation_error'] = None
        data['messages'].append({'role': 'user', 'text': text})
        reply = self.status(case)
        data['messages'].append({'role': 'assistant', 'text': reply})
        self.store.save(case)
        return reply

    def attach_photo(self, actor, content, name='photo.jpg'):
        case = self.current(actor)
        if len(content) > self.settings.max_photo_bytes:
            raise ValueError('عکس از حد مجاز ۱۰ مگابایت بزرگ‌تر است.')
        suffix = None
        if content.startswith(b'\xff\xd8\xff'):
            suffix = '.jpg'
        elif content.startswith(b'\x89PNG\r\n\x1a\n'):
            suffix = '.png'
        elif content.startswith(b'RIFF') and content[8:12] == b'WEBP':
            suffix = '.webp'
        if suffix is None:
            raise ValueError('فقط عکس JPEG، PNG یا WebP پذیرفته می‌شود؛ تصویر تفسیر نمی‌شود.')
        root = self.settings.attachments.resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = root / (uuid4().hex + suffix)
        target.write_bytes(content)
        target.chmod(0o600)
        case['data']['attachments'].append(dict(name=Path(name).name, reference=str(target),
                                                sha256=hashlib.sha256(content).hexdigest()))
        try:
            self.store.save(case)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return self.banner() + 'عکس فقط به‌عنوان ضمیمه ذخیره شد؛ هیچ تفسیر تصویری انجام نشد. پیش‌نمایش قبلی باطل شد.'
