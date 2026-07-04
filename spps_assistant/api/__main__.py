"""Standalone entrypoint for the SPPS Assistant API sidecar process.

Run with: python -m spps_assistant.api
Reads SPPS_API_PORT from the environment (0 or unset means "pick any free
port"). Prints "SPPS_SIDECAR_READY <port>" to stdout once bound and
listening, so a parent process (e.g. Electron's main process) can discover
the port without needing to pre-agree on a fixed value, then serves
forever until the process is terminated.
"""

import os

from werkzeug.serving import make_server

from spps_assistant.api.app import create_app


def main() -> None:
    """Bind the Flask app to a real socket, announce the port, and serve."""
    port = int(os.environ.get('SPPS_API_PORT', '0'))
    app = create_app()
    server = make_server('127.0.0.1', port, app)
    print(f"SPPS_SIDECAR_READY {server.server_port}", flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
