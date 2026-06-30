import json
from pathlib import Path
from typing import Dict, Any, List

class GitHubLoader:
    """Loader to parse JSON containing GitHub profile and repository metadata."""
    
    def __init__(self):
        pass

    def load(self, file_path: str | Path) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            # If file does not exist, return a default mock representation for this path to keep execution robust
            return {
                "username": path.stem,
                "html_url": f"https://github.com/{path.stem}",
                "public_repos": 0,
                "repositories": []
            }
        
        with open(path, mode="r", encoding="utf-8") as f:
            data = json.load(f)
        return data
