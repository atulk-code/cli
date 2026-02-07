"""Tests for --sequence feature (sequential request execution)."""
import pytest
from tests.utils import http, MockEnvironment, StdinBytesIO, HTTP_OK
from httpie.status import ExitStatus


class TestSequenceParsing:
    """Test cases for parsing sequence input."""

    def test_parse_single_request(self):
        """Test parsing a single request from stdin."""
        from httpie.sequence import parse_sequence_from_stdin

        content = "GET https://example.com/api\n"
        requests = parse_sequence_from_stdin(content)

        assert len(requests) == 1
        assert requests[0] == ['GET', 'https://example.com/api']

    def test_parse_multiple_requests_blank_line_separated(self):
        """Test parsing multiple requests separated by blank lines."""
        from httpie.sequence import parse_sequence_from_stdin

        content = """GET https://example.com/get

POST https://example.com/post name=value

GET https://example.com/headers
"""
        requests = parse_sequence_from_stdin(content)

        assert len(requests) == 3
        assert requests[0] == ['GET', 'https://example.com/get']
        assert requests[1] == ['POST', 'https://example.com/post', 'name=value']
        assert requests[2] == ['GET', 'https://example.com/headers']

    def test_parse_empty_input(self):
        """Test parsing empty input returns empty list."""
        from httpie.sequence import parse_sequence_from_stdin

        requests = parse_sequence_from_stdin("")
        assert requests == []

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only input returns empty list."""
        from httpie.sequence import parse_sequence_from_stdin

        requests = parse_sequence_from_stdin("   \n\n   \n")
        assert requests == []

    def test_parse_request_with_quoted_values(self):
        """Test parsing requests with quoted values."""
        from httpie.sequence import parse_sequence_from_stdin

        content = 'POST https://example.com/post "name=hello world"\n'
        requests = parse_sequence_from_stdin(content)

        assert len(requests) == 1
        assert requests[0] == ['POST', 'https://example.com/post', 'name=hello world']


class TestSequenceExecution:
    """Test cases for sequential request execution."""

    def test_sequence_requires_stdin(self):
        """Test --sequence without stdin pipe shows error."""
        env = MockEnvironment(stdin_isatty=True)
        r = http('--sequence', env=env, tolerate_error_exit_status=True)
        assert r.exit_status == ExitStatus.ERROR
        assert 'requires input from stdin' in r.stderr

    def test_sequence_empty_stdin_error(self):
        """Test --sequence with empty stdin shows error."""
        stdin = StdinBytesIO(b'')
        env = MockEnvironment(stdin=stdin, stdin_isatty=False)
        r = http('--sequence', env=env, tolerate_error_exit_status=True)
        assert r.exit_status == ExitStatus.ERROR
        assert 'No requests found' in r.stderr

    def test_sequence_single_request(self, httpbin):
        """Test --sequence with a single GET request."""
        stdin = StdinBytesIO(f'GET {httpbin.url}/get\n'.encode())
        env = MockEnvironment(stdin=stdin, stdin_isatty=False)
        r = http('--sequence', env=env)
        assert HTTP_OK in r

    def test_sequence_multiple_requests(self, httpbin):
        """Test --sequence with multiple requests separated by blank lines."""
        requests_content = f'''GET {httpbin.url}/get

POST {httpbin.url}/post name=test

GET {httpbin.url}/headers
'''
        stdin = StdinBytesIO(requests_content.encode())
        env = MockEnvironment(stdin=stdin, stdin_isatty=False)
        r = http('--sequence', env=env)
        # Should have multiple HTTP responses
        assert r.count('HTTP/') >= 3

    def test_sequence_with_headers(self, httpbin):
        """Test --sequence with requests that include headers."""
        requests_content = f'''GET {httpbin.url}/get X-Custom:value1

GET {httpbin.url}/get X-Custom:value2
'''
        stdin = StdinBytesIO(requests_content.encode())
        env = MockEnvironment(stdin=stdin, stdin_isatty=False)
        r = http('--sequence', env=env)
        assert HTTP_OK in r
