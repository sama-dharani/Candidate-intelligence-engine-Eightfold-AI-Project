import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Optional, Union

try:
    import spacy
    try:
        _nlp = spacy.load("en_core_web_sm")
    except OSError:
        _nlp = None
except ImportError:
    _nlp = None

class ResumeParser:
    """Parse raw resume text and extract structured fields deterministically."""

    def __init__(self, skills_config_path: Optional[Union[str, Path]] = None):
        self.skills: List[str] = []
        if skills_config_path:
            skill_path = Path(skills_config_path)
            if skill_path.is_file():
                with skill_path.open("r", encoding="utf-8") as f:
                    skill_data = json.load(f)
                for category_skills in skill_data.values():
                    self.skills.extend(category_skills)

    # ── Section Chunking ─────────────────────────────────────────

    @staticmethod
    def _chunk_sections(text: str) -> Dict[str, str]:
        headers = {
            "experience": [
                r"^experience$",
                r"^professional\s+experience$",
                r"^work\s+experience$",
                r"^employment$",
                r"^career\s+history$",
                r"^work\s+history$",
                r"^career$"
            ],
            "education": [r"^education$", r"^academic background$", r"^scholastic$", r"^qualifications$", r"^academic history$"],
            "projects": [r"^projects$", r"^personal projects$", r"^academic projects$", r"^key projects$"],
            "skills": [r"^skills$", r"^technical skills$", r"^core competencies$", r"^technologies$", r"^expertise$"],
            "summary": [r"^summary$", r"^profile$", r"^professional summary$", r"^about me$", r"^objective$"],
            "certifications": [r"^certifications$", r"^certificates$", r"^licenses$"],
            "awards": [r"^awards$", r"^honors$", r"^achievements$"],
            "languages": [r"^languages$", r"^spoken languages$"],
            "portfolio": [r"^portfolio$", r"^websites$", r"^links$"],
            "internships": [
                r"^internship$",
                r"^internships$",
                r"^internship\s+experience$",
                r"^industrial\s+training$",
                r"^training$"
            ],
            "research": [r"^research$", r"^publications$", r"^research\s+experience$"],
            "volunteer": [r"^volunteer$", r"^volunteering$", r"^community service$", r"^extracurricular$"]
        }
        
        sections = {}
        current_section = "header"
        sections[current_section] = []
        
        for line in text.split('\n'):
            clean_line = line.strip().lower()
            # Remove bullets or trailing colons for header matching
            clean_line = re.sub(r"^[\W_]+|[\W_]+$", "", clean_line).strip()
            
            matched = False
            if len(clean_line) > 2 and len(clean_line) < 35:
                for sec_name, patterns in headers.items():
                    if any(re.match(p, clean_line) for p in patterns):
                        current_section = sec_name
                        if current_section not in sections:
                            sections[current_section] = []
                        matched = True
                        break
            
            if not matched:
                sections[current_section].append(line)
                
        return {k: '\n'.join(v).strip() for k, v in sections.items() if any(x.strip() for x in v)}

    # ── Field Extractors ──────────────────────────────────────────

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        return list({e.lower().strip() for e in re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text)})

    @staticmethod
    def extract_phones(text: str) -> List[str]:
        raw = re.findall(r"\+?\d[\d\s\-\(\)]{8,}\d", text)
        cleaned = []
        for p in raw:
            p_clean = re.sub(r"[\s\-\(\)]", "", p)
            if 9 <= len(p_clean) <= 15:
                if re.search(r"(19|20)\d{2}(19|20)\d{2}", p_clean):
                    continue
                cleaned.append(p_clean)
        return list(set(cleaned))

    @staticmethod
    def extract_links(text: str) -> Dict[str, List[str]]:
        github = list({m for m in re.findall(r"https?://(?:www\.)?github\.com/[a-zA-Z0-9\-_]+", text)})
        linkedin = list({m for m in re.findall(r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_]+", text)})
        portfolio = list({m for m in re.findall(r"https?://(?:www\.)?(?!github|linkedin)[a-zA-Z0-9\-_]+\.[a-zA-Z]{2,}(?:/[^\s]*)?", text)})
        return {"github": github, "linkedin": linkedin, "portfolio": portfolio}

    @staticmethod
    def extract_name(text: str) -> str:
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for line in lines[:8]:
            if any(k in line.lower() for k in ["email", "phone", "github", "linkedin", "address", "resume", "curriculum", "page"]):
                continue
            cleaned_line = re.sub(r"[^a-zA-Z\s\.]", "", line).strip()
            words = cleaned_line.split()
            if 2 <= len(words) <= 4:
                if cleaned_line.isupper():
                    return " ".join(w.capitalize() for w in words)
                if all(w[0].isupper() for w in words if w and w[0].isalpha()):
                    return cleaned_line
        if _nlp:
            doc = _nlp(text[:2000])
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    val = ent.text.strip()
                    if len(val.split()) >= 2 and not any(t in val.lower() for t in ["resume", "curriculum", "engineer", "developer"]):
                        return val
        return "Unknown Candidate"
        
    @staticmethod
    def extract_location(text: str) -> str:
        # Heuristic: look for city, state/country in the header
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for line in lines[:10]:
            # common pattern: City, State or City, Country
            match = re.search(r"([A-Z][a-zA-Z\s]+),\s*([A-Z]{2}|[A-Z][a-zA-Z\s]+)", line)
            if match and "email" not in line.lower() and "@" not in line:
                return match.group(0)
        return ""

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

    @staticmethod
    def parse_experience(exp_text: str, default_employment_type: str = "Full-Time") -> List[Dict[str, Any]]:
        # Look for dates to denote a new job entry
        date_pattern = r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\/]+\d{4}|\d{4})\s*(?:-|to|–)\s*(Present|Current|\w+[\s\-\/]+\d{4}|\d{4})"
        
        experiences = []
        lines = exp_text.split("\n")
        
        current_exp = {}
        desc_lines = []
        
        import datetime
        current_year = datetime.datetime.now().year
        
        def finalize_entry(entry, d_lines):
            description = "\n".join(d_lines).strip()
            entry["description"] = description
            entry["summary"] = d_lines
            
            # Extract technologies
            common_tech = ["python", "react", "aws", "docker", "kubernetes", "redis", "postgresql", "mysql", "mongodb", "pytorch", "tensorflow", "langchain", "crewai", "java", "spring boot", "javascript", "typescript", "c++", "c", "ci/cd", "git", "flask", "django"]
            techs_found = []
            text_for_tech = (entry["title"] + " " + description).lower()
            for tech in common_tech:
                if re.search(rf"\b{re.escape(tech)}\b", text_for_tech):
                    display_tech = tech.title() if tech not in ["aws", "git", "ci/cd", "ml", "ai", "sql"] else tech.upper()
                    if tech == "spring boot":
                        display_tech = "Spring Boot"
                    techs_found.append(display_tech)
            entry["technologies"] = techs_found
            
            # Infer employment type from keywords
            emp_type = default_employment_type
            text_for_type = (entry["title"] + " " + description).lower()
            if "intern" in text_for_type or "training" in text_for_type:
                emp_type = "Internship"
            elif "contract" in text_for_type or "consultant" in text_for_type:
                emp_type = "Contract"
            elif "part-time" in text_for_type or "part time" in text_for_type:
                emp_type = "Part-Time"
            elif "research" in text_for_type:
                emp_type = "Research"
            entry["employment_type"] = emp_type
            
            # Calculate duration
            start_date = entry["start_date"]
            end_date = entry["end_date"]
            start_yr = None
            end_yr = None
            start_match = re.search(r"\b(19\d{2}|20\d{2})\b", start_date)
            if start_match:
                start_yr = int(start_match.group(1))
            end_match = re.search(r"\b(19\d{2}|20\d{2})\b", end_date)
            if end_match:
                end_yr = int(end_match.group(1))
            elif "present" in end_date.lower() or "current" in end_date.lower():
                end_yr = current_year
                
            if start_yr and end_yr:
                diff = max(1, end_yr - start_yr)
                entry["duration"] = f"{diff} yr{'s' if diff > 1 else ''}"
            else:
                entry["duration"] = ""
            return entry

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            
            match = re.search(date_pattern, line_clean, re.IGNORECASE)
            if match:
                # Save previous
                if current_exp:
                    experiences.append(finalize_entry(current_exp, desc_lines))
                
                start_date = match.group(1).strip()
                end_date = match.group(2).strip()
                
                # Guess company and title from the line
                text_before = line_clean[:match.start()].strip(" -,\t|")
                
                title = ""
                company = ""
                
                if text_before:
                    if " at " in f" {text_before.lower()} ":
                        idx = text_before.lower().find(" at ")
                        title = text_before[:idx].strip(" -,\t|")
                        company = text_before[idx+4:].strip(" -,\t|")
                    elif "," in text_before:
                        parts = [p.strip() for p in text_before.split(",")]
                        title_keywords = ["engineer", "developer", "lead", "architect", "manager", "analyst", "intern", "consultant", "specialist", "scientist", "sde", "designer", "head"]
                        if any(k in parts[0].lower() for k in title_keywords):
                            title = parts[0]
                            company = " ".join(parts[1:])
                        else:
                            company = parts[0]
                            title = " ".join(parts[1:])
                    elif " - " in text_before:
                        parts = [p.strip() for p in text_before.split(" - ")]
                        if len(parts) > 1:
                            company = parts[0]
                            title = parts[1]
                        else:
                            company = parts[0]
                    else:
                        title_keywords = ["engineer", "developer", "lead", "architect", "manager", "analyst", "intern", "consultant", "specialist", "scientist", "sde", "designer", "head"]
                        if any(k in text_before.lower() for k in title_keywords):
                            title = text_before
                        else:
                            company = text_before
                
                current_exp = {
                    "company": company or "Tech Company",
                    "title": title or "Software Engineer",
                    "start": start_date,
                    "end": end_date,
                    "start_date": start_date,
                    "end_date": end_date,
                    "employment_type": default_employment_type,
                    "duration": "",
                    "summary": [],
                    "description": "",
                    "technologies": []
                }
                desc_lines = []
            else:
                if current_exp:
                    bullet_cleaned = re.sub(r"^[\-\•\*\s]+", "", line_clean).strip()
                    desc_lines.append(bullet_cleaned)
                    
        if current_exp:
            experiences.append(finalize_entry(current_exp, desc_lines))
            
        return experiences

    @staticmethod
    def parse_education(edu_text: str) -> List[Dict[str, Any]]:
        date_pattern = r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\/]+\d{4}|\d{4})\s*(?:-|to|–)\s*(Present|Current|\w+[\s\-\/]+\d{4}|\d{4})"
        
        educations = []
        lines = edu_text.split("\n")
        
        current_edu = {}
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
                
            match = re.search(date_pattern, line_clean, re.IGNORECASE)
            if match:
                if current_edu:
                    educations.append(current_edu)
                
                current_edu = {
                    "institution": "",
                    "degree": "",
                    "start_date": match.group(1).strip(),
                    "end_date": match.group(2).strip()
                }
                text_before = line_clean[:match.start()].strip(" -,\t|")
                if text_before:
                    if "," in text_before:
                        parts = [p.strip() for p in text_before.split(",")]
                        current_edu["degree"] = parts[0]
                        current_edu["institution"] = " ".join(parts[1:])
                    else:
                        current_edu["institution"] = text_before
            else:
                if current_edu:
                    if not current_edu.get("degree") and len(line_clean) < 80:
                        current_edu["degree"] = line_clean
        
        if current_edu:
            educations.append(current_edu)
            
        return educations

    @staticmethod
    def split_lines(text: str) -> List[str]:
        return [re.sub(r"^[\-\•\*\s]+", "", ln).strip() for ln in text.split("\n") if ln.strip()]

    # ── Public API ────────────────────────────────────────────────

    def parse_text(self, text: str) -> Dict[str, Any]:
        sections = self._chunk_sections(text)
        header_text = sections.get("header", text[:1000])
        
        links = self.extract_links(text)
        
        return {
            "full_name": self.extract_name(header_text),
            "emails": self.extract_emails(text),
            "phones": self.extract_phones(text),
            "location": self.extract_location(header_text),
            "headline": "",
            "summary": sections.get("summary", ""),
            "experience": self.parse_experience(sections.get("experience", ""), default_employment_type="Full-Time"),
            "education": self.parse_education(sections.get("education", "")),
            "skills": self.extract_skills(text), # fallback to global skill extraction
            "projects": self.parse_experience(sections.get("projects", ""), default_employment_type="Full-Time"), # Can reuse experience parser format
            "certifications": self.split_lines(sections.get("certifications", "")),
            "awards": self.split_lines(sections.get("awards", "")),
            "github": links["github"][0] if links["github"] else "",
            "linkedin": links["linkedin"][0] if links["linkedin"] else "",
            "portfolio": links["portfolio"][0] if links["portfolio"] else "",
            "languages": self.split_lines(sections.get("languages", "")),
            "achievements": self.split_lines(sections.get("achievements", "")),
            "internships": self.parse_experience(sections.get("internships", ""), default_employment_type="Internship"),
            "research": self.parse_experience(sections.get("research", ""), default_employment_type="Research"),
            "volunteer": self.parse_experience(sections.get("volunteer", ""), default_employment_type="Volunteer"),
            "_raw_text": text
        }
