import json
from pathlib import Path
from typing import List
from pydantic import TypeAdapter

from app.schemas.compliance import RuleDefinition

def load_rules(file_path: str) -> List[RuleDefinition]:
    """
    Loads rules from a JSON file deterministically.
    Fails on malformed files.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Rule pack not found: {file_path}")
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    adapter = TypeAdapter(List[RuleDefinition])
    rules = adapter.validate_json(content)
    
    # Sort deterministically by rule_id then effective_from
    rules.sort(key=lambda r: (r.rule_id, r.effective_from))
    
    return rules

def load_production_rules() -> List[RuleDefinition]:
    """
    Loads the default authoritative India LMPC rule pack.
    """
    base_dir = Path(__file__).resolve().parent.parent
    path = base_dir / "rules" / "india_lmpc_rules.json"
    return load_rules(str(path))
