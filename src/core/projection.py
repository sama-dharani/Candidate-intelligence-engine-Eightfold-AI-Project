import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

class ProfileProjector:
    """Filters, masks, and redacts fields on candidate profiles at runtime."""

    def __init__(self, rules_path: str | Path):
        path = Path(rules_path)
        if not path.is_file():
            raise FileNotFoundError(f"Projection rules file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            self.rules: Dict[str, Any] = json.load(f)

    def project(self, candidate: Dict[str, Any], view_name: Union[str, Dict[str, Any]] = "full") -> Dict[str, Any]:
        """Project candidate profile to a specific view name or a custom rule dict.
        
        Supports inclusion, exclusion, and redaction masking.
        """
        if isinstance(view_name, dict):
            rule = view_name
        else:
            if view_name not in self.rules:
                view_name = "full"
            rule = self.rules[view_name]

        includes: List[str] = rule.get("include", ["*"])
        excludes: List[str] = rule.get("exclude", [])
        redactions: Dict[str, str] = rule.get("redact", {})

        projected = {}

        # 1. Handle Inclusion
        if "*" in includes:
            projected = {k: v for k, v in candidate.items()}
        else:
            for k in includes:
                if k in candidate:
                    projected[k] = candidate[k]

        # 2. Handle Exclusion
        if "*" in excludes:
            # Keep only explicitly included keys
            pass
        else:
            for k in excludes:
                if k in projected:
                    del projected[k]

        # 3. Handle Redaction Masking
        for k, mask in redactions.items():
            if k in projected:
                val = projected[k]
                if isinstance(val, list):
                    projected[k] = [mask] * len(val) if val else []
                elif isinstance(val, dict):
                    projected[k] = {sub_k: mask for sub_k in val}
                else:
                    projected[k] = mask

        return projected
