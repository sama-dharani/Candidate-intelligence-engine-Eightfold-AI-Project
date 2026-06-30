import json
from pathlib import Path
from typing import List, Dict, Any

class ATSLoader:
    """Loader to parse JSON files representing candidate records or lists of candidate records."""
    
    def __init__(self):
        pass

    def load(self, file_path: str | Path) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"JSON file not found: {path}")
        
        with open(path, mode="r", encoding="utf-8") as f:
            data = json.load(f)
            
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        else:
            raise ValueError("JSON content must be a dictionary or a list of dictionaries.")
