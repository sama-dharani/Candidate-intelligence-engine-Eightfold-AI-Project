from typing import List, Dict, Any

class AnalyticsEngine:
    """Computes global analytics across the candidate talent pool for dashboard visualizations."""

    def __init__(self):
        pass

    def compile(self, raw_count: int, merged_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate stats from the pool of merged candidates."""
        merged_count = len(merged_candidates)
        duplicates = max(0, raw_count - merged_count)
        
        # Calculate Average Confidence
        avg_confidence = 0.0
        if merged_count > 0:
            total_conf = sum(c.get("confidence", {}).get("score", 0.0) for c in merged_candidates)
            avg_confidence = total_conf / merged_count
            
        # Top Skills
        skill_counts = {}
        for c in merged_candidates:
            for skill in c.get("skills", []):
                if isinstance(skill, str) and skill.strip():
                    name = skill.strip()
                    # Clean title casing for aggregations
                    key = name.title()
                    skill_counts[key] = skill_counts.get(key, 0) + 1
                    
        sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
        top_skills = [{"skill": s, "count": count} for s, count in sorted_skills[:10]]

        # Top Companies
        company_counts = {}
        for c in merged_candidates:
            for job in c.get("experience", []):
                company = job.get("company", "")
                if isinstance(company, str) and company.strip():
                    name = company.strip()
                    key = name.title()
                    company_counts[key] = company_counts.get(key, 0) + 1
                    
        sorted_companies = sorted(company_counts.items(), key=lambda x: x[1], reverse=True)
        top_companies = [{"company": comp, "count": count} for comp, count in sorted_companies[:10]]

        return {
            "processed": raw_count,
            "candidates_count": merged_count,
            "duplicates": duplicates,
            "average_confidence": round(avg_confidence * 100, 1),
            "top_skills": top_skills,
            "top_companies": top_companies
        }
