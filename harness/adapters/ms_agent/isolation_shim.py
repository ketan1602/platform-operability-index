"""isolation_shim — AutoGen F2 runaway-loop containment.

Lines between poi:custom markers are operator-written code required to add
loop limiting. AutoGen has no default; MaxMessageTermination must be wired in.
"""
from __future__ import annotations
import os
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat

# poi:custom-begin
_turn_limit = int(os.environ.get("AGENT_MAX_TURNS", "50"))
_turn_termination = MaxMessageTermination(max_messages=_turn_limit)
_stop_termination = TextMentionTermination("TERMINATE")
_termination = _turn_termination | _stop_termination
_team = RoundRobinGroupChat([...], termination_condition=_termination)
# poi:custom-end
