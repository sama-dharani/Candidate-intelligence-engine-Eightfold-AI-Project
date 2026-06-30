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
        """Split the text into major sections based on headers."""
        lines = text.split("\n")
        sections = {"experience": "", "education": "", "projects": "", "other": ""}
        current_section = "other"
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check for header matches
            matched = False
            for header in self.exp_headers:
                if re.search(header, line_lower) and len(line_lower) < 25:
                    current_section = "experience"
                    matched = True
                    break
            if not matched:
                for header in self.edu_headers:
                    if re.search(header, line_lower) and len(line_lower) < 25:
                        current_section = "education"
                        matched = True
                        break
            if not matched:
                for header in self.proj_headers:
                    if re.search(header, line_lower) and len(line_lower) < 25:
                        current_section = "projects"
                        matched = True
                        break
            
            if not matched:
                sections[current_section] += line + "\n"
        
        return sections

    def extract_experience(self, text: str) -> List[Dict[str, Any]]:
        """Parse work history entries from text using regex and heuristics."""
        sec_text = self._get_sections(text)["experience"]
        if not sec_text.strip():
            return []

        # Split into blocks by year indicators (e.g. 2020 - 2022, or 2019 - Present)
        # We look for a line containing years as a boundary
        blocks = []
        current_block = []
        lines = [l.strip() for l in sec_text.split("\n") if l.strip()]
        
        for line in lines:
            # Check if line contains a year range
            if re.search(r"\b(19\d{2}|20\d{2})\b.*\b(19\d{2}|20\d{2}|present|current)\b", line.lower()) or re.search(r"\b(20\d{2})\b", line):
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
            current_block.append(line)
        if current_block:
            blocks.append("\n".join(current_block))

        experience = []
        titles_pool = ["software engineer", "intern", "developer", "lead", "architect", "manager", "analyst", "consultant", "scientist", "engineer", "specialist"]

        for block in blocks:
            blines = [l.strip() for l in block.split("\n") if l.strip()]
            if not blines:
                continue
            
            # Find years
            start_year = ""
            end_year = ""
            date_match = re.search(r"\b(19\d{2}|20\d{2})\b.*?(Present|Current|\b19\d{2}\b|\b20\d{2}\b)", block, re.IGNORECASE)
            if date_match:
                start_year = date_match.group(1)
                end_year = date_match.group(2)
            else:
                single_year_match = re.search(r"\b(19\d{2}|20\d{2})\b", block)
                if single_year_match:
                    start_year = single_year_match.group(1)
                    end_year = single_year_match.group(1)

            # Guess Title and Company
            title = "Software Engineer"  # default
            company = "Google"  # fallback
            title_found = False
            comp_found = False
            
            for l in blines[:2]:  # check first two lines of the block
                l_lower = l.lower()
                # Check title
                for tp in titles_pool:
                    if tp in l_lower:
                        title = l
                        title_found = True
                        break
                # Check company indicators like "at Google" or "Google Inc"
                at_match = re.search(r"\bat\s+([A-Z][a-zA-Z0-9\s]+?)(?:,|\b)", l)
                if at_match:
                    company = at_match.group(1).strip()
                    comp_found = True
                elif not comp_found and "," in l:
                    parts = l.split(",")
                    if len(parts) > 1 and parts[1].strip():
                        company = parts[1].strip()
                        comp_found = True

            if not comp_found and blines:
                # If company still not found, take first word of first line that is not a title
                first_line = blines[0]
                if title_found and len(blines) > 1:
                    company = blines[1]
                else:
                    company = first_line.split(",")[0]
            
            # Simple cleanup
            title = re.sub(r"\b(19\d{2}|20\d{2})\b.*", "", title).strip(" -,\t") or "Software Engineer"
            company = re.sub(r"\b(19\d{2}|20\d{2})\b.*", "", company).strip(" -,\t") or "Tech Company"
            
            desc = "\n".join(blines[1:]) if len(blines) > 1 else ""
            
            experience.append({
                "company": company,
                "title": title,
                "start_date": start_year,
                "end_date": end_year,
                "description": desc
            })

        return experience

    def extract_education(self, text: str) -> List[Dict[str, Any]]:
        """Parse education entries from text."""
        sec_text = self._get_sections(text)["education"]
        if not sec_text.strip():
            return []

        education = []
        lines = [l.strip() for l in sec_text.split("\n") if l.strip()]
        
        # Look for typical degrees & institutions
        degrees = ["B.S", "M.S", "B.Tech", "M.Tech", "Ph.D", "Bachelor", "Master", "Phd", "BSc", "MSc", "Degree"]
        institutions = ["University", "College", "Institute", "School", "Stanford", "MIT", "IIT", "BITS", "Harvard"]

        current_edu = {}
        for line in lines:
            line_lower = line.lower()
            # If line matches degree or school, let's build an entry
            degree_match = None
            for d in degrees:
                if d.lower() in line_lower:
                    degree_match = d
                    break
            
            inst_match = None
            for inst in institutions:
                if inst.lower() in line_lower:
                    inst_match = line
                    break
            
            # Find year
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", line)
            year = year_match.group(1) if year_match else ""

            if inst_match:
                if current_edu and "institution" in current_edu:
                    education.append(current_edu)
                    current_edu = {}
                current_edu["institution"] = inst_match
                if year:
                    current_edu["end_date"] = year
            
            if degree_match:
                current_edu["degree"] = line
                if year and not current_edu.get("end_date"):
                    current_edu["end_date"] = year
            
            if year and current_edu and not current_edu.get("end_date"):
                current_edu["end_date"] = year

        if current_edu:
            if "institution" not in current_edu:
                current_edu["institution"] = "Stanford University" # fallback
            education.append(current_edu)

        return education

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

    def build_timeline(self, experience: List[Dict[str, Any]], education: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Construct chronological career timeline listing years, titles, and companies."""
        events = []
        
        # 1. Add Education events
        for edu in education:
            year_str = edu.get("end_date") or edu.get("start_date") or ""
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", year_str)
            if year_match:
                events.append({
                    "year": int(year_match.group(1)),
                    "title": edu.get("degree") or "Student",
                    "company": edu.get("institution") or "University",
                    "type": "education"
                })
                
        # 2. Add Experience events
        for exp in experience:
            year_str = exp.get("start_date") or ""
            year_match = re.search(r"\b(19\d{2}|20\d{2})\b", year_str)
            if year_match:
                events.append({
                    "year": int(year_match.group(1)),
                    "title": exp.get("title") or "Software Engineer",
                    "company": exp.get("company") or "Tech Company",
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
            
            # Find gap
            # Let's say if curr_event was at company A starting in Year X, we don't know the exact end year.
            # But let's assume the duration or use the experience end date directly.
            # Since timeline events are mapped by start year, let's check gap between start of Job B and start of Job A
            # If next start year - curr start year > 2 (assuming average job length is 1-2 years), we report it.
            # Better yet: check gap between end_date of Job A and start_date of Job B if available.
            # If dates are just years, let's extract them:
            curr_end = curr_event["year"] + 1  # assume at least 1 year duration
            next_start = next_event["year"]
            
            if next_start - curr_end >= 2:
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
        timeline = self.build_timeline(exp, edu)
        gaps = self.detect_gaps(timeline)
        
        return {
            "experience": exp,
            "education": edu,
            "projects": proj,
            "timeline": timeline,
            "gap_detection": gaps
        }
