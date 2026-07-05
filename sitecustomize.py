"""Enables coverage.py measurement inside subprocesses spawned during tests.

Python auto-imports sitecustomize at interpreter startup if it's importable
on sys.path. When a test spawns `python -m spps_assistant.api` as a real
subprocess (see tests/api/test_sidecar_entrypoint.py), this lets coverage.py
see code executed inside that child process, which it cannot do by default.

Only activates when COVERAGE_PROCESS_START is set by the test itself, so it
has no effect on normal `spps-assistant` CLI usage or the frozen sidecar
executable in production.
"""

import os

if os.environ.get('COVERAGE_PROCESS_START'):
    import coverage
    coverage.process_startup()
