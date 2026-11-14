"""Bounded read-only GitLab retrieval. Credentials never leave this layer."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class RetrievalError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


SOURCE_SUFFIXES = {'.py', '.go', '.js', '.ts', '.java', '.rb', '.cs', '.php', '.rs', '.kt', '.sql', '.proto', '.md', '.rst'}
DENIED_DIRS = {'.git', '.agents', '.claude', '.codex', '.github', '.gitlab', 'node_modules', 'vendor',
               '.venv', 'venv', 'dist', 'build', '__pycache__', 'generated', 'migrations', 'frontend', 'front-end'}
ALIASES = {
    'aspect_sentiment_analysis': ('aspect_sentiment', 'aspect sentiment', 'sentiment', 'aspect', 'احساس', 'جنبه'),
    'abstraction_analysis': ('abstraction', 'summarization', 'summarisation', 'summarize', 'summary', 'خلاصه', 'انتزاع'),
}


def allowed_path(path, directory=False):
    p = PurePosixPath(path)
    if not path or p.is_absolute() or '..' in p.parts or '\\' in path:
        return False
    if any(part.lower() in DENIED_DIRS or part.startswith('.') for part in p.parts):
        return False
    name = p.name.lower()
    if any(word in name for word in ('secret', 'credential', 'private', '.env', 'id_rsa', 'id_ed25519', 'token', 'password', 'lock')):
        return False
    return directory or (p.suffix.lower() in SOURCE_SUFFIXES and name not in {'agents.md', 'claude.md', 'skill.md'} and not name.endswith(('.min.js', '.d.ts')))


class GitLabSource:
    MAX_REQUESTS = 80
    MAX_SECONDS = 90
    MAX_TREE_PAGES = 10
    MAX_FILES = 60
    MAX_FILE_BYTES = 128_000
    MAX_TOTAL_BYTES = 2_000_000

    def __init__(self, base_url, project_path, ref=None, *, opener=None):
        parsed = urlsplit(base_url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RetrievalError('GITLAB_BASE_URL باید یک نشانی HTTPS بدون اطلاعات ورود باشد.')
        if not project_path or project_path.startswith('/') or '..' in project_path.split('/'):
            raise RetrievalError('GITLAB_PROJECT_PATH نامعتبر است.')
        self.base_url = base_url.rstrip('/')
        self.project_path = project_path.strip('/')
        self._token = os.environ.get('GITLAB_READ_TOKEN', '')
        if not self._token:
            raise RetrievalError('GITLAB_READ_TOKEN تنظیم نشده است؛ بررسی زنده انجام نشد.')
        self.opener = opener or build_opener(NoRedirect())
        self.deadline = time.monotonic() + self.MAX_SECONDS
        self.requests = 0
        self.bytes_read = 0
        self.cache = {}
        self.limits = []
        self.project_url = self.base_url + '/api/v4/projects/' + quote(self.project_path, safe='')
        project = self._json(self.project_url)
        if not isinstance(project, dict):
            raise RetrievalError('پاسخ اطلاعات پروژه GitLab معتبر نیست.')
        if project.get('path_with_namespace') != self.project_path:
            raise RetrievalError('پروژه پاسخ‌داده‌شده با پروژه پیکربندی‌شده مطابقت ندارد.')
        self.ref = ref or project.get('default_branch')
        if not isinstance(self.ref, str) or not self.ref:
            raise RetrievalError('شاخه پیش‌فرض پروژه پیدا نشد؛ BACKEND_REF را مشخص کنید.')
        commit = self._json(self.project_url + '/repository/commits/' + quote(self.ref, safe=''))
        if not isinstance(commit, dict):
            raise RetrievalError('پاسخ commit در GitLab معتبر نیست.')
        self.sha = commit.get('id', '')
        if not isinstance(self.sha, str) or not re.fullmatch(r'[a-fA-F0-9]{40,64}', self.sha):
            raise RetrievalError('GitLab شناسه commit معتبر برنگرداند.')
        self.tree = None

    def _get(self, url, limit):
        self.requests += 1
        remaining = self.deadline - time.monotonic()
        if self.requests > self.MAX_REQUESTS or remaining <= 0:
            raise RetrievalError('مهلت یا تعداد مجاز درخواست‌های GitLab تمام شد.')
        if not (url == self.project_url or url.startswith(self.project_url + '/')):
            raise RetrievalError('دسترسی خارج از پروژه مجاز نیست.')
        request = Request(url, headers={'PRIVATE-TOKEN': self._token, 'Accept': 'application/json'}, method='GET')
        try:
            with self.opener.open(request, timeout=min(20, remaining)) as response:
                data = response.read(limit + 1)
        except HTTPError as exc:
            raise RetrievalError(f'خواندن GitLab ناموفق بود (HTTP {exc.code})؛ دسترسی پروژه و توکن را بررسی کنید.') from None
        except (URLError, TimeoutError, OSError):
            raise RetrievalError('ارتباط خواندن GitLab ناموفق بود؛ بررسی زنده انجام نشد.') from None
        if len(data) > limit:
            raise RetrievalError('پاسخ GitLab از حد مجاز بزرگ‌تر است.')
        return data

    def _json(self, url):
        try:
            return json.loads(self._get(url, 1_000_000))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RetrievalError('پاسخ GitLab JSON معتبر نیست.') from None

    def list_directory(self, path='', recursive=False):
        if path and not allowed_path(path, directory=True):
            raise RetrievalError('این مسیر برای بررسی مجاز نیست.')
        entries = []
        for page in range(1, self.MAX_TREE_PAGES + 1):
            query = urlencode(dict(ref=self.sha, path=path, recursive=str(recursive).lower(), per_page=100, page=page))
            batch = self._json(self.project_url + '/repository/tree?' + query)
            if not isinstance(batch, list):
                raise RetrievalError('فهرست مسیرهای GitLab معتبر نیست.')
            entries.extend(item for item in batch if isinstance(item, dict) and
                           allowed_path(item.get('path', ''), directory=item.get('type') == 'tree') and
                           item.get('mode') != '120000')
            if len(batch) < 100:
                break
        else:
            self.limits.append('فهرست مسیرها به ۱۰۰۰ ورودی محدود شد؛ ممکن است همه مسیرها دیده نشده باشند.')
        return entries

    def find_paths(self, terms):
        if self.tree is None:
            self.tree = self.list_directory(recursive=True)
        return [item['path'] for item in self.tree if item.get('type') == 'blob' and
                any(term.casefold() in item['path'].casefold() for term in terms)]

    def read_file(self, path):
        if not allowed_path(path):
            raise RetrievalError('این فایل برای بررسی مجاز نیست.')
        if path in self.cache:
            return self.cache[path]
        if len(self.cache) >= self.MAX_FILES:
            raise RetrievalError('حد تعداد فایل‌های بررسی پر شده است.')
        raw = self._get(self.project_url + '/repository/files/' + quote(path, safe='') + '/raw?' + urlencode({'ref': self.sha}), self.MAX_FILE_BYTES)
        if self.bytes_read + len(raw) > self.MAX_TOTAL_BYTES:
            raise RetrievalError('حد حجم دریافت منبع پر شده است.')
        self.bytes_read += len(raw)
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise RetrievalError('فایل منبع متنی UTF-8 نیست.') from None
        # Exclude credential-bearing content, not just known credential filenames.
        if ('PRIVATE KEY-----' in text or self._token in text or
            re.search(r'(?i)(?:password|secret|api_key|access_token)\s*[=:]\s*[\"\'][^\"\'\n]{8,}[\"\']', text)):
            raise RetrievalError('فایل دارای محتوای احتمالی محرمانه از بررسی کنار گذاشته شد.')
        self.cache[path] = text
        return text

    def snapshot(self, destination, feature):
        terms = ALIASES[feature]
        direct = self.find_paths(terms)
        docs = self.find_paths(('readme', 'architecture', 'overview'))[:8]
        candidates = list(dict.fromkeys(docs + direct))
        # Documentation can name modules whose filenames don't match the feature key.
        verified = []
        for path in docs:
            try:
                text = self.read_file(path)
            except RetrievalError:
                continue
            for candidate in self.find_paths(('',)):
                if candidate in text and candidate not in candidates:
                    candidates.append(candidate)
        fallback = self.find_paths(('route', 'service', 'api', 'model', 'analy', 'pipeline', 'task', 'view'))
        candidates = list(dict.fromkeys(candidates + fallback))[:self.MAX_FILES]
        for path in candidates:
            try:
                text = self.read_file(path)
            except RetrievalError:
                self.limits.append(f'فایل {path} قابل دریافت نبود یا به علت محدودیت کنار گذاشته شد.')
                continue
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8')
            for number, line in enumerate(text.splitlines(), 1):
                if any(term.casefold() in line.casefold() for term in terms):
                    verified.append(dict(path=path, line=number, quote=line[:500], commit_sha=self.sha,
                                         relationship='feature term observed in source; root cause not established'))
                    break
        if not any(p.is_file() for p in destination.rglob('*')):
            raise RetrievalError('هیچ منبع مجاز مرتبطی دریافت نشد؛ یافته ساختگی تولید نمی‌شود.')
        return dict(project=self.project_path, ref=self.ref, commit_sha=self.sha,
                    retrieved_paths=sorted(str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()),
                    verified_paths=verified, limitations=self.limits + [
                        'دریافت منبع محدود است و جای جست‌وجوی کامل مخزن یا اجرای کد را نمی‌گیرد.'])
