import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Optional, Union

# spaCy is optional — if not installed, regex fallbacks are used
try:
    import spacy
    try:
        _nlp = spacy.load("en_core_web_sm")
    except OSError:
        _nlp = None
except ImportError:
    _nlp = None


class ResumeParser:
    """Parse raw resume text and extract structured contact/profile fields.

    Uses regex as the primary extraction method; enhances with spaCy NER
    when available (en_core_web_sm model required).
    """

    def __init__(self, skills_config_path: Optional[Union[str, Path]] = None):
        self.skills: List[str] = []
        if skills_config_path:
            skill_path = Path(skills_config_path)
            if skill_path.is_file():
                with skill_path.open("r", encoding="utf-8") as f:
                    skill_data: Dict[str, List[str]] = json.load(f)
                for category_skills in skill_data.values():
                    self.skills.extend(category_skills)

    # ── Contact extraction ────────────────────────────────────────

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        return list({e.lower().strip()
                     for e in re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text)})

    @staticmethod
    def extract_phones(text: str) -> List[str]:
        raw = re.findall(r"\+?\d[\d\s\-\(\)]{8,}\d", text)
        cleaned = []
        for p in raw:
            p_clean = re.sub(r"[\s\-\(\)]", "", p)
            if 9 <= len(p_clean) <= 15:
                cleaned.append(p_clean)
        return list(set(cleaned))

    # ── Name extraction ───────────────────────────────────────────

    @staticmethod
    def extract_name(text: str) -> str:
        """Best-effort name extraction: regex line heuristic → spaCy → fallback."""
        # 1. Regex heuristic: check first few lines of text
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for line in lines[:8]:
            # Skip lines with common non-name headers or symbols
            if any(k in line.lower() for k in ["email", "phone", "github", "linkedin", "address", "resume", "curriculum", "page"]):
                continue
            
            # Check for name pattern (either Title Case or ALL CAPS name, 2 to 4 words)
            cleaned_line = re.sub(r"[^a-zA-Z\s\.]", "", line).strip()
            words = cleaned_line.split()
            if 2 <= len(words) <= 4:
                # If it's all uppercase (e.g. SAMA DHARANI), convert it to title case (e.g. Sama Dharani)
                if cleaned_line.isupper():
                    return " ".join(w.capitalize() for w in words)
                # If it is already in Title Case or similar
                if all(w[0].isupper() for w in words if w and w[0].isalpha()):
                    return cleaned_line

        # 2. spaCy path
        if _nlp:
            doc = _nlp(text[:2000])
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    val = ent.text.strip()
                    if len(val.split()) >= 2 and not any(
                        t in val.lower()
                        for t in ["resume", "curriculum", "engineer", "developer"]
                    ):
                        return val
                        
        return "Unknown Candidate"

    # ── Skills extraction ─────────────────────────────────────────

    def extract_skills(self, text: str) -> List[str]:
        if not self.skills:
            return []
        lower = text.lower()
        found: Set[str] = set()
        for skill in self.skills:
            pattern = rf"(?<!\w){re.escape(skill.lower())}(?!\w)"
            if re.search(pattern, lower):
                found.add(skill)
        return sorted(found)

    # ── Link extraction ───────────────────────────────────────────

    @staticmethod
    def extract_links(text: str) -> Dict[str, List[str]]:
        github   = list({m for m in re.findall(
            r"https?://(?:www\.)?github\.com/[a-zA-Z0-9\-_]+", text)})
        linkedin = list({m for m in re.findall(
            r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_]+", text)})
        return {"github": github, "linkedin": linkedin}

    # ── Public API ────────────────────────────────────────────────

    def parse_text(self, text: str) -> Dict[str, Any]:
        links = self.extract_links(text)
        return {
            "full_name": self.extract_name(text),
            "emails":    self.extract_emails(text),
            "phones":    self.extract_phones(text),
            "skills":    self.extract_skills(text),
            "github":    links["github"][0]   if links["github"]   else "",
            "linkedin":  links["linkedin"][0] if links["linkedin"] else "",
        }
