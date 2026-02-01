"""Sequential request execution for HTTPie.

This module provides functionality to execute multiple HTTP requests
sequentially from stdin input.
"""

import shlex
from typing import List

from httpie.context import Environment
from httpie.status import ExitStatus


def parse_sequence_from_stdin(stdin_content: str) -> List[List[str]]:
    """
    Parse stdin content into a list of request arguments.

    Each request is separated by one or more blank lines.
    Lines within a request are joined to form HTTPie arguments.

    Returns a list where each item is a list of arguments for one request.
    """
    requests = []
    current_request_lines = []

    for line in stdin_content.split('\n'):
        stripped_line = line.strip()
        if not stripped_line:
            if current_request_lines:
                # Join all lines and parse as shell arguments
                full_line = ' '.join(current_request_lines)
                try:
                    request_args = shlex.split(full_line)
                except ValueError:
                    # Fallback to simple split if shlex fails
                    request_args = full_line.split()
                if request_args:
                    requests.append(request_args)
                current_request_lines = []
        else:
            current_request_lines.append(stripped_line)

    # Don't forget the last request if file doesn't end with blank line
    if current_request_lines:
        full_line = ' '.join(current_request_lines)
        try:
            request_args = shlex.split(full_line)
        except ValueError:
            request_args = full_line.split()
        if request_args:
            requests.append(request_args)

    return requests


def run_sequence(
    request_args_list: List[List[str]],
    env: Environment,
    base_args: List[str] = None,
) -> ExitStatus:
    """
    Execute multiple requests sequentially.

    Args:
        request_args_list: List of argument lists, one per request
        env: Environment instance
        base_args: Base arguments to apply to each request (e.g., --verbose)

    Returns:
        ExitStatus.SUCCESS if all requests succeed, otherwise the first error status.
    """
    from httpie.core import main

    if base_args is None:
        base_args = []

    final_status = ExitStatus.SUCCESS

    for i, request_args in enumerate(request_args_list):
        if i > 0:
            # Print separator between requests
            separator = '\n' + '=' * 60 + '\n\n'
            try:
                env.stdout.write(separator)
            except TypeError:
                # Handle binary mode stdout
                env.stdout.buffer.write(separator.encode())

        # Combine base args with request-specific args
        full_args = ['http'] + base_args + request_args

        # Create a fresh stdin for each request (non-piped)
        # to avoid interfering with stdin being consumed
        from io import BytesIO
        original_stdin = env.stdin
        original_stdin_isatty = env.stdin_isatty
        env.stdin = BytesIO(b'')
        env.stdin_isatty = True

        try:
            status = main(args=full_args, env=env)
        finally:
            env.stdin = original_stdin
            env.stdin_isatty = original_stdin_isatty

        if status != ExitStatus.SUCCESS:
            final_status = status
            # Continue executing remaining requests even on error

    return final_status
