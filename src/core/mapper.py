import json
import re
from pathlib import Path
from typing import Any, List, Optional, Dict

class DynamicFieldMapper:
    """Map heterogeneous source fields to canonical candidate profile attributes.

    Loads a mapping JSON config (e.g. configs/mapping.json) defining aliases for
    each canonical field. Supports nested JSON paths and flat dictionary rows.
    """

    def __init__(self, mapping_path: str | Path):
        mapping_file = Path(mapping_path)
        if not mapping_file.is_file():
            raise FileNotFoundError(f"Mapping file not found: {mapping_file}")
        self.mapping: Dict[str, List[str]] = json.loads(mapping_file.read_text(encoding="utf-8"))

    @staticmethod
    def _clean(text: str) -> str:
        """Normalize a field name for comparison."""
        text = text.lower()
        text = text.replace("_", " ")
        text = text.replace("-", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _find_in_row(self, row: Any, canonical: str) -> Optional[Any]:
        """Search a flat row (dict-like) for a key matching the canonical field's aliases."""
        aliases = self.mapping.get(canonical, [])
        cleaned_aliases = [self._clean(a) for a in aliases]
        
        # Also include the canonical key itself
        cleaned_aliases.append(self._clean(canonical))
        
        if hasattr(row, "items"):
            for col, value in row.items():
                if self._clean(col) in cleaned_aliases:
                    return value
        return None

    def _recursive_find(self, data: Any, aliases: List[str], canonical: str = "") -> Optional[Any]:
        """Recursively search nested dictionaries/lists for a matching key."""
        cleaned_aliases = [self._clean(a) for a in aliases]
        if canonical:
            cleaned_aliases.append(self._clean(canonical))
        if isinstance(data, dict):
            for key, value in data.items():
                if self._clean(key) in cleaned_aliases:
                    return value
                result = self._recursive_find(value, aliases, canonical)
                if result is not None:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._recursive_find(item, aliases, canonical)
                if result is not None:
                    return result
        return None

    def find_value(self, source: Any, canonical: str) -> Optional[Any]:
        """Look up canonical attribute from source data (tries flat dictionary first, then nested)."""
        flat_result = self._find_in_row(source, canonical)
        if flat_result is not None:
            return flat_result
        
        aliases = self.mapping.get(canonical, [])
        return self._recursive_find(source, aliases, canonical)

    def get_all(self, source: Any) -> Dict[str, Any]:
        """Build and return a canonical candidate dictionary from the raw source."""
        result = {}
        for canonical in self.mapping.keys():
            value = self.find_value(source, canonical)
            if value is not None:
                # Basic string-to-list splitting if canonical target requires list (like emails, phones, skills)
                if canonical in ["emails", "phones", "skills", "certifications"]:
                    if isinstance(value, str):
                        # split by comma, semicolon or newline
                        value = [item.strip() for item in re.split(r"[,;\n]", value) if item.strip()]
                    elif not isinstance(value, list):
                        value = [str(value).strip()]
                result[canonical] = value
        return result
