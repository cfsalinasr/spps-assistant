"""Standalone entrypoint for the SPPS Assistant API sidecar process.

Run with: python -m spps_assistant.api
Reads SPPS_API_PORT from the environment (0 or unset means "pick any free
port"). Generates a random shared-secret token and prints
"SPPS_SIDECAR_READY <port> <token>" to stdout once bound and listening, so
a parent process (e.g. Electron's main process) can discover both the port
and the token it must send back on the X-SPPS-Sidecar-Token header of every
request — required because this sidecar has no other request
authentication, and binding to localhost alone does not stop another local
process, or a malicious webpage's browser-side fetch(), from reaching it.

Uses werkzeug's make_server (Flask's underlying dev server) rather than a
production WSGI server (gunicorn/waitress/etc.) — an intentional choice,
not an oversight: this process is never exposed beyond 127.0.0.1 and has
exactly one real client (a future Electron main process spawning it as a
local subprocess), so the dev server's request handling is sufficient and
avoids an extra runtime dependency. threaded=True is set so a slower
request (e.g. a future long-running /synthesis call) can't block /health
polling from the same client.

Serves forever until the process is terminated.
"""

import os
import secrets
import sys

from werkzeug.serving import make_server

from spps_assistant.api.app import create_app


def main() -> None:
    """Bind the Flask app to a real socket, announce port+token, and serve."""
    raw_port = os.environ.get('SPPS_API_PORT', '0')
    try:
        port = int(raw_port)
    except ValueError:
        print(f"Invalid SPPS_API_PORT value: {raw_port!r} (must be an integer)", file=sys.stderr)
        sys.exit(1)

    token = secrets.token_urlsafe(32)
    app = create_app(auth_token=token)
    server = make_server('127.0.0.1', port, app, threaded=True)
    print(f"SPPS_SIDECAR_READY {server.server_port} {token}", flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
