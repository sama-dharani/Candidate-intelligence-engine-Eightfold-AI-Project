# Project Title

Eightfold AI Candidate Intelligence Platform

---

# Project Overview

**Purpose:** A deterministic candidate transformation pipeline that ingests multiple candidate information sources, normalizes and merges them into a single canonical candidate profile, tracks provenance, calculates confidence scores, and generates configurable JSON output.
**Supported Sources:** Recruiter CSV, ATS JSON, PDF/DOCX Resumes, GitHub Profiles, LinkedIn Profiles.
**Canonical Profile:** Transforms all data into a strictly defined JSON schema.
**Normalization:** E.164 phones, YYYY-MM dates, ISO-3166 Alpha-2 countries, and canonical skills.
**Merge Engine:** Deduplicates arrays and handles primitive field conflicts based on source priority.
**Confidence:** Calculates 0-100 score based on corroborating sources and data completeness.
**Provenance:** Every data field is tracked back to its original source document.
**Runtime Projection:** Configurable views (e.g., PII masking) applied at output time.
**Validation:** Strict enforcement of `canonical_candidate.json` using `jsonschema`.
**Dashboard:** Interactive vanilla JS UI featuring Knowledge Graphs and Side-by-Side Candidate Comparisons.

---

# Features

- Multi-source structured and unstructured candidate ingestion
- Canonical Candidate Profile generation
- Field Normalization
- Exact/Fuzzy Duplicate Detection
- Merge Engine & Priority Conflict Resolution
- Provenance Tracking
- Configurable Confidence Scoring
- Runtime Configurable Output Projections
- Strict Schema Validation
- Interactive Visual Dashboard (Knowledge Graph, Comparison Matrix)

---

# Folder Structure

```text
Eight Fold AI/
│
├── configs/             # Runtime mapping, projection, and weighting rules
├── data/                # Sample input data (CSV, JSON, PDF, and subfolders)
├── docs/                # Architecture and design documentation
├── examples/            # Dashboard source code (Flask + HTML/JS)
├── schemas/             # JSON schemas (canonical_candidate.json)
├── src/                 # Core backend logic (AI, Pipeline, Core, Loaders)
├── tests/               # Pytest suite
├── .github/             # GitHub Actions CI workflow
├── README.md            # Execution and project guide
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container build file
└── docker-compose.yml   # Multi-service local orchestrator
```

---

# Prerequisites

**Python Version:** Python 3.10+ (Recommended Python 3.12 or 3.13)
**Dependencies:** flask, pdfminer.six, jsonschema, spacy, pytest
**Operating System:** Windows, Linux, or macOS
**Package Manager:** pip

---

# Installation

Clone Repository:
```bash
git clone https://github.com/sama-dharani/Candidate-intelligence-engine-Eightfold-AI-Project.git
cd Candidate-intelligence-engine-Eightfold-AI-Project
```

Virtual Environment:
```bash
python -m venv venv
# Activate on Windows:
venv\Scripts\activate
# Activate on Linux/macOS:
source venv/bin/activate
```

Dependency Installation:
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

---

# Input Sources

Place candidate sources inside the appropriate folders:

| Source | Folder |
|----------|----------|
| Recruiter CSV | `data/` |
| ATS JSON | `data/` |
| Resume PDF | `data/` |
| Resume DOCX | `data/` |
| GitHub Profile | `data/github/` |
| LinkedIn Profile | `data/linkedin/` |
| Recruiter Notes | `data/` |

---

# Configuration

- **mapping.json**: Defines source-to-canonical field mapping aliases (e.g., "cell" to "phones").
- **projection_rules.json**: Runtime output configuration (e.g., the `public` view strips out PII emails/phones).
- **weights.json**: Confidence scoring penalty and reward weights (e.g., missing email = -20 points).
- **skills_taxonomy.json**: Canonical skill name normalization dictionary.

---

# Running the Pipeline

The pipeline is automatically triggered when running the dashboard, but you can explicitly run tests to see it execute headless:
```bash
python -m pytest tests/test_pipeline.py -v
```
This executes the core python pipeline, extracting, resolving, mapping, validating, and projecting JSON without a UI.

