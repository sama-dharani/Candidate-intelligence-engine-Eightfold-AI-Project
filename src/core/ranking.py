import re
from typing import Dict, List, Any, Optional
import difflib

class RankingEngine:
    """Ranks candidate profiles against queries containing required skills, experience, and location."""

    def __init__(self):
        pass

    @staticmethod
    def _calculate_total_experience_years(experience: List[Dict[str, Any]]) -> float:
        """Estimate total years of experience from candidates' work history list."""
        if not experience:
            return 0.0
        
        total_years = 0.0
        for job in experience:
            start_str = str(job.get("start_date", ""))
            end_str = str(job.get("end_date", ""))
            
            # Extract years using regex
            start_years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", start_str)]
            end_years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", end_str)]
            
            start_y = start_years[0] if start_years else None
            end_y = end_years[0] if end_years else None
            
            # Handle current/present jobs
            if not end_y and ("present" in end_str.lower() or "current" in end_str.lower() or not end_str):
                end_y = 2026  # default current year
                
            if start_y and end_y:
                duration = max(0.5, end_y - start_y)
                total_years += duration
            else:
                # Fallback: assume 1 year per listed experience if dates cannot be parsed
                total_years += 1.0
                
        return round(total_years, 1)

    def rank_candidates(self, candidates: List[Dict[str, Any]], query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Rank a list of candidates against the query dictionary.
        
        Query keys:
        - skills: List[str] (required skills)
        - min_experience_years: float (minimum years of experience)
        - location: str (preferred city/location)
        
        Returns:
          A list of candidates enriched with:
          - '_rank_score': matching percentage (0 to 100)
          - '_rank_reasons': matching details
        """
        ranked = []
        required_skills = [s.lower().strip() for s in query.get("skills", []) if isinstance(s, str)]
        min_exp = float(query.get("min_experience_years", 0))
        pref_location = str(query.get("location", "")).lower().strip()

        for cand in candidates:
            # 1. Skills Match Score (Weight: 40%)
            skill_score = 0.0
            matched_skills = []
            cand_skills = [s.lower().strip() for s in cand.get("skills", []) if isinstance(s, str)]
            
            if required_skills:
                matches = 0
                for req in required_skills:
                    if req in cand_skills:
                        matches += 1
                        matched_skills.append(req)
                    else:
                        # Fuzzy matches or substring matches (safe length check to prevent single-letter false positives)
                        fuzzy_match = False
                        for cs in cand_skills:
                            if (len(req) >= 4 and len(cs) >= 4 and (req in cs or cs in req)) or difflib.SequenceMatcher(None, req, cs).ratio() > 0.8:
                                fuzzy_match = True
                                matched_skills.append(cs)
                                break
                        if fuzzy_match:
                            matches += 1
                skill_score = matches / len(required_skills)
            else:
                # If no skills are requested, candidate gets full points
                skill_score = 1.0

            # 2. Experience Match Score (Weight: 30%)
            exp_years = cand.get("experience_years") or (
                self._calculate_total_experience_years(cand.get("experience", [])) +
                self._calculate_total_experience_years(cand.get("internships", []))
            )
            exp_score = 1.0
            if min_exp > 0:
                exp_score = min(1.0, exp_years / min_exp)

            # 3. Location Match Score (Weight: 20%)
            loc_score = 0.0
            cand_location = str(cand.get("location", "")).lower().strip()
            if not pref_location:
                loc_score = 1.0
            elif pref_location in cand_location or cand_location in pref_location:
                loc_score = 1.0
            elif cand_location:
                # Fuzzy location comparison
                ratio = difflib.SequenceMatcher(None, pref_location, cand_location).ratio()
                loc_score = ratio if ratio > 0.6 else 0.0

            # 4. Profile Confidence Score (Weight: 10%)
            raw_conf = cand.get("confidence", {}).get("score", 0.0)
            conf_score = raw_conf / 100.0 if raw_conf > 1.0 else raw_conf

            # Final Score Calculation
            final_score = (
                skill_score * 0.40 +
                exp_score * 0.30 +
                loc_score * 0.20 +
                conf_score * 0.10
            )

            # Build explainable reasons
            reasons = []
            if required_skills:
                reasons.append(f"Matched {len(matched_skills)}/{len(required_skills)} skills: {', '.join(matched_skills)}")
            reasons.append(f"Has {exp_years} yrs of experience (Target: {min_exp} yrs)")
            if pref_location:
                if loc_score == 1.0:
                    reasons.append(f"Location match: {cand.get('location')}")
                elif loc_score > 0:
                    reasons.append(f"Fuzzy location match: {cand.get('location')}")
                else:
                    reasons.append(f"Location mismatch: Candidate is in {cand.get('location') or 'unknown'}")
            reasons.append(f"Profile Confidence: {int(conf_score * 100)}%")

            # Create copy and enrich
            cand_ranked = dict(cand)
            cand_ranked["_rank_score"] = int(final_score * 100)
            cand_ranked["_rank_reasons"] = reasons
            ranked.append(cand_ranked)

        # Sort by rank score descending, then experience descending, then confidence descending
        ranked.sort(key=lambda x: (x["_rank_score"], x.get("confidence", {}).get("score", 0.0)), reverse=True)
        return ranked
