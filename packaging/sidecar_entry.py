"""PyInstaller entry point for the frozen SPPS API sidecar.

Run with: python -m spps_assistant.api (in dev), or the frozen executable
this script produces (in a packaged build). Delegates to the real
entrypoint so both paths share identical behavior.
"""

from spps_assistant.api.__main__ import main

if __name__ == '__main__':
    main()
