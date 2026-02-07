"""WebSocket support for HTTPie.

This module provides functionality to connect to WebSocket servers
using ws:// and wss:// URL schemes.
"""

import re
import sys
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from httpie.context import Environment

from httpie.status import ExitStatus


# WebSocket URL scheme pattern
WEBSOCKET_SCHEME_RE = re.compile(r'^wss?://', re.IGNORECASE)


def is_websocket_url(url: str) -> bool:
    """Check if the given URL uses WebSocket scheme (ws:// or wss://)."""
    return bool(WEBSOCKET_SCHEME_RE.match(url))


class WebSocketSession:
    """Manages a WebSocket connection session."""

    def __init__(
        self,
        url: str,
        headers: Optional[dict] = None,
        timeout: Optional[float] = None,
        verify_ssl: bool = True,
    ):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._ws = None
        self._connected = False

    def connect(self) -> dict:
        """
        Establish WebSocket connection.
        
        Returns the handshake response headers.
        """
        try:
            import websocket
        except ImportError:
            raise ImportError(
                "WebSocket support requires the 'websocket-client' package. "
                "Install it with: pip install websocket-client"
            )

        # Convert headers dict to list of tuples for websocket-client
        header_list = [f"{k}: {v}" for k, v in self.headers.items()]

        # Create WebSocket connection
        self._ws = websocket.create_connection(
            self.url,
            header=header_list,
            timeout=self.timeout,
            sslopt={"cert_reqs": 0} if not self.verify_ssl else None,
        )
        self._connected = True

        # Return handshake headers
        return dict(self._ws.getheaders()) if self._ws.getheaders() else {}

    def send(self, message: str) -> None:
        """Send a message to the WebSocket server."""
        if not self._connected or not self._ws:
            raise RuntimeError("WebSocket is not connected")
        self._ws.send(message)

    def receive(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Receive a message from the WebSocket server.
        
        Returns None if connection is closed.
        """
        if not self._connected or not self._ws:
            raise RuntimeError("WebSocket is not connected")

        try:
            if timeout is not None:
                self._ws.settimeout(timeout)
            return self._ws.recv()
        except Exception:
            return None

    def close(self, code: int = 1000, reason: str = "") -> tuple:
        """
        Close the WebSocket connection.
        
        Returns (close_code, close_reason).
        """
        if self._ws:
            try:
                self._ws.close(status=code, reason=reason.encode() if reason else b"")
            except Exception:
                pass
            close_code = getattr(self._ws, 'close_status', code)
            close_reason = getattr(self._ws, 'close_reason', reason)
            self._connected = False
            return (close_code, close_reason)
        return (code, reason)

    @property
    def connected(self) -> bool:
        """Check if the WebSocket is connected."""
        return self._connected


def run_websocket_session(
    url: str,
    env: 'Environment',
    headers: Optional[dict] = None,
    auth: Optional[tuple] = None,
    timeout: Optional[float] = None,
    verify_ssl: bool = True,
) -> ExitStatus:
    """
    Run an interactive WebSocket session.

    Args:
        url: WebSocket URL (ws:// or wss://)
        env: HTTPie Environment instance
        headers: Optional custom headers
        auth: Optional (username, password) tuple for basic auth
        timeout: Connection timeout in seconds
        verify_ssl: Whether to verify SSL certificates

    Returns:
        ExitStatus indicating success or failure.
    """
    import base64

    headers = dict(headers) if headers else {}

    # Add basic auth header if provided
    if auth:
        username, password = auth
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers['Authorization'] = f'Basic {credentials}'

    session = WebSocketSession(
        url=url,
        headers=headers,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )

    try:
        # Connect to WebSocket server
        env.stdout.write(f"> Connecting to {url}...\n")
        handshake_headers = session.connect()

        # Display handshake response
        env.stdout.write(f"> Connected to {url}\n")
        if handshake_headers:
            env.stdout.write("> Handshake response headers:\n")
            for key, value in handshake_headers.items():
                env.stdout.write(f">   {key}: {value}\n")

        env.stdout.write(">\n")
        env.stdout.write("> Type a message and press Enter to send.\n")
        env.stdout.write("> Use \\\\ at end of line for multi-line input.\n")
        env.stdout.write("> Press Ctrl+C to disconnect.\n")
        env.stdout.write(">\n")

        # Interactive message loop
        while session.connected:
            try:
                # Read input from user
                env.stdout.write("< ")
                env.stdout.flush()

                # Handle multi-line input (lines ending with \)
                message_lines = []
                while True:
                    line = env.stdin.readline()
                    if not line:
                        # EOF
                        raise KeyboardInterrupt

                    line = line.rstrip('\n\r')
                    if line.endswith('\\'):
                        message_lines.append(line[:-1])
                    else:
                        message_lines.append(line)
                        break

                message = '\n'.join(message_lines)

                if message:
                    # Send message
                    session.send(message)

                    # Try to receive response (with short timeout for echo servers)
                    response = session.receive(timeout=5.0)
                    if response:
                        env.stdout.write(f"> {response}\n")

            except KeyboardInterrupt:
                env.stdout.write("\n> Disconnecting...\n")
                break

    except ImportError as e:
        env.log_error(str(e))
        return ExitStatus.ERROR
    except Exception as e:
        env.log_error(f"WebSocket error: {e}")
        return ExitStatus.ERROR
    finally:
        # Close connection
        close_code, close_reason = session.close()
        env.stdout.write(f"> Connection closed (code: {close_code})\n")
        if close_reason:
            env.stdout.write(f"> Close reason: {close_reason}\n")

    return ExitStatus.SUCCESS


def extract_websocket_args(args: List[str]) -> tuple:
    """
    Extract WebSocket-relevant arguments from command line args.
    
    Returns (url, headers_dict, auth_tuple, timeout, verify_ssl).
    """
    url = None
    headers = {}
    auth = None
    timeout = None
    verify_ssl = True

    i = 0
    while i < len(args):
        arg = args[i]

        # URL (first positional that looks like ws:// or wss://)
        if url is None and is_websocket_url(arg):
            url = arg
        # Header (Key:Value)
        elif ':' in arg and not arg.startswith('-') and '=' not in arg.split(':')[0]:
            key, value = arg.split(':', 1)
            if key and not key.startswith('-'):
                headers[key] = value
        # Auth
        elif arg in ('--auth', '-a') and i + 1 < len(args):
            auth_str = args[i + 1]
            if ':' in auth_str:
                auth = tuple(auth_str.split(':', 1))
            i += 1
        # Timeout
        elif arg == '--timeout' and i + 1 < len(args):
            try:
                timeout = float(args[i + 1])
            except ValueError:
                pass
            i += 1
        # Verify SSL
        elif arg == '--verify':
            if i + 1 < len(args) and args[i + 1].lower() in ('no', 'false', '0'):
                verify_ssl = False
                i += 1

        i += 1

    return url, headers, auth, timeout, verify_ssl
