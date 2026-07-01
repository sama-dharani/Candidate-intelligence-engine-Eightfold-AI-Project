import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import re

class ConfidenceEngine:
    """Dynamic confidence engine that scores fields, skills, and overall profiles."""

    def __init__(self, weights_path: Optional[str | Path] = None):
        # Base reliability of different sources
        self.source_trust = {
            "linkedin": 0.95,
            "github": 0.95,
            "ats": 0.90,
            "resume": 0.85,
            "recruiter_notes": 0.80,
            "csv": 0.75,
            "unknown": 0.50
        }
        
    def _compute_field_confidence(self, field: str, candidate: Dict[str, Any], reasons: List[str]) -> float:
        # Check provenance
        field_prov_raw = candidate.get("field_provenance", {}).get(field, [])
        if not field_prov_raw:
            return 0.0
            
        # If it's a dict (e.g. {"a@b.com": ["csv"]}), collect unique sources from its values
        if isinstance(field_prov_raw, dict):
            field_prov = []
            for src_list in field_prov_raw.values():
                if isinstance(src_list, list):
                    field_prov.extend(src_list)
            field_prov = list(set(field_prov))
        else:
            field_prov = field_prov_raw
            
        if not field_prov:
            return 50.0
            
        # Get base trust from best source
        base_trust = max((self.source_trust.get(str(src).lower(), 0.50) for src in field_prov), default=0.50)
        
        # Agreement bonus
        agreement_bonus = 0.0
        if len(field_prov) > 1:
            agreement_bonus = min(0.15, (len(field_prov) - 1) * 0.05)
            
        # Conflict penalty
        conflict_penalty = 0.0
        conflicts = [c for c in candidate.get("conflict_log", []) if c.get("field") == field]
        if conflicts:
            conflict_penalty = 0.10
            
        final_conf = min(1.0, max(0.1, base_trust + agreement_bonus - conflict_penalty))
        return round(final_conf * 100, 1)

    def compute(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Compute score dynamically based on data quality and source reliability."""
        reasons: List[str] = []
        missing_fields: List[str] = []
        
        import datetime
        current_year = datetime.datetime.now().year
        
        def _get_years(entries):
            y = 0.0
            for entry in entries:
                start_str = str(entry.get("start_date") or entry.get("start") or "")
                end_str = str(entry.get("end_date") or entry.get("end") or "")
                start_match = re.search(r"\b(19\d{2}|20\d{2})\b", start_str)
                end_match = re.search(r"\b(19\d{2}|20\d{2})\b", end_str)
                s_yr = int(start_match.group(1)) if start_match else None
                if end_match:
                    e_yr = int(end_match.group(1))
                elif "present" in end_str.lower() or "current" in end_str.lower():
                    e_yr = current_year
                else:
                    e_yr = None
                
                if s_yr and e_yr:
                    y += max(0.25, e_yr - s_yr)
            return round(y, 1)
            
        prof_exp = candidate.get("experience", [])
        internship_exp = candidate.get("internships", [])
        
        total_prof_years = _get_years(prof_exp)
        total_intern_years = _get_years(internship_exp)
        
        candidate["total_professional_experience"] = total_prof_years
        candidate["total_internship_experience"] = total_intern_years
        candidate["overall_industry_experience"] = round(total_prof_years + total_intern_years, 1)
        candidate["experience_years"] = candidate["overall_industry_experience"]

        # Calculate dynamic profile completeness (0-100)
        comp_fields = [
            "full_name",
            "emails",
            "phones",
            "location",
            "skills",
            "experience",
            "internships",
            "education",
            "projects",
            "certifications",
            "github",
            "linkedin"
        ]
        
        populated_count = 0
        for f in comp_fields:
            val = candidate.get(f)
            is_populated = False
            if f == "experience" or f == "internships":
                is_populated = (val and len(val) > 0)
            else:
                is_populated = val and (not isinstance(val, (list, dict)) or len(val) > 0)
            
            if is_populated:
                populated_count += 1
                
        completeness_pct = round((populated_count / len(comp_fields)) * 100, 1)
        candidate["profile_completeness"] = completeness_pct
        
        # 1. Profile Completeness (max 25 points)
        completeness_weights = {
            "full_name": 3.0,
            "emails": 3.0,
            "phones": 3.0,
            "location": 2.0,
            "skills": 3.0,
            "education": 3.0,
            "projects": 2.0,
            "certifications": 1.0,
            "github": 1.0,
            "linkedin": 1.0
        }
        
        completeness_score = 0.0
        for f, weight in completeness_weights.items():
            val = candidate.get(f)
            is_present = val and (not isinstance(val, (list, dict)) or len(val) > 0)
            if is_present:
                completeness_score += weight
            else:
                missing_fields.append(f)
                
        # Experience / Internship completeness segment (3.0 max)
        has_exp = bool(candidate.get("experience") and len(candidate.get("experience")) > 0)
        has_int = bool(candidate.get("internships") and len(candidate.get("internships")) > 0)
        if has_exp or has_int:
            completeness_score += 3.0
        else:
            missing_fields.append("experience")
                
        # 2. Source Trust Score (max 25 points)
        sources = list(set(str(p.get("source_type", "unknown")).lower() for p in candidate.get("provenance", [])))
        if sources:
            avg_source_trust = sum(self.source_trust.get(s, 0.50) for s in sources) / len(sources)
            source_score = round(avg_source_trust * 25, 1)
        else:
            source_score = 0.0
            
        # 3. Normalization Success Score (max 15 points)
        normalization_score = 15.0
        if completeness_score == 0.0:
            normalization_score = 0.0
        # Phone Validation Check
        phones = candidate.get("phones", [])
        for p in phones:
            p_clean = re.sub(r"[^\d\+]", "", p)
            if not p_clean.startswith("+") and len(p_clean) >= 10:
                # missing international prefix but cleaned
                pass
            elif p_clean.startswith("+") and (10 <= len(p_clean) <= 16):
                # correct E.164
                pass
            else:
                normalization_score -= 3.0
                reasons.append(f"⚠ Phone number '{p}' is not strictly formatted to E.164")
                
        # Email Validation Check
        emails = candidate.get("emails", [])
        email_re = re.compile(r"^[a-z0-9\._\-]+@[a-z0-9\._\-]+\.[a-z]{2,4}$")
        for e in emails:
            if not email_re.match(e):
                normalization_score -= 3.0
                reasons.append(f"⚠ Email '{e}' failed lowercase/syntax check")
                
        # Name Validation Check
        name = candidate.get("full_name", "")
        if name and name.isupper():
            normalization_score -= 2.0
            reasons.append("⚠ Candidate name is in ALL CAPS")
            
        normalization_score = max(0.0, normalization_score)
        
        # 4. Cross-Source Agreement Score (max 15 points)
        agreement_score = 0.0
        field_prov_map = candidate.get("field_provenance", {})
        for f, sources_list in field_prov_map.items():
            if isinstance(sources_list, dict):
                # Nested structures like emails/phones
                for val, src_list in sources_list.items():
                    if isinstance(src_list, list) and len(src_list) > 1:
                        agreement_score += 2.0
            elif isinstance(sources_list, list) and len(sources_list) > 1:
                agreement_score += 2.0
        agreement_score = min(15.0, agreement_score)
        
        # 5. Validation Score (max 20 points)
        validation_score = 20.0
        # Check validator warnings/errors
        val_errors = candidate.get("_errors", [])
        if val_errors:
            validation_score = max(0.0, 20.0 - (len(val_errors) * 4.0))
            for err in val_errors[:2]:
                reasons.append(f"⚠ JSON schema validation error: {err}")
                
        if not candidate.get("full_name"):
            validation_score = max(0.0, validation_score - 10.0)
            reasons.append("✖ Required field 'full_name' is missing")
            
        # Calculate overall score out of 100
        overall = completeness_score + source_score + normalization_score + agreement_score + validation_score
        overall = max(0.0, min(100.0, overall))
        
        # Build individual field scores
        fields = {}
        for key in completeness_weights.keys():
            if candidate.get(key):
                fields[key] = self._compute_field_confidence(key, candidate, reasons)
                
        # Skill confidence
        skills = {}
        skill_list = candidate.get("skills", [])
        if skill_list:
            raw_text = candidate.get("_raw_text", "").lower()
            for skill in skill_list:
                base = self.source_trust.get("resume", 0.85)
                mentions = raw_text.count(skill.lower())
                bonus = min(0.15, mentions * 0.02)
                skills[skill] = round(min(1.0, base + bonus) * 100, 1)

        # Generate reasons
        reasons.append(f"Profile completeness: {round(completeness_score, 1)}/25")
        reasons.append(f"Source verification score: {round(source_score, 1)}/25")
        reasons.append(f"Data normalization success: {round(normalization_score, 1)}/15")
        if agreement_score > 0:
            reasons.append(f"Cross-source agreement bonus: +{round(agreement_score, 1)}")
        if missing_fields:
            reasons.append(f"Missing attributes: {', '.join(missing_fields[:3])}")
            
        # Store properties directly on the candidate root as requested
        candidate["overall_confidence"] = round(overall, 1)
        candidate["confidence_breakdown"] = {
            "completeness_score": round(completeness_score, 1),
            "source_score": round(source_score, 1),
            "normalization_score": round(normalization_score, 1),
            "agreement_score": round(agreement_score, 1),
            "validation_score": round(validation_score, 1)
        }
        candidate["reasons"] = reasons
        candidate["missing_fields"] = missing_fields
        candidate["normalization_score"] = round(normalization_score, 1)
        candidate["source_score"] = round(source_score, 1)
        candidate["validation_score"] = round(validation_score, 1)

        return {
            "score": round(overall, 1),
            "reasons": reasons,
            "fields": fields,
            "skills": skills,
            "confidence_breakdown": candidate["confidence_breakdown"],
            "missing_fields": missing_fields,
            "normalization_score": candidate["normalization_score"],
            "source_score": candidate["source_score"],
            "validation_score": candidate["validation_score"]
        }
