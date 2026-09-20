"""Subprocess runner — executes any framework adapter in its own isolated process."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from harness.shared.measurement import RunResult


class SubprocessRunner:
    """
    Runs a framework adapter's run.py in an isolated subprocess and reads YAML output.

    Each adapter lives in harness/adapters/<name>/ with its own requirements.txt
    and optional .venv. The runner finds the Python interpreter, calls run.py
    with standardised CLI args, and deserialises the YAML result.
    """

    def __init__(self, adapter_dir: Path, venv_python: Optional[Path] = None):
        self._adapter_dir = adapter_dir
        self._python = str(venv_python or Path(sys.executable))

    def run(
        self,
        pillar: str,
        scenario_id: str,
        impl_type: str,
        output_path: Path,
        run_id: Optional[str] = None,
        extra_env: Optional[dict] = None,
        timeout_s: int = 600,
    ) -> RunResult:
        env = {**os.environ, **(extra_env or {})}
        cmd = [
            self._python,
            str(self._adapter_dir / "run.py"),
            "--pillar", pillar,
            "--scenario", scenario_id,
            "--impl", impl_type,
            "--output", str(output_path),
        ]
        if run_id:
            cmd += ["--run-id", run_id]

        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=timeout_s
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Adapter '{self._adapter_dir.name}' exited {result.returncode}:\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

        if not output_path.exists():
            raise FileNotFoundError(
                f"Adapter did not write output to {output_path}. "
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

        return RunResult.from_yaml(output_path.read_text())

    @classmethod
    def for_adapter(cls, adapter_dir: Path) -> SubprocessRunner:
        """Auto-detects venv Python if present, falls back to current interpreter."""
        venv_python = adapter_dir / ".venv" / "bin" / "python"
        return cls(adapter_dir, venv_python if venv_python.exists() else None)
