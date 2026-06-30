import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

class SkillClassifier:
    """Classifies candidate skills into domains and estimates proficiency and confidence."""

    def __init__(self, taxonomy_path: Optional[str | Path] = None):
        self.taxonomy = {
            "Programming": ["python", "java", "javascript", "c++", "go", "typescript", "ruby", "rust"],
            "AI": ["tensorflow", "pytorch", "langchain", "crewai", "keras", "scikit-learn", "machine learning", "deep learning", "llm"],
            "Cloud": ["aws", "gcp", "azure", "google cloud", "amazon web services"],
            "Containers": ["docker", "kubernetes", "k8s", "helm", "devops"],
            "Database": ["redis", "postgresql", "mysql", "mongodb", "sqlite", "sql"]
        }
        if taxonomy_path:
            path = Path(taxonomy_path)
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self.taxonomy = json.load(f)
                except Exception:
                    pass

    def classify(self, skill: str) -> str:
        """Find the taxonomic category for a skill using fuzzy lookup."""
        skill_lower = skill.lower().strip()

        # Pass 1: exact match across all domains first
        for domain, skills_list in self.taxonomy.items():
            if skill_lower in [s.lower() for s in skills_list]:
                return domain

        # Pass 2: substring match (only if no exact match found)
        for domain, skills_list in self.taxonomy.items():
            for s in skills_list:
                s_l = s.lower()
                if s_l == skill_lower:
                    return domain
                # Only accept substring if the skill is at least 4 chars to avoid false positives
                if len(skill_lower) >= 4 and (s_l in skill_lower or skill_lower in s_l):
                    return domain

        return "Programming"  # fallback default category

    def analyze_skills(self, candidate: Dict[str, Any], raw_text: str = "") -> Dict[str, Any]:
        """Analyze each skill in the candidate profile, estimating proficiency and confidence.
        
        Analyzes occurrences in:
        - raw_text (frequency)
        - experience list (work duration)
        - projects list (hands-on usage)
        - github repositories (if present)
        """
        skills = candidate.get("skills", [])
        experience = candidate.get("experience", [])
        projects = candidate.get("projects", [])
        github_data = candidate.get("_github_raw", {})  # raw github loader payload if present
        
        analysis = {}
        text_lower = raw_text.lower()

        # Calculate total work duration
        total_exp_years = len(experience) * 1.5  # fallback estimate

        for skill in skills:
            domain = self.classify(skill)
            skill_lower = skill.lower().strip()
            
            # 1. Frequency in Resume Text
            freq = len(re.findall(rf"\b{re.escape(skill_lower)}\b", text_lower)) if text_lower else 1
            
            # 2. Used in Projects?
            proj_match = False
            for proj in projects:
                tech_stack = [t.lower() for t in proj.get("technologies", [])]
                if skill_lower in tech_stack or skill_lower in proj.get("description", "").lower():
                    proj_match = True
                    break
                    
            # 3. Present on GitHub?
            github_match = False
            if github_data:
                repos = github_data.get("repositories", [])
                for repo in repos:
                    langs = [l.lower() for l in repo.get("languages", [])]
                    if skill_lower in langs or skill_lower in repo.get("description", "").lower():
                        github_match = True
                        break

            # 4. Experience Years
            years_used = 0.0
            for job in experience:
                if skill_lower in job.get("description", "").lower() or skill_lower in job.get("title", "").lower():
                    years_used += 1.5  # assume 1.5 years per job mentioning it

            # --- Proficiency Estimation (1 to 5 Stars) ---
            proficiency = 2  # base rating
            reasons = []
            
            if freq >= 3:
                proficiency += 1
                reasons.append("Frequently referenced in resume profile")
            if proj_match:
                proficiency += 1
                reasons.append("Applied in hands-on projects")
            if years_used >= 3.0 or total_exp_years >= 5.0:
                proficiency += 1
                reasons.append(f"Supported by {years_used or total_exp_years} years of work history")
            elif github_match:
                proficiency += 1
                reasons.append("Active repositories using this skill found on GitHub")
                
            proficiency = min(5, max(1, proficiency))

            # --- Confidence Estimation (0.0 to 1.0) ---
            confidence = 0.60  # base confidence
            if proj_match:
                confidence += 0.15
            if github_match:
                confidence += 0.15
            if years_used >= 3.0:
                confidence += 0.10
            
            confidence = round(min(0.98, confidence), 2)
            
            if not reasons:
                reasons.append("Listed as candidate core capability")

            analysis[skill] = {
                "domain": domain,
                "proficiency": proficiency,
                "confidence": confidence,
                "reasons": reasons
            }

        return analysis
