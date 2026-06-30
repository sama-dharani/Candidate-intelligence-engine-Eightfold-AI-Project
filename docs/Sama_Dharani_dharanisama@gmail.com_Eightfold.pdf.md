# Eightfold AI Candidate Intelligence Platform - Technical Design

## 1. Problem Statement
The candidate intelligence platform solves the challenge of fractured applicant data by ingesting multiple structured (CSV, ATS) and unstructured (Resumes, GitHub, LinkedIn) sources. It deterministically transforms, normalizes, and merges these disparate inputs into a single, highly reliable canonical candidate profile while maintaining strict data provenance and assigning confidence scores.

## 2. Processing Pipeline
Detect Source
↓
Extract Text/Keys
↓
Parse (Spacy/PDFMiner)
↓
Canonical Mapping
↓
Normalize (Dates/Phones)
↓
Candidate Matching
↓
Duplicate Detection
↓
Merge
↓
Conflict Resolution
↓
Confidence Calculation
↓
Provenance Tracking
↓
Runtime Projection
↓
Schema Validation
↓
Final JSON Output

## 3. Canonical Candidate Schema
The canonical schema is the single source of truth for a candidate. 
* **Fields:** `candidate_id`, `full_name`, `emails`, `phones`, `location`, `links`, `headline`, `experience`, `education`, `skills`, `provenance`, `overall_confidence`.
* **Normalization:** Phones map to E.164. Dates map to YYYY-MM. Country maps to ISO-3166 Alpha-2. Skills map to a canonical taxonomy dictionary.

## 4. Merge & Conflict Resolution Strategy
* **Duplicate Detection:** Exact string match on `emails` or Jaro-Winkler fuzzy match on `full_name` (>0.85 threshold).
* **Source Priority:** Recruiter CSV > ATS > LinkedIn > Resume > GitHub.
* **Merge Rules / Conflict Resolution:** Primitive fields (location, headline) resolve to the highest priority source or newest timestamp. Array fields (experience, skills) are deduplicated via set unions using exact title/company matching.
* **Confidence Assignment:** Adds points for corroborating sources (+10), subtracts points for missing critical fields like email (-20).
* **Provenance Preservation:** Every field value maps to a `field_provenance` dictionary (e.g., `"phones": ["ats.json", "resume.pdf"]`).

## 5. Runtime Configurable Output
* **Field Selection & Projection:** Uses `projection_rules.json` to define dynamic views. For example, a `public` view strips PII (emails, phones) before JSON serialization.
* **Missing Value Policy:** Unresolved or missing values default to `null` to ensure strict schema enforcement without failing validation.
* **Schema Validation:** The final projected dictionary is strictly validated against `canonical_candidate.json` using `jsonschema`.

## 6. Edge Cases
* **Missing Email:** Confidence score is heavily penalized (-20). Fuzzy name matching takes over duplicate detection.
* **Conflicting Phone:** The merge engine falls back to the source priority ranking, taking the phone number from the most trusted source.
* **Malformed Resume:** Regex and Spacy NLP gracefully skip unparseable blocks, returning partial data which is penalized via confidence scoring.
* **Duplicate Candidate:** Handled by the resolver. The two records are collapsed, their arrays combined via union, and provenance updated.

## 7. Scope Left Out
* True database persistence (SQLite/PostgreSQL) is omitted; the pipeline runs entirely in-memory for the assignment scope.
* Real-world LLM integration (OpenAI/Anthropic) for unstructured parsing is omitted in favor of deterministic `spacy` NLP models.
* End-to-end UI testing (Cypress) is not implemented.
