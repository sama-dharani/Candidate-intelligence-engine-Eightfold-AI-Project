import json
from pathlib import Path
from typing import Dict, Any, List, Optional

class ConfidenceEngine:
    """Computes candidate confidence score and generates human-readable explanations.

    Uses weights defined in configs/weights.json to calculate the score.
    """

    def __init__(self, weights_path: Optional[str | Path] = None):
        self.weights = {
            "email": 0.35,
            "phone": 0.25,
            "skills": 0.20,
            "github": 0.10,
            "linkedin": 0.05,
            "other": 0.05
        }
        if weights_path:
            path = Path(weights_path)
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        if "confidence" in cfg:
                            self.weights.update(cfg["confidence"])
                except Exception:
                    pass

    def compute(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Compute score and explainability reasons for a merged candidate profile."""
        score = 0.0
        reasons: List[str] = []

        w = self.weights
        provenance = candidate.get("provenance", [])
        field_prov = candidate.get("field_provenance", {})
        num_sources = len(provenance)
        
        def get_source_count(field_name: str) -> int:
            prov_data = field_prov.get(field_name, {})
            sources = set()
            if isinstance(prov_data, dict):
                for src_list in prov_data.values():
                    sources.update(src_list)
            elif isinstance(prov_data, list):
                sources.update(prov_data)
            return len(sources)

        # 1. Emails Confidence
        emails = candidate.get("emails", [])
        if emails:
            num_email_sources = get_source_count("emails")
            multiplier = min(1.5, 1.0 + 0.25 * max(0, num_email_sources - 1))
            score += w["email"] * multiplier
            if num_email_sources > 1:
                reasons.append(f"✔ Email verified across {num_email_sources} distinct sources (Dynamic Bonus)")
            else:
                reasons.append("✔ Email address provided and parsed")
        else:
            reasons.append("✖ No email address provided (-35%)")

        # 2. Phones Confidence
        phones = candidate.get("phones", [])
        if phones:
            num_phone_sources = get_source_count("phones")
            multiplier = min(1.5, 1.0 + 0.25 * max(0, num_phone_sources - 1))
            score += w["phone"] * multiplier
            if num_phone_sources > 1:
                reasons.append(f"✔ Phone number matched across {num_phone_sources} distinct sources (Dynamic Bonus)")
            else:
                reasons.append("✔ Phone number provided and validated")
        else:
            reasons.append("✖ No contact phone number found (-25%)")

        # 3. Skills Confidence
        skills = candidate.get("skills", [])
        if skills:
            # Dynamic scaling: up to 1.5x based on volume of skills
            skill_factor = min(1.5, len(skills) / 8.0)
            score += w["skills"] * skill_factor
            
            # Check if skills were cross-validated by GitHub or Resume
            skill_sources = []
            skill_prov_data = field_prov.get("skills", {})
            if isinstance(skill_prov_data, dict):
                for src_list in skill_prov_data.values():
                    skill_sources.extend(src_list)
            
            if len(skills) >= 12:
                reasons.append(f"✔ Exceptional skills profile ({len(skills)} skills parsed) (Dynamic Bonus)")
            elif len(skills) >= 5:
                reasons.append(f"✔ Rich skills profile ({len(skills)} skills parsed)")
            else:
                reasons.append(f"✔ Basic skills parsed ({len(skills)} skills)")
                
            if "github" in skill_sources:
                reasons.append("✔ Skills verified by GitHub projects and languages")
        else:
            reasons.append("✖ No technical skills extracted (-20%)")

        # 4. GitHub Presence
        gh = candidate.get("github")
        if gh:
            score += w["github"]
            reasons.append("✔ GitHub developer profile linked and verified")
        else:
            reasons.append("ℹ No GitHub profile linked")

        # 5. LinkedIn Presence
        li = candidate.get("linkedin")
        if li:
            score += w["linkedin"]
            reasons.append("✔ LinkedIn profile matched and parsed")
        else:
            reasons.append("ℹ No LinkedIn profile linked")

        # 6. Other/History density
        exp = candidate.get("experience", [])
        edu = candidate.get("education", [])
        if exp or edu:
            score += w["other"]
            if exp and edu:
                reasons.append("✔ Complete career profile (both education and work history present)")
            elif exp:
                reasons.append("✔ Work history present")
            else:
                reasons.append("✔ Education profile present")
        else:
            reasons.append("✖ Missing both experience and education data (-5%)")

        score = min(max(score, 0.0), 1.0)
        return {
            "score": round(score, 2),
            "reasons": reasons
        }
