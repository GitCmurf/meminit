from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Any, Optional
import hashlib
import json

class PlanActionType(str, Enum):
    INSERT_METADATA_BLOCK = "insert_metadata_block"
    UPDATE_METADATA = "update_metadata"
    MOVE_FILE = "move_file"
    RENAME_FILE = "rename_file"

@dataclass
class ActionPreconditions:
    source_sha256: Optional[str] = None
    
    def as_dict(self) -> Dict[str, Any]:
        d = {}
        if self.source_sha256:
            d["source_sha256"] = self.source_sha256
        return d

@dataclass
class ActionSafety:
    destructive: bool = False
    overwrites: bool = False

    def as_dict(self) -> Dict[str, bool]:
        return {"destructive": self.destructive, "overwrites": self.overwrites}

@dataclass
class PlanAction:
    id: str
    action: PlanActionType
    source_path: str
    target_path: str
    confidence: float
    rationale: List[str]
    preconditions: ActionPreconditions
    safety: ActionSafety
    metadata_patch: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "action": self.action.value if isinstance(self.action, Enum) else self.action,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "preconditions": self.preconditions.as_dict(),
            "safety": self.safety.as_dict(),
        }
        if self.metadata_patch is not None:
            d["metadata_patch"] = self.metadata_patch
        return d
    
    @classmethod
    def generate_id(cls, action: str, source_path: str, target_path: str) -> str:
        s = f"{action}:{source_path}:{target_path}"
        return "PA_" + hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]
    
    def sort_key(self) -> tuple:
        priority = {
            PlanActionType.INSERT_METADATA_BLOCK: 0,
            PlanActionType.UPDATE_METADATA: 1,
            PlanActionType.RENAME_FILE: 2,
            PlanActionType.MOVE_FILE: 3,
        }
        try:
            action_enum = self.action if isinstance(self.action, PlanActionType) else PlanActionType(self.action)
            action_priority = priority.get(action_enum, 99)
        except ValueError:
            action_priority = 99
        return (self.source_path, action_priority, self.target_path, self.id)

@dataclass
class MigrationPlan:
    plan_version: str = "1.0"
    generated_at: str = ""
    config_fingerprint: str = ""
    actions: List[PlanAction] = field(default_factory=list)
    _sorted: bool = field(default=False, init=False, repr=False)

    def sort_actions(self):
        self.actions.sort(key=lambda a: a.sort_key())
        self._sorted = True

    def as_dict(self) -> Dict[str, Any]:
        if not self._sorted:
            self.sort_actions()
        return {
            "plan_version": self.plan_version,
            "generated_at": self.generated_at,
            "config_fingerprint": self.config_fingerprint,
            "actions": [a.as_dict() for a in self.actions]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationPlan":
        actions = []
        for a_data in data.get("actions", []):
            try:
                action_type = PlanActionType(a_data.get("action"))
            except ValueError:
                action_type = a_data.get("action")  # Allow unknown actions to be parsed but failed during validation
                
            pre = a_data.get("preconditions", {})
            preconditions = ActionPreconditions(source_sha256=pre.get("source_sha256"))
            
            saf = a_data.get("safety", {})
            safety = ActionSafety(destructive=bool(saf.get("destructive", False)), overwrites=bool(saf.get("overwrites", False)))
            
            a = PlanAction(
                id=a_data.get("id", ""),
                action=action_type,
                source_path=a_data.get("source_path", ""),
                target_path=a_data.get("target_path", ""),
                confidence=float(a_data.get("confidence", 0.0)),
                rationale=a_data.get("rationale", []),
                preconditions=preconditions,
                safety=safety,
                metadata_patch=a_data.get("metadata_patch")
            )
            actions.append(a)
            
        plan = cls(
            plan_version=data.get("plan_version", "1.0"),
            generated_at=data.get("generated_at", ""),
            config_fingerprint=data.get("config_fingerprint", ""),
            actions=actions
        )
        plan.sort_actions()
        plan._sorted = True
        return plan
