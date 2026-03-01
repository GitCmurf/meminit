import pytest
from meminit.core.services.scan_plan import MigrationPlan, PlanAction, PlanActionType, ActionPreconditions, ActionSafety

def test_plan_action_id_generation():
    action = PlanActionType.INSERT_METADATA_BLOCK.value
    src = "README.md"
    tgt = "README.md"
    id1 = PlanAction.generate_id(action, src, tgt)
    id2 = PlanAction.generate_id(action, src, tgt)
    assert id1 == id2
    assert id1.startswith("PA_")
    
    id3 = PlanAction.generate_id(PlanActionType.MOVE_FILE.value, src, "docs/README.md")
    assert id1 != id3

def test_migration_plan_serialization():
    action = PlanAction(
        id="PA_123",
        action=PlanActionType.RENAME_FILE,
        source_path="old.md",
        target_path="new.md",
        confidence=0.9,
        rationale=["Test"],
        preconditions=ActionPreconditions(source_sha256="abc"),
        safety=ActionSafety(destructive=False, overwrites=False)
    )
    plan = MigrationPlan(config_fingerprint="xyz", actions=[action])
    d = plan.as_dict()
    
    assert d["plan_version"] == "1.0"
    assert d["config_fingerprint"] == "xyz"
    assert len(d["actions"]) == 1
    assert d["actions"][0]["id"] == "PA_123"
    assert d["actions"][0]["action"] == "rename_file"

def test_migration_plan_deserialization():
    data = {
        "plan_version": "1.0",
        "config_fingerprint": "xyz",
        "actions": [
            {
                "id": "PA_123",
                "action": "rename_file",
                "source_path": "old.md",
                "target_path": "new.md",
                "confidence": 0.9,
                "rationale": ["Test"],
                "preconditions": {"source_sha256": "abc"},
                "safety": {"destructive": False, "overwrites": False}
            }
        ]
    }
    plan = MigrationPlan.from_dict(data)
    assert plan.plan_version == "1.0"
    assert plan.config_fingerprint == "xyz"
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.id == "PA_123"
    assert action.action == PlanActionType.RENAME_FILE
    assert action.source_path == "old.md"
    assert action.preconditions.source_sha256 == "abc"
    assert action.safety.destructive is False

def test_migration_plan_sorting():
    a1 = PlanAction(id="1", action=PlanActionType.RENAME_FILE, source_path="b.md", target_path="b.md", confidence=0.0, rationale=[], preconditions=ActionPreconditions(), safety=ActionSafety())
    a2 = PlanAction(id="2", action=PlanActionType.MOVE_FILE, source_path="a.md", target_path="a.md", confidence=0.0, rationale=[], preconditions=ActionPreconditions(), safety=ActionSafety())
    a3 = PlanAction(id="3", action=PlanActionType.INSERT_METADATA_BLOCK, source_path="a.md", target_path="a.md", confidence=0.0, rationale=[], preconditions=ActionPreconditions(), safety=ActionSafety())
    
    plan = MigrationPlan(actions=[a1, a2, a3])
    plan.sort_actions()
    
    # Sort key is (source_path, action_priority, target_path, id). a.md before b.md. 
    # For a.md: INSERT_METADATA_BLOCK (priority 0) before MOVE_FILE (priority 3).
    # insert < move
    assert plan.actions[0].id == "3"
    assert plan.actions[1].id == "2"
    assert plan.actions[2].id == "1"
