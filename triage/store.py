"""Persistent conversation state and optimistic case updates."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from .publication import Cases


class Store:
    def __init__(self, database):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.publications = Cases(self.database)
        self.database.chmod(0o600)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (
                    case_id TEXT PRIMARY KEY, owner TEXT NOT NULL, version INTEGER NOT NULL,
                    data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS active_cases (owner TEXT PRIMARY KEY, case_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS telegram_updates (
                    update_id INTEGER PRIMARY KEY, response TEXT);
                CREATE TABLE IF NOT EXISTS feature_catalog (
                    feature TEXT, project TEXT, commit_sha TEXT, entries TEXT NOT NULL,
                    PRIMARY KEY(feature, project, commit_sha));
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, owner, report, mode):
        case_id = uuid4().hex[:16]
        data = dict(report=report, feature=None, scenario=None, answers={}, attachments=[],
                    investigation=None, investigation_error=None, mode=mode,
                    messages=[{'role': 'user', 'text': report}])
        with self.connect() as db:
            db.execute('INSERT INTO sessions VALUES (?,?,0,?)', (case_id, owner, json.dumps(data, ensure_ascii=False)))
            db.execute('INSERT INTO active_cases VALUES (?,?) ON CONFLICT(owner) DO UPDATE SET case_id=excluded.case_id', (owner, case_id))
        return self.get(case_id, owner)

    def get(self, case_id, owner):
        with self.connect() as db:
            row = db.execute('SELECT owner,version,data FROM sessions WHERE case_id=?', (case_id,)).fetchone()
        if row is None:
            raise ValueError('پرونده پیدا نشد.')
        if row[0] != owner:
            raise PermissionError('فقط صاحب پرونده به آن دسترسی دارد.')
        return dict(case_id=case_id, owner=owner, version=row[1], data=json.loads(row[2]))

    def active(self, owner):
        with self.connect() as db:
            row = db.execute('SELECT case_id FROM active_cases WHERE owner=?', (owner,)).fetchone()
        return self.get(row[0], owner) if row else None

    def select(self, owner, case_id):
        case = self.get(case_id, owner)
        with self.connect() as db:
            db.execute('INSERT INTO active_cases VALUES (?,?) ON CONFLICT(owner) DO UPDATE SET case_id=excluded.case_id', (owner, case_id))
        return case

    def list_cases(self, owner):
        with self.connect() as db:
            return [r[0] for r in db.execute('SELECT case_id FROM sessions WHERE owner=? ORDER BY rowid DESC', (owner,))]

    def save(self, case):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            publication = db.execute('SELECT attempted FROM cases WHERE case_id=?', (case['case_id'],)).fetchone()
            if publication and publication[0]:
                raise ValueError('انتشار قبلاً تلاش شده است؛ ابتدا نتیجه را بررسی کنید. پرونده حفظ شده است.')
            changed = db.execute('UPDATE sessions SET data=?,version=version+1 WHERE case_id=? AND owner=? AND version=?',
                                 (json.dumps(case['data'], ensure_ascii=False), case['case_id'], case['owner'], case['version'])).rowcount
            if not changed:
                raise ValueError('پرونده همزمان تغییر کرد؛ /status را ببینید و دوباره تلاش کنید.')
            db.execute('DELETE FROM cases WHERE case_id=? AND attempted=0', (case['case_id'],))
            source = (case['data'].get('investigation') or {}).get('source')
            if source:
                db.execute('INSERT OR REPLACE INTO feature_catalog VALUES (?,?,?,?)',
                           (case['data']['feature'], source['project'], source['commit_sha'],
                            json.dumps(source['verified_paths'], ensure_ascii=False)))
        case['version'] += 1

    def reserve_update(self, update_id):
        with self.connect() as db:
            changed = db.execute('INSERT OR IGNORE INTO telegram_updates(update_id) VALUES (?)', (update_id,)).rowcount
            response = db.execute('SELECT response FROM telegram_updates WHERE update_id=?', (update_id,)).fetchone()[0]
        return bool(changed), response

    def save_update_response(self, update_id, response):
        with self.connect() as db:
            db.execute('UPDATE telegram_updates SET response=? WHERE update_id=?', (response, update_id))

    def finish_update(self, update_id, response):
        with self.connect() as db:
            db.execute('UPDATE telegram_updates SET response=? WHERE update_id=?', (response, update_id))
            db.execute("INSERT INTO settings VALUES ('telegram_offset',?) ON CONFLICT(key) DO UPDATE SET value=CAST(MAX(CAST(settings.value AS INTEGER), CAST(excluded.value AS INTEGER)) AS TEXT)", (str(update_id + 1),))

    def offset(self):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key='telegram_offset'").fetchone()
        return int(row[0]) if row else 0

    def catalog(self):
        with self.connect() as db:
            return [dict(feature=r[0], project=r[1], commit_sha=r[2], verified_paths=json.loads(r[3]))
                    for r in db.execute('SELECT feature, project, commit_sha, entries FROM feature_catalog')]
