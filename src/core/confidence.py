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
        num_sources = len(provenance)

        # 1. Emails Confidence
        emails = candidate.get("emails", [])
        if emails:
            # Check how many sources contributed email
            email_sources = [p["source_index"] for p in provenance if "emails" in p.get("fields_contributed", [])]
            score += w["email"]
            if len(email_sources) > 1:
                reasons.append(f"✔ Email verified across {len(email_sources)} distinct sources")
            else:
                reasons.append("✔ Email address provided and parsed")
        else:
            reasons.append("✖ No email address provided (-35%)")

        # 2. Phones Confidence
        phones = candidate.get("phones", [])
        if phones:
            phone_sources = [p["source_index"] for p in provenance if "phones" in p.get("fields_contributed", [])]
            score += w["phone"]
            if len(phone_sources) > 1:
                reasons.append(f"✔ Phone number matched across {len(phone_sources)} distinct sources")
            else:
                reasons.append("✔ Phone number provided and validated")
        else:
            reasons.append("✖ No contact phone number found (-25%)")

        # 3. Skills Confidence
        skills = candidate.get("skills", [])
        if skills:
            skill_factor = min(1.0, len(skills) / 8.0)  # max contribution at 8 skills
            score += w["skills"] * skill_factor
            
            # Check if skills were cross-validated by GitHub or Resume
            skill_sources = [p["source_type"] for p in provenance if "skills" in p.get("fields_contributed", [])]
            if len(skills) >= 5:
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
