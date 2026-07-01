import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import difflib

class EntityResolver:
    """Decides if two candidate records refer to the same person.

    Uses a weighted matching score:
    - If at least one email matches exactly, similarity is 1.0 (100%).
    - Otherwise, compute weighted similarity across Name (30%), Email (35%),
      Phone (20%), LinkedIn (10%), and GitHub (5%).
    """

    def __init__(self, weights_path: Optional[str | Path] = None, threshold: float = 0.80):
        self.threshold = threshold
        self.weights = {
            "name": 0.30,
            "email": 0.35,
            "phone": 0.20,
            "linkedin": 0.10,
            "github": 0.05
        }
        if weights_path:
            path = Path(weights_path)
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        if "entity_resolution" in cfg:
                            self.weights.update(cfg["entity_resolution"])
                except Exception:
                    pass

    @staticmethod
    def _clean_name(name: Optional[str]) -> str:
        if not name:
            return ""
        name = name.lower()
        name = re.sub(r"[^a-z0-9\s]", "", name)  # remove special chars
        return " ".join(name.split())

    @staticmethod
    def _clean_phone(phone: Optional[str]) -> str:
        if not phone:
            return ""
        return re.sub(r"[\s\-\(\)\+]", "", phone).strip()

    @staticmethod
    def _extract_handle(url: Optional[str], domain: str) -> str:
        if not url:
            return ""
        url = url.lower().strip()
        # Remove trailing slashes
        url = url.rstrip("/")
        # Regex to capture handle
        match = re.search(rf"{domain}/(?:in/|users/)?([^/?#]+)", url)
        if match:
            return match.group(1)
        return url

    def _similarity_score(self, rec1: Dict[str, Any], rec2: Dict[str, Any]) -> Dict[str, Any]:
        """Compute matching score and field-level similarities between two candidate records."""
        
        # 1. Exact Email Match Check
        emails1 = [e.lower().strip() for e in rec1.get("emails", []) if isinstance(e, str) and e.strip()]
        emails2 = [e.lower().strip() for e in rec2.get("emails", []) if isinstance(e, str) and e.strip()]
        
        # If there's any exact email overlap
        if emails1 and emails2 and (set(emails1) & set(emails2)):
            return {
                "score": 1.0,
                "reasons": ["Exact email match found"],
                "details": {"email": 1.0}
            }

        # 2. Weighted similarity computation
        # Name Similarity (difflib SequenceMatcher ratio)
        name1 = self._clean_name(rec1.get("full_name", ""))
        name2 = self._clean_name(rec2.get("full_name", ""))
        name_sim = 0.0
        if name1 and name2:
            name_sim = difflib.SequenceMatcher(None, name1, name2).ratio()
            
        # Email Similarity (set intersection over union if not exact, or 0)
        email_sim = 0.0
        if emails1 and emails2:
            union = len(set(emails1) | set(emails2))
            email_sim = len(set(emails1) & set(emails2)) / union if union > 0 else 0.0
            
        # Phone Similarity
        phones1 = [self._clean_phone(p) for p in rec1.get("phones", []) if isinstance(p, str) and self._clean_phone(p)]
        phones2 = [self._clean_phone(p) for p in rec2.get("phones", []) if isinstance(p, str) and self._clean_phone(p)]
        phone_sim = 0.0
        if phones1 and phones2:
            if set(phones1) & set(phones2):
                phone_sim = 1.0
            else:
                # Check for suffix matching (e.g. matching last 10 digits)
                for p1 in phones1:
                    for p2 in phones2:
                        if len(p1) >= 10 and len(p2) >= 10 and p1[-10:] == p2[-10:]:
                            phone_sim = 0.9
                            break
                    if phone_sim > 0:
                        break
        
        # Github Similarity
        gh1 = rec1.get("github") or ""
        if isinstance(gh1, list) and gh1: gh1 = gh1[0]
        gh2 = rec2.get("github") or ""
        if isinstance(gh2, list) and gh2: gh2 = gh2[0]
        
        h_gh1 = self._extract_handle(gh1, "github.com")
        h_gh2 = self._extract_handle(gh2, "github.com")
        github_sim = 1.0 if (h_gh1 and h_gh2 and h_gh1 == h_gh2) else 0.0

        # LinkedIn Similarity
        li1 = rec1.get("linkedin") or ""
        if isinstance(li1, list) and li1: li1 = li1[0]
        li2 = rec2.get("linkedin") or ""
        if isinstance(li2, list) and li2: li2 = li2[0]
        
        h_li1 = self._extract_handle(li1, "linkedin.com")
        h_li2 = self._extract_handle(li2, "linkedin.com")
        linkedin_sim = 1.0 if (h_li1 and h_li2 and h_li1 == h_li2) else 0.0

        # Weighted calculation
        w = self.weights
        total_score = (
            name_sim * w["name"] +
            email_sim * w["email"] +
            phone_sim * w["phone"] +
            linkedin_sim * w["linkedin"] +
            github_sim * w["github"]
        )

        reasons = []
        if name_sim >= 0.8: reasons.append(f"Name matched at {int(name_sim*100)}%")
        if phone_sim >= 0.9: reasons.append("Phone verified")
        if github_sim == 1.0: reasons.append("GitHub profile matched")
        if linkedin_sim == 1.0: reasons.append("LinkedIn profile matched")
        if not reasons: reasons.append("Low individual feature similarity")

        return {
            "score": round(total_score, 3),
            "reasons": reasons,
            "details": {
                "name": round(name_sim, 2),
                "email": round(email_sim, 2),
                "phone": round(phone_sim, 2),
                "linkedin": round(linkedin_sim, 2),
                "github": round(github_sim, 2)
            }
        }

    def is_same_candidate(self, rec1: Dict[str, Any], rec2: Dict[str, Any]) -> bool:
        """Return True if similarity score meets the threshold."""
        return self._similarity_score(rec1, rec2)["score"] >= self.threshold
