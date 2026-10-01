"""Count custom scaffolding lines between `# poi:custom-begin` and `# poi:custom-end` markers.

Operability tax is counted from code, not estimated: any framework-specific glue an
implementation needs beyond the framework's own API is fenced by these markers.
"""
from __future__ import annotations
from pathlib import Path

BEGIN, END = "# poi:custom-begin", "# poi:custom-end"


def count(path: Path) -> int:
    inside, total = False, 0
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line.startswith(BEGIN):
            inside = True
        elif line.startswith(END):
            inside = False
        elif inside and line and not line.startswith("#"):
            total += 1
    return total
