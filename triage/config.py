"""Validated application settings; Jira authentication belongs to the skill runtime."""
from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database: Path = Path('data/cases.sqlite3')
    attachments: Path = Path('data/attachments')
    mode: str = 'mock'
    gitlab_base_url: str = 'https://git.example.com'
    gitlab_project_path: str = 'group/backend'
    backend_ref: str | None = None
    codex_binary: str = 'codex'
    investigation_timeout: int = 180
    ticket_project: str = ''
    ticket_issue_type: str = 'Bug'
    telegram_token: str = ''
    telegram_users: frozenset[int] = frozenset()
    max_photo_bytes: int = 10 * 1024 * 1024

    @classmethod
    def from_env(cls):
        mode = os.getenv('APP_MODE', 'mock')
        if mode not in {'mock', 'live'}:
            raise ValueError('APP_MODE must be mock or live')
        timeout = int(os.getenv('INVESTIGATION_TIMEOUT_SECONDS', '180'))
        if timeout < 1:
            raise ValueError('INVESTIGATION_TIMEOUT_SECONDS must be positive')
        if mode == 'mock' and os.getenv('TICKET_PUBLISHER', 'dry-run') != 'dry-run':
            raise ValueError('Offline mock mode requires TICKET_PUBLISHER=dry-run')
        return cls(database=Path(os.getenv('CASE_DATABASE', 'data/cases.sqlite3')),
                   attachments=Path(os.getenv('ATTACHMENT_DIR', 'data/attachments')),
                   mode=mode, gitlab_base_url=os.getenv('GITLAB_BASE_URL', 'https://git.example.com'),
                   gitlab_project_path=os.getenv('GITLAB_PROJECT_PATH', 'group/backend'),
                   backend_ref=os.getenv('BACKEND_REF') or None,
                   codex_binary=os.getenv('CODEX_BINARY', 'codex'), investigation_timeout=timeout,
                   ticket_project=os.getenv('TICKET_PROJECT', ''),
                   ticket_issue_type=os.getenv('TICKET_ISSUE_TYPE', 'Bug'),
                   telegram_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
                   telegram_users=frozenset(int(x.strip()) for x in os.getenv('TELEGRAM_ALLOWED_USER_IDS', '').split(',') if x.strip()))
