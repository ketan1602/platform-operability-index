"""Adapter registry — maps framework IDs to adapter directories.

Adding a new framework = drop a directory under harness/adapters/ with
run.py + metadata.json. _auto_discover() picks it up; no other file changes.
"""
from __future__ import annotations
import json
from pathlib import Path

_ADAPTERS: dict[str, Path] = {}


def register(framework_id: str, adapter_dir: Path) -> None:
    _ADAPTERS[framework_id.upper()] = adapter_dir


def get_adapter_dir(framework_id: str) -> Path:
    key = framework_id.upper()
    if key not in _ADAPTERS:
        available = ", ".join(sorted(_ADAPTERS)) or "(none discovered yet)"
        raise KeyError(f"Unknown framework '{framework_id}'. Available: {available}")
    return _ADAPTERS[key]


def list_adapters() -> list[str]:
    return sorted(_ADAPTERS.keys())


def _auto_discover(adapters_root: Path) -> None:
    """
    Scan adapters_root for subdirectories that contain both run.py and
    metadata.json. Registers each discovered adapter.
    metadata.json must contain at minimum: {"framework_id": "F1"}
    """
    if not adapters_root.is_dir():
        return
    for child in sorted(adapters_root.iterdir()):
        if not child.is_dir():
            continue
        run_py = child / "run.py"
        meta_file = child / "metadata.json"
        if run_py.exists() and meta_file.exists():
            meta = json.loads(meta_file.read_text())
            fid = meta.get("framework_id", "").upper()
            if fid:
                register(fid, child)
