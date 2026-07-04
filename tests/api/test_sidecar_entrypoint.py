"""Integration test for the standalone sidecar entrypoint.

This spawns the module as a real subprocess (the same way Electron's main
process will eventually spawn the frozen sidecar executable), reads the
port-announcement line from stdout, and makes a real HTTP request to
confirm the server is actually listening and serving the Flask app.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request


def test_sidecar_prints_ready_line_and_serves_health():
    env = {**os.environ, 'SPPS_API_PORT': '0'}
    proc = subprocess.Popen(
        [sys.executable, '-m', 'spps_assistant.api'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    try:
        ready_line = proc.stdout.readline()
        match = re.match(r'SPPS_SIDECAR_READY (\d+)', ready_line)
        assert match, f"unexpected first stdout line: {ready_line!r}"
        port = int(match.group(1))
        assert port > 0

        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=5) as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode())
            assert body['ok'] is True
            assert body['data']['status'] == 'ok'
    finally:
        proc.terminate()
        proc.wait(timeout=5)
