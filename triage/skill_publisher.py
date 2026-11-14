"""Adapter to the supplied jira-create-issue skill's documented CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys

from .publication import Publication


class SkillPublisher:
    def publish(self, case_id: str, draft: dict) -> Publication:
        default_script = Path(__file__).resolve().parent.parent / 'agent/skills/jira/scripts/jira_tool.py'
        script = Path(os.environ.get('TICKET_SKILL_SCRIPT', str(default_script))).expanduser().resolve()
        if not script.is_file():
            return Publication('pending', errors=('Jira skill CLI is missing. Use the saved draft for manual handoff.',))
        if draft.get('attachments'):
            return Publication('pending', errors=(
                'The supplied Jira skill has no attachment-upload operation. '
                'Manual handoff is required; no Jira issue was created.',))
        supported = {'title', 'description', 'project', 'issue_type', 'parent_key',
                     'labels', 'assignee_account_id', 'priority', 'components',
                     'custom_fields', 'attachments'}
        if set(draft) - supported:
            return Publication('pending', errors=(
                'Unsupported structured fields: ' + ', '.join(sorted(set(draft) - supported)) +
                '. Include their content in the preview description or use documented custom_fields; '
                'no Jira issue was created.',))
        for field in ('project', 'issue_type'):
            if not isinstance(draft.get(field), str) or not draft[field].strip():
                return Publication('pending', errors=(f'Confirmed preview must include {field}; no Jira issue was created.',))
        if draft['issue_type'] == 'Sub-task' and not draft.get('parent_key'):
            return Publication('pending', errors=('Sub-task requires parent_key; no Jira issue was created.',))
        command = [sys.executable, str(script), 'create_issue', '--project', draft['project'],
                   '--summary', draft['title'], '--issue_type', draft['issue_type'],
                   '--description', draft['description'], '--confirm']
        for field in ('parent_key', 'assignee_account_id', 'priority', 'labels', 'components', 'custom_fields'):
            if field not in draft:
                continue
            value = draft[field]
            if field in ('labels', 'components'):
                if not isinstance(value, list) or any(not isinstance(v, str) or ',' in v for v in value):
                    return Publication('pending', errors=(f'{field} must be a list of strings without commas.',))
                value = ','.join(value)
            elif field == 'custom_fields':
                if not isinstance(value, dict):
                    return Publication('pending', errors=('custom_fields must be an object with verified field IDs.',))
                value = json.dumps(value)
            elif not isinstance(value, str):
                return Publication('pending', errors=(f'{field} must be a string.',))
            command.extend(['--' + field, value])
        # Skill-owned auth uses the inherited runtime environment. Do not read/store credentials.
        # The supplied client retries POST by default; its documented setting disables that.
        env = {key: value for key, value in os.environ.items() if key.startswith('JIRA_') or key in {
            'PATH', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'TMPDIR'}}
        env.update(JIRA_MAX_RETRIES='0', JIRA_AUTO_CONFIRM_WRITES='false')
        completed = subprocess.run(command, cwd=script.parent.parent, env=env,
                                   capture_output=True, text=True, timeout=120, check=False)
        payload = json.loads(completed.stdout)
        issue = payload.get('issue') or {}
        key, url = issue.get('key'), issue.get('url')
        if payload.get('requires_confirmation'):
            return Publication('pending', key, url, ('Skill declined to act and requires confirmation; no automatic retry.',))
        if payload.get('error'):
            error = payload['error']
            message = error.get('message', str(error)) if isinstance(error, dict) else str(error)
            return Publication('unknown', key, url, (message,))
        if completed.returncode != 0 or payload.get('confirmed') is not True or not key or not url:
            return Publication('unknown', key, url, ('Skill did not report a complete successful result; reconcile before retrying.',))
        return Publication('published', key, url)
