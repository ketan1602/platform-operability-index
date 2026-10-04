"""isolation_shim — Strands Agents F5 runaway-loop containment.

Lines between poi:custom markers are operator-written code required to add
loop limiting. Agent(max_iterations=N) default is None (unlimited); must be set.
"""
from __future__ import annotations
import os

# poi:custom-begin
_max_iters = int(os.environ.get("AGENT_MAX_TURNS", "50"))
result = agent(task, max_iterations=_max_iters)
# poi:custom-end
