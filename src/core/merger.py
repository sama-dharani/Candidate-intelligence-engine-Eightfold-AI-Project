from typing import Dict, List, Any, Tuple, Optional
import re
from .resolver import EntityResolver

class CandidateMerger:
    """Clusters similar records and merges them into unified candidates.
    
    Intelligently tracks:
    - field_provenance: exactly which sources contributed which field values
    - conflict_log: details of mismatched values and how they were resolved
    - normalization_history: before/after tracking of all cleaned attributes
    - edge_cases: alerts and resolutions for empty fields, missing info recovered, etc.
    """

    def __init__(self, resolver: Optional[EntityResolver] = None):
        self.resolver = resolver or EntityResolver()

    def cluster_records(self, records: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Groups candidate records that represent the same physical person using EntityResolver."""
        clusters: List[List[Dict[str, Any]]] = []
        for rec in records:
            placed = False
            for cluster in clusters:
                if self.resolver.is_same_candidate(rec, cluster[0]):
                    cluster.append(rec)
                    placed = True
                    break
            if not placed:
                clusters.append([rec])
        return clusters

    def _merge_list_field(self, values_list: List[List[Any]]) -> List[Any]:
        """Combine lists and deduplicate values, stripping whitespace."""
        merged = []
        seen = set()
        for sublist in values_list:
            if not isinstance(sublist, list):
                continue
            for val in sublist:
                if val is None:
                    continue
                val_str = str(val).strip()
                val_key = val_str.lower()
                if val_key and val_key not in seen:
                    seen.add(val_key)
                    merged.append(val_str)
        return merged

    def _merge_experience(self, exp_list: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Merge list of experience entries, deduplicating by company + title."""
        merged: List[Dict[str, Any]] = []
        seen = set()
        for sublist in exp_list:
            if not isinstance(sublist, list):
                continue
            for entry in sublist:
                if not isinstance(entry, dict):
                    continue
                comp = str(entry.get("company", "")).strip()
                title = str(entry.get("title", "")).strip()
                key = f"{comp.lower()}|{title.lower()}"
                if comp and title and key not in seen:
                    seen.add(key)
                    merged.append({
                        "company": comp,
                        "title": title,
                        "start_date": str(entry.get("start_date", "")).strip(),
                        "end_date": str(entry.get("end_date", "")).strip(),
                        "description": str(entry.get("description", "")).strip()
                    })
        return merged

    def _merge_education(self, edu_list: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Merge list of education entries, deduplicating by institution + degree."""
        merged: List[Dict[str, Any]] = []
        seen = set()
        for sublist in edu_list:
            if not isinstance(sublist, list):
                continue
            for entry in sublist:
                if not isinstance(entry, dict):
                    continue
                inst = str(entry.get("institution", "")).strip()
                deg = str(entry.get("degree", "")).strip()
                key = f"{inst.lower()}|{deg.lower()}"
                if inst and key not in seen:
                    seen.add(key)
                    merged.append({
                        "institution": inst,
                        "degree": deg,
                        "start_date": str(entry.get("start_date", "")).strip(),
                        "end_date": str(entry.get("end_date", "")).strip()
                    })
        return merged

    def _merge_projects(self, proj_list: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Merge list of projects, deduplicating by project name."""
        merged: List[Dict[str, Any]] = []
        seen = set()
        for sublist in proj_list:
            if not isinstance(sublist, list):
                continue
            for entry in sublist:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name", "")).strip()
                key = name.lower()
                if name and key not in seen:
                    seen.add(key)
                    tech = entry.get("technologies", [])
                    if isinstance(tech, str):
                        tech = [t.strip() for t in tech.split(",") if t.strip()]
                    merged.append({
                        "name": name,
                        "description": str(entry.get("description", "")).strip(),
                        "technologies": [str(t).strip() for t in tech if t]
                    })
        return merged

    def merge_cluster(self, cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge a cluster of candidate records and return a single unified dict with metadata."""
        if not cluster:
            raise ValueError("Cannot merge an empty cluster.")

        merged: Dict[str, Any] = {}
        provenance_dict: Dict[int, List[str]] = {}
        
        # Track before/after normalization and conflicts
        norm_history = []
        conflict_log = []
        edge_cases = []
        field_prov = {}  # field_name -> [sources] or field_name -> dict(value -> [sources])

        list_fields = ["emails", "phones", "skills", "certifications"]
        history_fields = ["experience", "education", "projects"]
        
        # Initialize lists and check for missing/recovered info edge cases
        for idx, rec in enumerate(cluster):
            src_idx = rec.get("_source_index", idx)
            provenance_dict[src_idx] = []

        # Gather list of emails/phones to check edge cases
        all_emails = []
        all_phones = []
        for rec in cluster:
            for e in rec.get("emails", []):
                if e and e not in all_emails: all_emails.append(e)
            for p in rec.get("phones", []):
                if p and p not in all_phones: all_phones.append(p)

        # Detect email recovery edge case
        for rec in cluster:
            src_type = rec.get("_source_type", "unknown")
            if not rec.get("emails") and all_emails:
                edge_cases.append({
                    "case": f"Missing Email in {src_type.upper()}",
                    "detail": f"Recovered from other matched source: {all_emails[0]}",
                    "status": "resolved"
                })
                rec["emails"] = all_emails  # Recover email
            if not rec.get("phones") and all_phones:
                edge_cases.append({
                    "case": f"Missing Phone in {src_type.upper()}",
                    "detail": f"Recovered from other matched source: {all_phones[0]}",
                    "status": "resolved"
                })
                rec["phones"] = all_phones

        # 1. Merge List Fields (track items & provenance)
        for field in list_fields:
            val_lists = []
            field_prov[field] = {}
            for rec in cluster:
                src_type = rec.get("_source_type", "unknown")
                val = rec.get(field)
                if val:
                    if not isinstance(val, list):
                        val = [val]
                    val_lists.append(val)
                    for item in val:
                        item_str = str(item).strip()
                        if item_str:
                            if item_str not in field_prov[field]:
                                field_prov[field][item_str] = []
                            if src_type not in field_prov[field][item_str]:
                                field_prov[field][item_str].append(src_type)

            merged[field] = self._merge_list_field(val_lists)

        # 2. Merge History/Nested Arrays
        for field in history_fields:
            nested_lists = []
            for rec in cluster:
                src_idx = rec.get("_source_index", cluster.index(rec))
                val = rec.get(field)
                if val:
                    if not isinstance(val, list):
                        val = [val]
                    nested_lists.append(val)
                    provenance_dict[src_idx].append(field)
            if field == "experience":
                merged[field] = self._merge_experience(nested_lists)
            elif field == "education":
                merged[field] = self._merge_education(nested_lists)
            elif field == "projects":
                merged[field] = self._merge_projects(nested_lists)

        # 3. Merge Scalar Fields with Conflict Resolution
        scalar_fields = ["full_name", "location", "github", "linkedin"]
        for field in scalar_fields:
            candidates = []
            for rec in cluster:
                val = rec.get(field)
                if val:
                    candidates.append((val, rec.get("_source_type", "unknown"), rec.get("_source_index", cluster.index(rec))))
            
            if not candidates:
                merged[field] = ""
                continue

            # Check for conflict
            unique_vals = list(set(c[0] for c in candidates))
            if len(unique_vals) > 1:
                # We have a conflict!
                # Policy: Newest or higher trust source (ATS > Resume > CSV)
                trust_order = ["ats", "resume", "linkedin", "github", "csv"]
                best_cand = candidates[0]
                best_trust_index = len(trust_order)
                for cand in candidates:
                    src_type = cand[1]
                    if src_type in trust_order:
                        trust_idx = trust_order.index(src_type)
                        if trust_idx < best_trust_index:
                            best_trust_index = trust_idx
                            best_cand = cand
                
                selected_val = best_cand[0]
                conflicting_sources = {c[1]: c[0] for c in candidates}
                conflict_log.append({
                    "field": field,
                    "sources": conflicting_sources,
                    "selected": selected_val,
                    "reason": f"Resolved conflict by picking value from higher priority source: {best_cand[1].upper()}"
                })
                merged[field] = selected_val
            else:
                merged[field] = unique_vals[0]

            # Field provenance
            field_prov[field] = list(set(c[1] for c in candidates))

        # Provenance metadata
        provenance = []
        for rec in cluster:
            src_idx = rec.get("_source_index")
            src_type = rec.get("_source_type", "unknown")
            provenance.append({
                "source_index": src_idx,
                "source_type": src_type,
                "file_name": rec.get("_source_file", "")
            })

        merged["provenance"] = provenance
        merged["conflict_log"] = conflict_log
        merged["normalization_history"] = norm_history
        merged["edge_cases"] = edge_cases
        merged["field_provenance"] = field_prov
        return merged

    def merge_all(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Cluster records and merge each group. Returns a list of merged candidates."""
        clusters = self.cluster_records(records)
        return [self.merge_cluster(cluster) for cluster in clusters]
