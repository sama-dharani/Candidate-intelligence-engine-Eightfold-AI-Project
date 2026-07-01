import json
import re
from pathlib import Path
from typing import Any, List, Optional, Dict

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

try:
    import pycountry
except ImportError:
    pycountry = None

class CanonicalNormalizer:
    """Deterministically normalizes fields and generates a change log."""
    
    @staticmethod
    def _normalize_phone(phone: str, default_region="US") -> str:
        if not phonenumbers:
            return re.sub(r"[^\d\+]", "", phone)
        try:
            parsed = phonenumbers.parse(phone, default_region)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass
        return re.sub(r"[^\d\+]", "", phone)

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        # Heuristic to convert dates to YYYY-MM
        date_str = str(date_str).strip()
        match = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-\/]+(\d{4})", date_str, re.IGNORECASE)
        if match:
            months = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
                      "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
            return f"{match.group(2)}-{months[match.group(1).lower()]}"
        match_year = re.search(r"(\d{4})", date_str)
        if match_year:
            return f"{match_year.group(1)}-01" # Default to January if only year
        return date_str

    @staticmethod
    def _normalize_location(location: str) -> str:
        if not location:
            return ""
        if pycountry:
            # Try fuzzy search
            try:
                matches = pycountry.countries.search_fuzzy(location)
                if matches:
                    return matches[0].alpha_2
            except Exception:
                pass
            # Try strict lookup
            try:
                c = pycountry.countries.lookup(location)
                if c:
                    return c.alpha_2
            except Exception:
                pass
        return str(location).strip().title()

    @staticmethod
    def normalize(record: Dict[str, Any]) -> Dict[str, Any]:
        log = []
        original = dict(record)
        
        # 1. Name
        name = record.get("full_name")
        if isinstance(name, str) and name:
            new_name = name.title()
            if new_name != name:
                log.append({"field": "full_name", "from": name, "to": new_name})
                record["full_name"] = new_name
                
        # 2. Emails
        emails = record.get("emails", [])
        if isinstance(emails, list):
            new_emails = []
            for e in emails:
                if isinstance(e, str):
                    new_e = e.lower().strip()
                    new_emails.append(new_e)
                    if new_e != e:
                        log.append({"field": "emails", "from": e, "to": new_e})
                else:
                    new_emails.append(e)
            record["emails"] = list(set(new_emails))

        # 3. Phones
        phones = record.get("phones", [])
        if isinstance(phones, list):
            new_phones = []
            for p in phones:
                if isinstance(p, str):
                    new_p = CanonicalNormalizer._normalize_phone(p)
                    new_phones.append(new_p)
                    if new_p != p:
                        log.append({"field": "phones", "from": p, "to": new_p})
                else:
                    new_phones.append(p)
            record["phones"] = list(set(new_phones))
            
        # 4. Location
        loc = record.get("location")
        if isinstance(loc, str) and loc:
            new_loc = CanonicalNormalizer._normalize_location(loc)
            if new_loc != loc:
                log.append({"field": "location", "from": loc, "to": new_loc})
                record["location"] = new_loc

        # 5. Experience / Education / Internship Dates
        for nested in ["experience", "education", "internships"]:
            items = record.get(nested, [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        for df in ["start_date", "end_date"]:
                            if df in item and item[df]:
                                d_val = str(item[df])
                                new_d = CanonicalNormalizer._normalize_date(d_val)
                                if new_d != d_val:
                                    log.append({"field": f"{nested}.{df}", "from": d_val, "to": new_d})
                                    item[df] = new_d
                                    
        record["_normalization_log"] = log
        return record


class DynamicFieldMapper:
    """Map heterogeneous source fields to canonical candidate profile attributes."""

    def __init__(self, mapping_path: str | Path):
        mapping_file = Path(mapping_path)
        if not mapping_file.is_file():
            raise FileNotFoundError(f"Mapping file not found: {mapping_file}")
        self.mapping: Dict[str, List[str]] = json.loads(mapping_file.read_text(encoding="utf-8"))

    @staticmethod
    def _clean(text: str) -> str:
        text = text.lower().replace("_", " ").replace("-", " ")
        return re.sub(r"\s+", " ", text).strip()

    def _find_in_row(self, row: Any, canonical: str) -> Optional[Any]:
        aliases = self.mapping.get(canonical, [])
        cleaned_aliases = [self._clean(a) for a in aliases]
        cleaned_aliases.append(self._clean(canonical))
        
        if hasattr(row, "items"):
            for col, value in row.items():
                if self._clean(col) in cleaned_aliases:
                    return value
        return None

    def _recursive_find(self, data: Any, aliases: List[str], canonical: str = "") -> Optional[Any]:
        cleaned_aliases = [self._clean(a) for a in aliases]
        if canonical:
            cleaned_aliases.append(self._clean(canonical))
        if isinstance(data, dict):
            for key, value in data.items():
                if self._clean(key) in cleaned_aliases:
                    return value
                result = self._recursive_find(value, aliases, canonical)
                if result is not None:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._recursive_find(item, aliases, canonical)
                if result is not None:
                    return result
        return None

    def find_value(self, source: Any, canonical: str) -> Optional[Any]:
        flat_result = self._find_in_row(source, canonical)
        if flat_result is not None:
            return flat_result
        aliases = self.mapping.get(canonical, [])
        return self._recursive_find(source, aliases, canonical)

    def get_all(self, source: Any) -> Dict[str, Any]:
        result = {}
        for canonical in self.mapping.keys():
            value = self.find_value(source, canonical)
            if value is not None:
                if canonical in ["emails", "phones", "skills", "certifications"]:
                    if isinstance(value, str):
                        value = [item.strip() for item in re.split(r"[,;\n]", value) if item.strip()]
                    elif not isinstance(value, list):
                        value = [str(value).strip()]
                result[canonical] = value
                
        # Apply deterministic normalization
        return CanonicalNormalizer.normalize(result)
