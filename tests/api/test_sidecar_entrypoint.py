"""Integration test for the standalone sidecar entrypoint.

This spawns the module as a real subprocess (the same way Electron's main
process will eventually spawn the frozen sidecar executable), reads the
port-announcement line from stdout, and makes a real HTTP request to
confirm the server is actually listening and serving the Flask app.
"""

import json
import os
import queue
import re
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_line_with_timeout(stream, timeout_seconds):
    """Read one line from stream, returning None if no line arrives in time.

    Runs the blocking readline() in a daemon thread so a hung subprocess
    can never hang the test itself — the test fails fast with a clear
    message instead.
    """
    line_queue: queue.Queue = queue.Queue(maxsize=1)

    def _reader():
        line_queue.put(stream.readline())

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()
    try:
        return line_queue.get(timeout=timeout_seconds)
    except queue.Empty:
        return None


def test_sidecar_prints_ready_line_and_serves_health():
    # PYTHONPATH (not just cwd) is required for sitecustomize.py at the repo
    # root to be auto-imported by Python's site initialization: for `python -m`,
    # the current directory is only added to sys.path *after* site.py has
    # already attempted (and, without this, silently failed) its own
    # sitecustomize import. Putting the repo root on PYTHONPATH makes it part
    # of sys.path early enough for that auto-import to actually find it.
    existing_pythonpath = os.environ.get('PYTHONPATH', '')
    pythonpath = (
        f"{_REPO_ROOT}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(_REPO_ROOT)
    )
    env = {
        **os.environ,
        'SPPS_API_PORT': '0',
        'COVERAGE_PROCESS_START': str(_REPO_ROOT / 'pyproject.toml'),
        'PYTHONPATH': pythonpath,
    }
    proc = subprocess.Popen(
        [sys.executable, '-m', 'spps_assistant.api'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    try:
        ready_line = _read_line_with_timeout(proc.stdout, timeout_seconds=10)
        assert ready_line is not None, (
            "sidecar did not print a ready line within 10s; it may have hung on startup"
        )
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