---

# Running the Dashboard

```bash
python examples/dashboard/app.py
```
Open your browser to:
`http://127.0.0.1:5000`

---

# Running Tests

```bash
python -m pytest tests/test_pipeline.py -v
```

---

# Processing Pipeline

Input
↓
Source Detection
↓
Parsing
↓
Canonical Mapping
↓
Normalization
↓
Duplicate Detection
↓
Merge
↓
Conflict Resolution
↓
Confidence
↓
Provenance
↓
Projection
↓
Validation
↓
Final JSON

---

# Canonical Candidate Profile

The output schema contains: `candidate_id`, `full_name`, `emails`, `phones`, `location`, `links`, `headline`, `years_experience`, `skills`, `experience`, `education`, `provenance`, and `overall_confidence`. It strictly adheres to `schemas/canonical_candidate.json`.

---

# Supported Sources

### Structured
- Recruiter CSV
- ATS JSON

### Unstructured
- Resume PDF
- GitHub Profile JSON
- LinkedIn Profile JSON
- Recruiter Notes TXT

---

# Output

- **Output JSON:** Strict adherence to canonical schema.
- **Projection Views:** Output can dynamically omit PII based on `projection_rules.json`.
- **Validation:** JSON is strictly validated via the `jsonschema` library.
- **Knowledge Graph:** Rendered visually in the Dashboard using D3/Canvas.
- **Comparison Results:** Side-by-side matrices and Radar charts in the Dashboard.
- **Analytics:** Basic statistical endpoint served by the Flask API.

---

# Edge Cases

- **Missing Email:** Heavy confidence penalty applied; fuzzy Jaro-Winkler name matching takes over deduplication.
- **Malformed Resume:** Spacy handles block skips and returns partial data, which lowers the confidence score appropriately.
- **Duplicate Candidate:** Safely resolved by collapsing fields and merging array histories.
- **Conflicting Phone:** Falls back to timestamp/source priority trust hierarchy.
- **Invalid JSON:** `jsonschema` throws a validation error during the final phase, flagging the output.

---

# Assumptions

- Configuration files are valid JSON.
- Unknown array values are ignored or cast to string; missing primitives default to `null`.
- Unstructured GitHub/LinkedIn exports are provided as flat JSON files in their respective directories.

---

# Limitations

- No persistent relational database (runs purely in memory).
- Unstructured parsing relies on deterministic NLP (`spacy`) rather than API-driven LLMs.
- End-to-end Cypress UI testing is omitted.

---

# Future Improvements

- Add PostgreSQL for true data persistence.
- Implement OpenAI/Anthropic APIs for 99.9% accurate unstructured resume NLP extraction.
- Expand dashboard to allow inline manual corrections of merged conflicts.

---

# Assignment Mapping

- [x] Multi-source ingestion
- [x] Canonical schema generation
- [x] Field normalization
- [x] Duplicate detection
- [x] Merge engine
- [x] Conflict resolution
- [x] Provenance tracking
- [x] Confidence scoring
- [x] Runtime configurable output
- [x] Schema validation
- [x] Dashboard / CLI support
- [x] Edge case handling

---

# Quick Start

```bash
# 1. Clone the repository

git clone https://github.com/sama-dharani/Candidate-intelligence-engine-Eightfold-AI-Project.git

# 2. Enter the project directory (use quotes since there are spaces in the name)

cd Candidate-intelligence-engine-Eightfold-AI-Project

# 3. Create a virtual environment
python -m venv venv

# 4. Activate the virtual environment (Windows)
venv\Scripts\activate

# 5. Install the required Python packages
pip install -r requirements.txt

# 6. Download the required AI language model for Spacy
python -m spacy download en_core_web_sm

# 7. Start the Dashboard UI (this will block your terminal)
python examples/dashboard/app.py
```
### Extra
### Running Tests
To run the automated tests open a **new terminal**, activate the environment again, and run:
```bash
python -m pytest tests/test_pipeline.py -v
```
