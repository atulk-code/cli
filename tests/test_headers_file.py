"""Tests for --headers-file feature."""
import os
import tempfile
import pytest
from httpie.status import ExitStatus


class TestHeadersFile:
    """Test cases for --headers-file argument."""

    def test_headers_file_basic(self, httpbin):
        """Test reading headers from a file."""
        from tests.utils import http
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("X-Custom-Header: custom-value\n")
            f.write("X-Another-Header: another-value\n")
            headers_file = f.name
        
        try:
            r = http('--headers-file', headers_file, httpbin.url + '/headers')
            assert 'X-Custom-Header' in r
            assert 'custom-value' in r
            assert 'X-Another-Header' in r
            assert 'another-value' in r
        finally:
            os.unlink(headers_file)

    def test_headers_file_with_comments(self, httpbin):
        """Test that comment lines (starting with #) are ignored."""
        from tests.utils import http
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("# This is a comment\n")
            f.write("X-Valid-Header: valid-value\n")
            f.write("# Another comment\n")
            headers_file = f.name
        
        try:
            r = http('--headers-file', headers_file, httpbin.url + '/headers')
            assert 'X-Valid-Header' in r
            assert 'valid-value' in r
            # Comments should not appear as headers
            assert 'This is a comment' not in r
        finally:
            os.unlink(headers_file)

    def test_headers_file_with_empty_lines(self, httpbin):
        """Test that empty lines are ignored."""
        from tests.utils import http
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("X-First-Header: first-value\n")
            f.write("\n")
            f.write("   \n")  # whitespace only
            f.write("X-Second-Header: second-value\n")
            headers_file = f.name
        
        try:
            r = http('--headers-file', headers_file, httpbin.url + '/headers')
            assert 'X-First-Header' in r
            assert 'X-Second-Header' in r
        finally:
            os.unlink(headers_file)

    def test_headers_file_cli_headers_take_precedence(self, httpbin):
        """Test that CLI headers override headers from file."""
        from tests.utils import http
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("X-Override: file-value\n")
            headers_file = f.name
        
        try:
            r = http('--headers-file', headers_file, 
                     httpbin.url + '/headers', 'X-Override:cli-value')
            assert 'cli-value' in r
            assert 'file-value' not in r
        finally:
            os.unlink(headers_file)

    def test_headers_file_nonexistent_file(self):
        """Test error when headers file doesn't exist."""
        from tests.utils import http, MockEnvironment
        
        env = MockEnvironment()
        r = http('--headers-file', '/nonexistent/path/headers.txt',
                 'https://example.com', env=env, tolerate_error_exit_status=True)
        assert r.exit_status == ExitStatus.ERROR
        assert 'Cannot read headers file' in r.stderr

    def test_headers_file_invalid_format(self):
        """Test error when header format is invalid (no colon)."""
        from tests.utils import http, MockEnvironment
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Invalid header without colon\n")
            headers_file = f.name
        
        try:
            env = MockEnvironment()
            r = http('--headers-file', headers_file, 'https://example.com', 
                     env=env, tolerate_error_exit_status=True)
            assert r.exit_status == ExitStatus.ERROR
            assert 'Invalid' in r.stderr and 'header format' in r.stderr
        finally:
            os.unlink(headers_file)

    def test_headers_file_header_with_colon_in_value(self, httpbin):
        """Test headers with colons in the value (e.g., Authorization: Bearer token)."""
        from tests.utils import http
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Authorization: Bearer token:with:colons\n")
            f.write("X-URL: https://example.com:8080/path\n")
            headers_file = f.name
        
        try:
            r = http('--headers-file', headers_file, httpbin.url + '/headers')
            assert 'Authorization' in r
            assert 'Bearer token:with:colons' in r
            assert 'https://example.com:8080/path' in r
        finally:
            os.unlink(headers_file)

    def test_headers_file_multiple_headers_same_name(self, httpbin):
        """Test multiple headers with the same name (last one wins in file)."""
        from tests.utils import http
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("X-Duplicate: first-value\n")
            f.write("X-Duplicate: second-value\n")
            headers_file = f.name
        
        try:
            r = http('--headers-file', headers_file, httpbin.url + '/headers')
            # The second value should be used (or both depending on implementation)
            assert 'X-Duplicate' in r
        finally:
            os.unlink(headers_file)
