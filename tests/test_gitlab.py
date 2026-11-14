import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit, unquote

from triage.gitlab import GitLabSource, RetrievalError, allowed_path

SHA = 'a' * 40


class FakeGitLab:
    def __init__(self): self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        path = unquote(urlsplit(request.full_url).path)
        query = parse_qs(urlsplit(request.full_url).query)
        if path.endswith('/group/backend'):
            result = {'path_with_namespace': 'group/backend', 'default_branch': 'release'}
        elif '/commits/' in path:
            result = {'id': SHA}
        elif path.endswith('/tree'):
            assert query['ref'] == [SHA]
            result = [{'path': 'services/sentiment.py', 'type': 'blob', 'mode': '100644'},
                      {'path': 'README.md', 'type': 'blob', 'mode': '100644'},
                      {'path': '.env', 'type': 'blob'}, {'path': 'private_key.py', 'type': 'blob'},
                      {'path': 'node_modules/sentiment.js', 'type': 'blob'},
                      {'path': 'shortcut.py', 'type': 'blob', 'mode': '120000'}]
        elif '/files/' in path:
            assert query['ref'] == [SHA]
            text = 'Sentiment service: services/sentiment.py' if 'README' in path else 'def sentiment(text):\n    return text\n'
            return io.BytesIO(text.encode())
        else:
            raise AssertionError(path)
        return io.BytesIO(json.dumps(result).encode())


class GitLabTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict('os.environ', {'GITLAB_READ_TOKEN': 'only-in-retrieval-token'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.api = FakeGitLab()

    def source(self, **kwargs):
        return GitLabSource('https://git.example.com', 'group/backend', opener=self.api, **kwargs)

    def test_discovers_default_branch_and_pins_every_read(self):
        source = self.source()
        self.assertEqual(source.ref, 'release')
        with tempfile.TemporaryDirectory() as directory:
            metadata = source.snapshot(Path(directory), 'aspect_sentiment_analysis')
            self.assertEqual(metadata['commit_sha'], SHA)
            self.assertTrue(metadata['verified_paths'])
            self.assertEqual(set(metadata['retrieved_paths']), {'README.md', 'services/sentiment.py'})
            self.assertNotIn('only-in-retrieval-token', json.dumps(metadata))
        self.assertIn('/commits/release', self.api.requests[1].full_url)
        self.assertTrue(all(request.get_method() == 'GET' for request in self.api.requests))

    def test_selected_ref_resolved_to_commit(self):
        self.source(ref='feature/summarize')
        self.assertIn('/commits/feature%2Fsummarize', self.api.requests[1].full_url)

    def test_exclusions_and_project_scope(self):
        source = self.source()
        for path in ('../other.py', '/etc/passwd', '.env', 'private.pem', 'node_modules/a.py', 'generated/a.py', 'tokens.py'):
            self.assertFalse(allowed_path(path))
            with self.assertRaises(RetrievalError): source.read_file(path)
        with self.assertRaises(RetrievalError): source._get('https://other.example', 100)

    def test_missing_credentials_and_http_error_never_leak_token(self):
        with patch.dict('os.environ', {'GITLAB_READ_TOKEN': ''}):
            with self.assertRaises(RetrievalError): self.source()
        self.api.open = lambda *a, **k: (_ for _ in ()).throw(HTTPError('https://host/only-in-retrieval-token', 403, 'token', {}, None))
        with self.assertRaises(RetrievalError) as result: self.source()
        self.assertNotIn('only-in-retrieval-token', str(result.exception))
        self.assertIn('403', str(result.exception))

    def test_credential_content_and_file_limits(self):
        source = self.source()
        self.api.open = lambda *a, **k: io.BytesIO(b'only-in-retrieval-token')
        with self.assertRaises(RetrievalError): source.read_file('service.py')
        self.api.open = lambda *a, **k: io.BytesIO(b'x' * (source.MAX_FILE_BYTES + 1))
        with self.assertRaises(RetrievalError): source.read_file('service.py')

    def test_tree_pagination_is_bounded(self):
        source = self.source()
        self.api.open = lambda *a, **k: io.BytesIO(json.dumps([{'path': f'a{i}.py', 'type': 'blob'} for i in range(100)]).encode())
        self.assertEqual(len(source.list_directory()), 1000)
        self.assertTrue(source.limits)

    def test_request_budget_and_redirect_protection(self):
        from triage.gitlab import NoRedirect
        source = self.source()
        source.requests = source.MAX_REQUESTS
        with self.assertRaises(RetrievalError): source.read_file('service.py')
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.invalid'))

    def test_project_identity_mismatch_is_rejected(self):
        self.api.open = lambda *a, **k: io.BytesIO(json.dumps({'path_with_namespace': 'other/project', 'default_branch': 'main'}).encode())
        with self.assertRaises(RetrievalError): self.source()
