"""Entry point: ``python -m crisp`` launches the GUI."""
from __future__ import annotations

import sys


def main() -> int:
    # Import lazily so `python -m crisp --help`-style probes don't require Qt.
    from crisp.gui.app import run
    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
