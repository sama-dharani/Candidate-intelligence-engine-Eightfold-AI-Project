import json
from pathlib import Path
from typing import Dict, Any

class LinkedInLoader:
    """Loader to parse JSON containing LinkedIn profile data."""
    
    def __init__(self):
        pass

    def load(self, file_path: str | Path) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            # Fallback mock representation for missing profiles
            return {
                "linkedin_id": path.stem,
                "profile_url": f"https://linkedin.com/in/{path.stem}",
                "headline": "",
                "experience": [],
                "skills": []
            }
        
        with open(path, mode="r", encoding="utf-8") as f:
            data = json.load(f)
        return data
