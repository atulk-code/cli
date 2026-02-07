"""Tests for WebSocket support."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from httpie.websocket import (
    is_websocket_url,
    WebSocketSession,
    extract_websocket_args,
)
from httpie.status import ExitStatus


class TestIsWebSocketUrl:
    """Test cases for is_websocket_url function."""

    def test_ws_scheme(self):
        """Test ws:// scheme detection."""
        assert is_websocket_url('ws://localhost:8000/ws') is True
        assert is_websocket_url('ws://example.com') is True

    def test_wss_scheme(self):
        """Test wss:// scheme detection."""
        assert is_websocket_url('wss://localhost:8000/ws') is True
        assert is_websocket_url('wss://example.com/path') is True

    def test_http_scheme_not_websocket(self):
        """Test http:// is not detected as WebSocket."""
        assert is_websocket_url('http://localhost:8000') is False
        assert is_websocket_url('https://example.com') is False

    def test_no_scheme(self):
        """Test URLs without scheme are not detected as WebSocket."""
        assert is_websocket_url('localhost:8000') is False
        assert is_websocket_url('example.com') is False

    def test_case_insensitive(self):
        """Test scheme detection is case insensitive."""
        assert is_websocket_url('WS://example.com') is True
        assert is_websocket_url('WSS://example.com') is True
        assert is_websocket_url('Ws://example.com') is True


class TestExtractWebSocketArgs:
    """Test cases for extract_websocket_args function."""

    def test_extract_url(self):
        """Test URL extraction from args."""
        args = ['ws://localhost:8000/ws']
        url, headers, auth, timeout, verify_ssl = extract_websocket_args(args)
        assert url == 'ws://localhost:8000/ws'

    def test_extract_headers(self):
        """Test header extraction from args."""
        args = ['ws://localhost:8000/ws', 'X-Custom:value', 'Authorization:Bearer token']
        url, headers, auth, timeout, verify_ssl = extract_websocket_args(args)
        assert headers == {'X-Custom': 'value', 'Authorization': 'Bearer token'}

    def test_extract_auth(self):
        """Test auth extraction from args."""
        args = ['ws://localhost:8000/ws', '--auth', 'user:pass']
        url, headers, auth, timeout, verify_ssl = extract_websocket_args(args)
        assert auth == ('user', 'pass')

    def test_extract_auth_short_form(self):
        """Test auth extraction with -a short form."""
        args = ['ws://localhost:8000/ws', '-a', 'user:pass']
        url, headers, auth, timeout, verify_ssl = extract_websocket_args(args)
        assert auth == ('user', 'pass')

    def test_extract_timeout(self):
        """Test timeout extraction from args."""
        args = ['ws://localhost:8000/ws', '--timeout', '30']
        url, headers, auth, timeout, verify_ssl = extract_websocket_args(args)
        assert timeout == 30.0

    def test_extract_verify_no(self):
        """Test SSL verification disable."""
        args = ['wss://localhost:8000/ws', '--verify', 'no']
        url, headers, auth, timeout, verify_ssl = extract_websocket_args(args)
        assert verify_ssl is False

    def test_default_verify_ssl(self):
        """Test SSL verification is enabled by default."""
        args = ['wss://localhost:8000/ws']
        url, headers, auth, timeout, verify_ssl = extract_websocket_args(args)
        assert verify_ssl is True


class TestWebSocketSession:
    """Test cases for WebSocketSession class."""

    def test_init(self):
        """Test WebSocketSession initialization."""
        session = WebSocketSession(
            url='ws://localhost:8000/ws',
            headers={'X-Custom': 'value'},
            timeout=30.0,
            verify_ssl=True,
        )
        assert session.url == 'ws://localhost:8000/ws'
        assert session.headers == {'X-Custom': 'value'}
        assert session.timeout == 30.0
        assert session.verify_ssl is True
        assert session.connected is False

    def test_connect(self):
        """Test WebSocket connection."""
        mock_ws = MagicMock()
        mock_ws.getheaders.return_value = [('server', 'test-server')]

        mock_websocket_module = MagicMock()
        mock_websocket_module.create_connection.return_value = mock_ws

        with patch.dict('sys.modules', {'websocket': mock_websocket_module}):
            session = WebSocketSession(url='ws://localhost:8000/ws')
            headers = session.connect()

            mock_websocket_module.create_connection.assert_called_once()
            assert session.connected is True
            assert headers == {'server': 'test-server'}

    def test_send(self):
        """Test sending message."""
        mock_ws = MagicMock()
        mock_ws.getheaders.return_value = []

        mock_websocket_module = MagicMock()
        mock_websocket_module.create_connection.return_value = mock_ws

        with patch.dict('sys.modules', {'websocket': mock_websocket_module}):
            session = WebSocketSession(url='ws://localhost:8000/ws')
            session.connect()
            session.send('Hello, World!')

            mock_ws.send.assert_called_once_with('Hello, World!')

    def test_receive(self):
        """Test receiving message."""
        mock_ws = MagicMock()
        mock_ws.getheaders.return_value = []
        mock_ws.recv.return_value = 'Response message'

        mock_websocket_module = MagicMock()
        mock_websocket_module.create_connection.return_value = mock_ws

        with patch.dict('sys.modules', {'websocket': mock_websocket_module}):
            session = WebSocketSession(url='ws://localhost:8000/ws')
            session.connect()
            message = session.receive()

            assert message == 'Response message'

    def test_close(self):
        """Test closing connection."""
        mock_ws = MagicMock()
        mock_ws.getheaders.return_value = []
        mock_ws.close_status = 1000
        mock_ws.close_reason = 'Normal closure'

        mock_websocket_module = MagicMock()
        mock_websocket_module.create_connection.return_value = mock_ws

        with patch.dict('sys.modules', {'websocket': mock_websocket_module}):
            session = WebSocketSession(url='ws://localhost:8000/ws')
            session.connect()
            close_code, close_reason = session.close()

            assert session.connected is False
            assert close_code == 1000
            assert close_reason == 'Normal closure'

    def test_send_without_connect_raises(self):
        """Test sending without connecting raises error."""
        session = WebSocketSession(url='ws://localhost:8000/ws')
        with pytest.raises(RuntimeError, match="not connected"):
            session.send('test')

    def test_receive_without_connect_raises(self):
        """Test receiving without connecting raises error."""
        session = WebSocketSession(url='ws://localhost:8000/ws')
        with pytest.raises(RuntimeError, match="not connected"):
            session.receive()
