from typing import List, Dict, Any

class AnalyticsEngine:
    """Computes global analytics across the candidate talent pool for dashboard visualizations."""

    def __init__(self):
        pass

    def compile(self, raw_count: int, merged_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate stats from the pool of merged candidates."""
        merged_count = len(merged_candidates)
        duplicates = max(0, raw_count - merged_count)

        # Calculate Average Confidence — prefer the top-level overall_confidence (0-100),
        # fall back to the nested confidence.score for backwards compat.
        avg_confidence = 0.0
        if merged_count > 0:
            def _conf(c):
                oc = c.get("overall_confidence")
                if oc is not None:
                    return float(oc)
                return float(c.get("confidence", {}).get("score", 0.0))
            total_conf = sum(_conf(c) for c in merged_candidates)
            avg_confidence = total_conf / merged_count

        # Top Skills — deduplicate by title-case so "aws" and "AWS" merge
        skill_counts: Dict[str, int] = {}
        for c in merged_candidates:
            seen_this_cand: set = set()
            for skill in c.get("skills", []):
                if isinstance(skill, str) and skill.strip():
                    key = skill.strip().title()
                    if key not in seen_this_cand:   # count each skill once per candidate
                        skill_counts[key] = skill_counts.get(key, 0) + 1
                        seen_this_cand.add(key)

        sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
        top_skills = [{"skill": s, "count": count} for s, count in sorted_skills[:10]]

        # Top Companies — title-case deduplication
        company_counts: Dict[str, int] = {}
        for c in merged_candidates:
            for job in c.get("experience", []):
                company = job.get("company", "")
                if isinstance(company, str) and company.strip():
                    key = company.strip().title()
                    company_counts[key] = company_counts.get(key, 0) + 1

        sorted_companies = sorted(company_counts.items(), key=lambda x: x[1], reverse=True)
        top_companies = [{"company": comp, "count": count} for comp, count in sorted_companies[:10]]

        return {
            "processed": raw_count,
            "candidates_count": merged_count,
            "duplicates": duplicates,
            "average_confidence": round(avg_confidence, 1),
            "top_skills": top_skills,
            "top_companies": top_companies
        }
