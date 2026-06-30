import csv
from pathlib import Path
from typing import List, Dict, Any

class CSVLoader:
    """Loader to parse CSV files and return list of row dictionaries."""
    
    def __init__(self):
        pass

    def load(self, file_path: str | Path) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"CSV file not found: {path}")
        
        results: List[Dict[str, Any]] = []
        # utf-8-sig automatically strips Byte Order Mark (BOM) if present
        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                results.append(dict(row))
        return results
