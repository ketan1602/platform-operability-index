"""Subprocess entry point for the GoogleADKAdapter (runs in this adapter's own venv)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from harness.adapters.shared.entry import main  # noqa: E402
from harness.adapters.google_adk.adapter import GoogleADKAdapter  # noqa: E402

if __name__ == "__main__":
    main(GoogleADKAdapter)
