"""Tests for --encoded flag to preserve Content-Encoding."""
import gzip
import subprocess
import sys
import tempfile
import os


class TestEncodedFlag:
    """Test cases for --encoded argument."""

    def test_encoded_flag_exists(self):
        """Test that --encoded flag is recognized."""
        from tests.utils import MockEnvironment, http
        
        env = MockEnvironment()
        # Just verify the flag doesn't cause an error - use a simple request
        r = http('--encoded', '--print=h', 'https://httpbin.org/get',
                 env=env, tolerate_error_exit_status=True)
        # Should not get "unrecognized arguments" error
        assert 'unrecognized arguments' not in r.stderr

    def test_encoded_gzip_response_to_file(self, httpbin):
        """Test that --encoded preserves gzip-compressed response body when saving to file."""
        # Use subprocess to test real binary output behavior
        with tempfile.NamedTemporaryFile(delete=False, suffix='.gz') as f:
            output_file = f.name
        
        try:
            # Run httpie with --encoded, saving output to file
            result = subprocess.run(
                [sys.executable, '-m', 'httpie', '--encoded', '--body', 
                 '--output', output_file, httpbin.url + '/gzip'],
                capture_output=True,
                timeout=30
            )
            
            # Read the saved file
            with open(output_file, 'rb') as f:
                content = f.read()
            
            # Check for gzip magic bytes
            assert content[:2] == b'\x1f\x8b', f"Expected gzip magic bytes, got: {content[:10]}"
            
            # Verify it's valid gzip by decompressing
            decompressed = gzip.decompress(content)
            assert b'gzipped' in decompressed or b'origin' in decompressed
            
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    def test_encoded_with_non_compressed_response(self, httpbin):
        """Test --encoded doesn't break non-compressed responses."""
        # Use subprocess for reliability
        result = subprocess.run(
            [sys.executable, '-m', 'httpie', '--encoded', '--body', httpbin.url + '/get'],
            capture_output=True,
            timeout=30,
            text=True
        )
        
        # Should still work and return JSON
        assert 'origin' in result.stdout or 'headers' in result.stdout
