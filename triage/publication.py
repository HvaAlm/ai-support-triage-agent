"""Confirmed ticket publication; intentionally no Jira client or skill runner."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
import os
import sqlite3
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True)
class Publication:
    status: str
    issue_key: str | None = None
    jira_url: str | None = None
    errors: tuple[str, ...] = ()


class Publisher(Protocol):
    def publish(self, case_id: str, draft: dict) -> Publication:
        """Accept the confirmed draft and return actual runtime results."""
        ...


class DryRunPublisher:
    def publish(self, case_id: str, draft: dict) -> Publication:
        # Cases persists the exact draft before invoking this boundary.
        return Publication('dry-run', errors=('No Jira issue was created.',))


def configured_publisher() -> Publisher:
    mode = os.environ.get('TICKET_PUBLISHER', 'dry-run')
    if mode == 'dry-run':
        return DryRunPublisher()
    if mode == 'skill':
        from .skill_publisher import SkillPublisher
        return SkillPublisher()
    raise ValueError('TICKET_PUBLISHER must be dry-run or skill')


def validate_draft(draft: dict) -> str:
    if not isinstance(draft, dict):
        raise ValueError('Draft must be a JSON object')
    for key in ('title', 'description'):
        if not isinstance(draft.get(key), str) or not draft[key].strip():
            raise ValueError(f'Draft requires a nonempty {key}')
    attachments = draft.get('attachments', [])
    if not isinstance(attachments, list) or any(
        not isinstance(a, dict) or not all(isinstance(a.get(k), str) and a[k]
            for k in ('name', 'reference', 'sha256')) for a in attachments
    ):
        raise ValueError('Attachments require name, reference, and sha256')
    return json.dumps(draft, sort_keys=True, allow_nan=False)


class Cases:
    def __init__(self, database):
        self.database = str(database)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY, owner TEXT NOT NULL, revision TEXT NOT NULL,
                draft TEXT NOT NULL, result TEXT, attempted INTEGER NOT NULL DEFAULT 0)''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def prepare(self, case_id: str, owner: str, draft: dict, *, expected_session_version=None) -> str:
        """Save a preview. Investigation may prepare drafts but must never confirm."""
        if not case_id or not owner:
            raise ValueError('case_id and owner are required')
        encoded = validate_draft(draft)
        revision = uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if expected_session_version is not None:
                current = db.execute('SELECT version FROM sessions WHERE case_id=? AND owner=?', (case_id, owner)).fetchone()
                if not current or current[0] != expected_session_version:
                    raise ValueError('Case changed during preview; request a new preview')
            row = db.execute('SELECT owner, attempted FROM cases WHERE case_id=?', (case_id,)).fetchone()
            if row and row[0] != owner:
                raise PermissionError('Only the case owner may update this preview')
            if row and row[1]:
                raise ValueError('Publication already attempted; reconcile before modifying this case')
            db.execute('''INSERT INTO cases(case_id, owner, revision, draft) VALUES(?,?,?,?)
                ON CONFLICT(case_id) DO UPDATE SET revision=excluded.revision,
                draft=excluded.draft, result=NULL''', (case_id, owner, revision, encoded))
        return revision

    def preview(self, case_id: str, actor: str) -> dict:
        with self.connect() as db:
            row = db.execute('SELECT owner, revision, draft, result FROM cases WHERE case_id=?', (case_id,)).fetchone()
        if row is None:
            raise KeyError(case_id)
        if row[0] != actor:
            raise PermissionError('Only the case owner may view this preview')
        return dict(case_id=case_id, revision=row[1], draft=json.loads(row[2]),
                    publication=json.loads(row[3]) if row[3] else None)

    def confirm(self, case_id: str, actor: str, revision: str,
                publisher: Publisher, *, confirmed: bool = False) -> Publication:
        if confirmed is not True:
            raise ValueError('Explicit owner confirmation is required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT owner, revision, draft, result, attempted FROM cases WHERE case_id=?', (case_id,)).fetchone()
            if row is None:
                raise KeyError(case_id)
            if row[0] != actor:
                raise PermissionError('Only the case owner may confirm')
            if row[1] != revision:
                raise ValueError('Preview changed; view and confirm the current revision')
            if row[4]:
                saved = json.loads(row[3])
                saved['errors'] = tuple(saved['errors'])
                return Publication(**saved)
            reserved = Publication('unknown', errors=(
                'Publication may be in progress or may have succeeded. Reconcile before retrying.',))
            # Commit before external work; crashes and concurrent confirmations cannot retry.
            db.execute('UPDATE cases SET attempted=1, result=? WHERE case_id=?',
                       (json.dumps(asdict(reserved)), case_id))
        try:
            result = publisher.publish(case_id, json.loads(row[2]))
            if not isinstance(result, Publication) or result.status not in {
                'published', 'dry-run', 'pending', 'failed', 'unknown'
            }:
                raise ValueError('Invalid publisher result')
            if result.status == 'published' and not (result.issue_key and result.jira_url):
                raise ValueError('Publisher omitted the actual key or URL')
        except Exception:
            # Raw runtime exceptions can contain secrets. Do not persist them.
            result = Publication('unknown', errors=(
                'Publisher failed or returned an invalid result; creation may have succeeded. '
                'Do not retry before reconciling with the skill runtime.',))
        with self.connect() as db:
            db.execute('UPDATE cases SET result=? WHERE case_id=?',
                       (json.dumps(asdict(result)), case_id))
        return result
