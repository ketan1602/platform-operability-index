from __future__ import annotations
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import os
import uuid
from datetime import datetime, timezone


class FrameworkId(str, Enum):
    F1 = "F1"   # LangGraph
    F2 = "F2"   # Microsoft Agent Framework
    F3 = "F3"   # OpenAI Agents SDK
    F4 = "F4"   # Google ADK
    F5 = "F5"   # Strands Agents


FRAMEWORK_NAMES: dict[FrameworkId, str] = {
    FrameworkId.F1: "LangGraph",
    FrameworkId.F2: "Microsoft Agent Framework",
    FrameworkId.F3: "OpenAI Agents SDK",
    FrameworkId.F4: "Google ADK",
    FrameworkId.F5: "Strands Agents",
}


class ScenarioId(str, Enum):
    GEW = "GEW"   # baseline workflow: enterprise approval chain
    TCW = "TCW"   # baseline workflow: telco CVM / next-best-action
    RLC = "RLC"   # ReAct loop containment            -> P2 evidence
    SMA = "SMA"   # supervisor multi-agent             -> P2, P3 evidence
    AHQ = "AHQ"   # async human approval, kill+resume  -> P1 evidence


class ImplementationType(str, Enum):
    FIXED = "fixed"
    IDIOMATIC = "idiomatic"


class Pillar(str, Enum):
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"
    P5 = "p5"
    ALL = "all"


class RunMetadata(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    framework_id: FrameworkId
    framework_version: str
    scenario_id: ScenarioId
    implementation_type: ImplementationType
    pillar: Pillar
    infrastructure: str = "orbstack-k8s"
    runner: str = Field(default_factory=lambda: os.environ.get("POI_RUNNER", "local"))
    run_mode: str = Field(
        default_factory=lambda: "dry_run" if os.environ.get("DRY_RUN") == "true" else "live"
    )
    repeat: int = 0


class PillarScores(BaseModel):
    p1: Optional[int] = None  # 0-3 or null if not run
    p2: Optional[int] = None
    p3: Optional[int] = None
    p4: Optional[int] = None
    p5: Optional[int] = None

    @property
    def poi_total(self) -> int:
        return sum(s for s in [self.p1, self.p2, self.p3, self.p4, self.p5] if s is not None)


class OperabilityTax(BaseModel):
    ot_loc: int = 0
    ot_hrs: float = 0.0
    ot_recurring_hrs_per_yr: float = 0.0


class RunResult(BaseModel):
    run_metadata: RunMetadata
    pillar_scores: PillarScores = Field(default_factory=PillarScores)
    operability_tax: OperabilityTax = Field(default_factory=OperabilityTax)
    raw_measurements: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    notes: str = ""

    def to_yaml(self) -> str:
        import yaml, json
        # Route through JSON so enums serialise as plain strings in both pydantic v1 and v2.
        # model_dump_json() = v2; json() = v1 (deprecated in v2 but still works).
        json_str = (
            self.model_dump_json() if hasattr(self, "model_dump_json") else self.json()
        )
        data = json.loads(json_str)
        data["pillar_scores"]["poi_total"] = self.pillar_scores.poi_total
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> RunResult:
        import yaml
        data = yaml.safe_load(text)
        data.get("pillar_scores", {}).pop("poi_total", None)
        return cls(**data)
