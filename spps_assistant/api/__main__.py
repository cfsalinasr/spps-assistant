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
Serves forever until the process is terminated.
"""

import os
import secrets

from werkzeug.serving import make_server

from spps_assistant.api.app import create_app


def main() -> None:
    """Bind the Flask app to a real socket, announce port+token, and serve."""
    port = int(os.environ.get('SPPS_API_PORT', '0'))
    token = secrets.token_urlsafe(32)
    app = create_app(auth_token=token)
    server = make_server('127.0.0.1', port, app)
    print(f"SPPS_SIDECAR_READY {server.server_port} {token}", flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
