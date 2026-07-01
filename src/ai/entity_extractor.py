import re
from typing import Dict, List, Any, Tuple

class EntityExtractor:
    """Extracts nested entities (work history, education, projects) from text, compiles timelines, and flags gaps."""

    def __init__(self):
        # Section keywords
        self.exp_headers = [r"\bexperience\b", r"\bwork history\b", r"\bemployment\b", r"\bcareer\b"]
        self.edu_headers = [r"\beducation\b", r"\bacademics\b", r"\bacademic history\b"]
        self.proj_headers = [r"\bprojects\b", r"\bkey projects\b", r"\bportfolio\b"]

    def _get_sections(self, text: str) -> Dict[str, str]:
        """Split the text into major sections using ResumeParser._chunk_sections."""
        from src.ai.resume_parser import ResumeParser
        return ResumeParser._chunk_sections(text)

    def extract_experience(self, text: str) -> List[Dict[str, Any]]:
        """Parse work history entries from text using ResumeParser."""
        sec_text = self._get_sections(text).get("experience", "")
        if not sec_text.strip():
            return []

        from src.ai.resume_parser import ResumeParser
        return ResumeParser.parse_experience(sec_text, default_employment_type="Full-Time")

    def extract_internships(self, text: str) -> List[Dict[str, Any]]:
        """Parse internships from text using ResumeParser."""
        sec_text = self._get_sections(text).get("internships", "")
        if not sec_text.strip():
            return []

        from src.ai.resume_parser import ResumeParser
        return ResumeParser.parse_experience(sec_text, default_employment_type="Internship")

    def extract_education(self, text: str) -> List[Dict[str, Any]]:
        """Parse education entries from text."""
        sec_text = self._get_sections(text).get("education", "")
        if not sec_text.strip():
            return []

        from src.ai.resume_parser import ResumeParser
        return ResumeParser.parse_education(sec_text)

    def extract_projects(self, text: str) -> List[Dict[str, Any]]:
        """Parse projects from text."""
        sec_text = self._get_sections(text)["projects"]
        if not sec_text.strip():
            return []

        projects = []
        lines = [l.strip() for l in sec_text.split("\n") if l.strip()]
        
        # Simple splitting: every bullet point or header line can be a project
        current_project = {}
        for line in lines:
            if line.startswith("•") or line.startswith("-") or line.startswith("*"):
                desc = line.strip("•-* ")
                if current_project:
                    current_project["description"] = current_project.get("description", "") + " " + desc
                else:
                    current_project = {"name": desc[:30], "description": desc, "technologies": []}
            else:
                if current_project:
                    projects.append(current_project)
                current_project = {"name": line, "description": "", "technologies": []}
                # Check for tech in parentheses or after colon
                tech_match = re.search(r"\((.*?)\)", line)
                if tech_match:
                    current_project["technologies"] = [t.strip() for t in tech_match.group(1).split(",")]

        if current_project:
            projects.append(current_project)

        # Post-process: extract tech tags from description
        common_tech = ["python", "react", "aws", "docker", "kubernetes", "redis", "postgresql", "mysql", "mongodb", "pytorch", "tensorflow", "langchain", "crewai"]
        for proj in projects:
            desc_lower = proj["description"].lower()
            found_tech = proj.get("technologies", [])
            for tech in common_tech:
                if tech in desc_lower and tech not in [t.lower() for t in found_tech]:
                    found_tech.append(tech.title())
            proj["technologies"] = found_tech

        return projects

    def build_timeline(self, experience: List[Dict[str, Any]], education: List[Dict[str, Any]], internships: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Construct chronological career timeline listing years, titles, and companies."""
        events = []
        
        # 1. Add Education events
        for edu in education:
            year_str = edu.get("start_date") or edu.get("end_date") or ""
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", str(year_str))
            end_str = edu.get("end_date") or ""
            end_match = re.search(r"\b(19\d{2}|20\d{2})\b", str(end_str))
            
            if year_match:
                start_yr = int(year_match.group(1))
                end_yr = int(end_match.group(1)) if end_match else start_yr + 4
                events.append({
                    "year": start_yr,
                    "end_year": end_yr,
                    "title": edu.get("degree") or "Student",
                    "company": edu.get("institution") or "University",
                    "type": "education"
                })
                
        # 2. Add Experience events
        import datetime
        current_year = datetime.datetime.now().year
        for exp in experience:
            year_str = exp.get("start_date") or exp.get("start") or ""
            end_year_str = exp.get("end_date") or exp.get("end") or ""
            
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", str(year_str))
            end_match = re.search(r"\b(19\d{2}|20\d{2})\b", str(end_year_str))
            
            if year_match:
                start_yr = int(year_match.group(1))
                if end_match:
                    end_yr = int(end_match.group(1))
                elif "present" in str(end_year_str).lower() or "current" in str(end_year_str).lower():
                    end_yr = current_year
                else:
                    end_yr = start_yr + 1
                    
                events.append({
                    "year": start_yr,
                    "end_year": end_yr,
                    "title": exp.get("title") or "Software Engineer",
                    "company": exp.get("company") or "Tech Company",
                    "type": "work"
                })

        # 3. Add Internship events
        if internships:
            for intern in internships:
                year_str = intern.get("start_date") or intern.get("start") or ""
                end_year_str = intern.get("end_date") or intern.get("end") or ""
                
                year_match = re.search(r"\b(19\d{2}|20\d{2})\b", str(year_str))
                end_match = re.search(r"\b(19\d{2}|20\d{2})\b", str(end_year_str))
                
                if year_match:
                    start_yr = int(year_match.group(1))
                    if end_match:
                        end_yr = int(end_match.group(1))
                    elif "present" in str(end_year_str).lower() or "current" in str(end_year_str).lower():
                        end_yr = current_year
                    else:
                        end_yr = start_yr + 1
                        
                    events.append({
                        "year": start_yr,
                        "end_year": end_yr,
                        "title": intern.get("title") or "Intern",
                        "company": intern.get("company") or "Tech Company",
                        "type": "work"
                    })

        # Sort timeline chronologically (by year ascending)
        events.sort(key=lambda x: x["year"])
        return events

    def detect_gaps(self, timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify years where there is no education/work history listed."""
        work_events = [e for e in timeline if e["type"] == "work"]
        if len(work_events) < 2:
            return []

        gaps = []
        for i in range(len(work_events) - 1):
            curr_event = work_events[i]
            next_event = work_events[i + 1]
            
            curr_end = curr_event.get("end_year", curr_event["year"] + 1)
            next_start = next_event["year"]
            
            if next_start - curr_end > 1:
                gap_len = next_start - curr_end
                gaps.append({
                    "start_year": curr_end,
                    "end_year": next_start,
                    "duration_years": gap_len,
                    "description": f"Employment Gap: {gap_len} years between {curr_event['company']} and {next_event['company']}"
                })
        return gaps

    def extract_all(self, text: str) -> Dict[str, Any]:
        """Run all extractions on the raw text and return structured dictionaries."""
        exp = self.extract_experience(text)
        edu = self.extract_education(text)
        proj = self.extract_projects(text)
        internships = self.extract_internships(text)
        timeline = self.build_timeline(exp, edu, internships)
        gaps = self.detect_gaps(timeline)
        
        return {
            "experience": exp,
            "education": edu,
            "projects": proj,
            "internships": internships,
            "timeline": timeline,
            "gap_detection": gaps
        }
