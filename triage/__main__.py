"""CLI and Telegram entry points sharing the same application service."""
import argparse
import getpass
import json
from pathlib import Path
from dataclasses import replace

from .application import Application
from .config import Settings


def main():
    parser = argparse.ArgumentParser(description='Persian support triage: CLI / Telegram')
    parser.add_argument('--database', type=Path, help='Override CASE_DATABASE')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('chat', help='Interactive Persian conversation; /quit exits')
    commands.add_parser('telegram', help='Run the private-chat Telegram bot')
    for name in ('new', 'say'):
        command = commands.add_parser(name)
        command.add_argument('text')
    for name in ('status', 'cases', 'investigate', 'preview', 'handoff', 'catalog'):
        commands.add_parser(name)
    use = commands.add_parser('use')
    use.add_argument('case_id')
    photo = commands.add_parser('photo')
    photo.add_argument('path', type=Path)
    confirm = commands.add_parser('confirm')
    confirm.add_argument('case_id')
    confirm.add_argument('revision')
    prepare = commands.add_parser('prepare', help='Low-level local draft import (no investigation)')
    prepare.add_argument('case_id')
    prepare.add_argument('draft_file', type=Path)
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        if args.database:
            settings = replace(settings, database=args.database)
        app = Application(settings)
        actor = 'cli:' + getpass.getuser()
        if args.command == 'telegram':
            from .telegram import TelegramBot
            TelegramBot(app).run()
        elif args.command == 'chat':
            print(app.handle(actor, '/help'))
            active = app.store.active(actor)
            if active:
                print(app.handle(actor, '/status'))
            while True:
                try:
                    text = input('شما> ')
                except EOFError:
                    break
                if text.strip() == '/quit':
                    break
                try:
                    if text.startswith('/photo '):
                        path = Path(text[7:].strip())
                        with path.open('rb') as stream:
                            content = stream.read(settings.max_photo_bytes + 1)
                        print(app.attach_photo(actor, content, path.name))
                    else:
                        print(app.handle(actor, text))
                except (ValueError, PermissionError, KeyError, OSError) as exc:
                    print(str(exc))
        elif args.command == 'photo':
            with args.path.open('rb') as stream:
                content = stream.read(settings.max_photo_bytes + 1)
            print(app.attach_photo(actor, content, args.path.name))
        elif args.command == 'prepare':
            revision = app.store.publications.prepare(args.case_id, actor, json.loads(args.draft_file.read_text()))
            print(json.dumps(app.store.publications.preview(args.case_id, actor), ensure_ascii=False, indent=2))
            print('Low-level draft saved. No Jira issue was created. Revision: ' + revision)
        elif args.command == 'confirm':
            preview = app.store.publications.preview(args.case_id, actor)
            if preview['revision'] != args.revision:
                raise ValueError('پیش‌نمایش تغییر کرده است؛ نسخه فعلی را ببینید.')
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            if input('برای تأیید همین پیش‌نمایش CONFIRM بنویسید: ') != 'CONFIRM':
                print('لغو شد؛ پرونده حفظ شد.')
                return
            # Support previously imported drafts as well as full conversation cases.
            try:
                app.store.get(args.case_id, actor)
            except ValueError:
                from dataclasses import asdict
                print(json.dumps(asdict(app.store.publications.confirm(args.case_id, actor, args.revision,
                      app.publisher, confirmed=True)), ensure_ascii=False, indent=2))
            else:
                print(app.handle(actor, f'/confirm {args.case_id} {args.revision}'))
        elif args.command in ('new', 'say'):
            print(app.handle(actor, '/new ' + args.text if args.command == 'new' else args.text))
        elif args.command == 'use':
            print(app.handle(actor, '/use ' + args.case_id))
        else:
            print(app.handle(actor, '/' + args.command))
    except (ValueError, PermissionError, KeyError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
    except KeyboardInterrupt:
        print('\nمتوقف شد؛ پرونده‌ها در SQLite حفظ شده‌اند.')


if __name__ == '__main__':
    main()
