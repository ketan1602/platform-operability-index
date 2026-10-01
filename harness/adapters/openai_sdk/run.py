"""Subprocess entry point for the OpenAISDKAdapter (runs in this adapter's own venv)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from harness.adapters.shared.entry import main  # noqa: E402
from harness.adapters.openai_sdk.adapter import OpenAISDKAdapter  # noqa: E402

if __name__ == "__main__":
    main(OpenAISDKAdapter)
