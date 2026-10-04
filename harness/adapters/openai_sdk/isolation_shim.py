"""isolation_shim — OpenAI Agents SDK F3 runaway-loop containment.

Lines between poi:custom markers are operator-written code required to add
loop limiting. Runner.run() default is unlimited turns; max_turns must be set.
"""
from __future__ import annotations
import os
from agents import Runner

# poi:custom-begin
_max_turns = int(os.environ.get("AGENT_MAX_TURNS", "50"))
result = await Runner.run(agent, input=prompt, max_turns=_max_turns)
_output = result.final_output
# poi:custom-end
