import json
from pathlib import Path
from jsonschema import Draft7Validator, ValidationError
from typing import Tuple, List, Dict, Any

class CandidateValidator:
    """Validator that validates final candidate records against the Draft-07 candidate schema."""

    def __init__(self, schema_path: str | Path):
        path = Path(schema_path)
        if not path.is_file():
            raise FileNotFoundError(f"Schema file not found at: {path}")
        
        with open(path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)
        self.validator = Draft7Validator(self.schema)

    def validate(self, candidate: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate candidate profile.

        Returns a tuple: (is_valid: bool, error_messages: List[str])
        """
        errors = []
        for error in self.validator.iter_errors(candidate):
            # Format clean error message
            path = " -> ".join([str(p) for p in error.path])
            location = f" at '{path}'" if path else ""
            errors.append(f"{error.message}{location}")
        
        return len(errors) == 0, errors
