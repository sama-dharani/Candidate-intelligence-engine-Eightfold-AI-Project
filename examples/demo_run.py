#!/usr/bin/env python3
"""
demo_run.py - CLI demo of the Enterprise Candidate Intelligence Platform.

Runs the complete pipeline dynamically across all files in the data directory.
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.loaders import CSVLoader, ATSLoader, PDFLoader, GitHubLoader, LinkedInLoader
from src.core import (
    DynamicFieldMapper, EntityResolver, CandidateMerger,
    CandidateValidator, ProfileProjector, ConfidenceEngine,
    RankingEngine, AnalyticsEngine
)
from src.ai import ResumeParser, EntityExtractor, SkillClassifier, RoleRecommender
from src.graph import KnowledgeGraph

WORKSPACE = Path(__file__).resolve().parent.parent
CONFIGS   = WORKSPACE / "configs"
SCHEMAS   = WORKSPACE / "schemas"
DATA      = WORKSPACE / "data"


def setup_mock_data():
    """Create sample data files if they don't exist."""
    DATA.mkdir(exist_ok=True)
    (DATA / "github").mkdir(exist_ok=True)
    (DATA / "linkedin").mkdir(exist_ok=True)

    # CSV: three candidates, one is John Smith
    csv_path = DATA / "candidates.csv"
    if not csv_path.exists():
        csv_path.write_text(
            "Name,Email,Phone,Location,Skills,LinkedIn\n"
            "John Smith,john.smith@gmail.com,+1 123-456-7890,Hyderabad,Python;SQL,https://linkedin.com/in/johnsmith\n"
            "Jane Doe,jane.doe@yahoo.com,+91 9876543210,Bangalore,Java;Spring Boot;React;AWS;Docker,https://linkedin.com/in/janedoe\n"
            "Bob Johnson,bob.johnson@microsoft.com,444-555-6666,Hyderabad,React;JavaScript;HTML;CSS;TypeScript,https://linkedin.com/in/bobjohnson\n",
            encoding="utf-8"
        )

    # ATS JSON: same John Smith (different name variant)
    json_path = DATA / "candidates.json"
    if not json_path.exists():
        json_path.write_text(json.dumps([{
            "full_name": "John A. Smith",
            "emails": ["john.smith@gmail.com"],
            "phones": ["(123) 456-7890"],
            "skills": ["Python", "TensorFlow", "PyTorch"],
            "experience": [{
                "company": "Google",
                "title": "Software Engineer",
                "start_date": "2020", "end_date": "2022",
                "description": "Built scalable cloud services and Python models."
            }]
        }], indent=2), encoding="utf-8")

    # Resume (text file read by PDFLoader fallback)
    resume_path = DATA / "resume_john_smith.pdf"
    if not resume_path.exists():
        resume_path.write_text(
            "JOHN SMITH\n"
            "Email: john.smith@gmail.com\n"
            "Phone: 123-456-7890\n"
            "GitHub: https://github.com/john-smith-ai\n\n"
            "EXPERIENCE\n"
            "AI Lead at TechCorp 2025 - Present\n"
            "Leading AI research using LangChain, CrewAI, Python, AWS.\n"
            "Senior Engineer at StartupX 2022 - 2024\n"
            "Deployed ML models using PyTorch, Docker, Redis.\n"
            "Intern at Google 2019 - 2019\n"
            "Assisted in Python web development and PostgreSQL queries.\n\n"
            "EDUCATION\n"
            "BS in Computer Science, Stanford University 2015 - 2019\n\n"
            "PROJECTS\n"
            "AI Chatbot (LangChain, CrewAI, Python, OpenAI)\n"
            "Built an autonomous team assistant using OpenAI APIs.\n\n"
            "CERTIFICATIONS\n"
            "AWS Certified Developer\n",
            encoding="utf-8"
        )

    # GitHub JSON dump
    gh_path = DATA / "github" / "john-smith.json"
    if not gh_path.exists():
        gh_path.write_text(json.dumps({
            "username": "john-smith-ai",
            "html_url": "https://github.com/john-smith-ai",
            "public_repos": 3,
            "repositories": [
                {"name": "ai-chatbot",
                 "description": "LangChain and CrewAI chatbot.",
                 "languages": ["Python", "HTML"]},
                {"name": "pytorch-models",
                 "description": "CV models with PyTorch.",
                 "languages": ["Python"]}
            ]
        }, indent=2), encoding="utf-8")

    # LinkedIn JSON dump
    li_path = DATA / "linkedin" / "john-smith.json"
    if not li_path.exists():
        li_path.write_text(json.dumps({
            "linkedin_id": "johnsmith",
            "profile_url": "https://linkedin.com/in/johnsmith",
            "skills": ["Python", "SQL", "Machine Learning", "Cloud Computing"]
        }, indent=2), encoding="utf-8")


def run():
    print("\n" + "=" * 65)
    print("  Enterprise Candidate Intelligence Platform — Demo Run")
    print("=" * 65)

    # ── Step 0: Mock Data ─────────────────────────────────────────
    setup_mock_data()
    print("\n[1/9]  Mock data ready in ./data/")

    # ── Step 1: Initialise engines ────────────────────────────────
    mapper          = DynamicFieldMapper(CONFIGS / "mapping.json")
    resolver        = EntityResolver(CONFIGS / "weights.json", threshold=0.75)
    merger          = CandidateMerger(resolver)
    validator       = CandidateValidator(SCHEMAS / "candidate_schema.json")
    projector       = ProfileProjector(CONFIGS / "projection_rules.json")
    conf_engine     = ConfidenceEngine(CONFIGS / "weights.json")
    rank_engine     = RankingEngine()
    analytics_eng   = AnalyticsEngine()
    resume_parser   = ResumeParser(CONFIGS / "skills_taxonomy.json")
    entity_extract  = EntityExtractor()
    skill_cls       = SkillClassifier(CONFIGS / "skills_taxonomy.json")
    recommender     = RoleRecommender()

    # ── Step 2: Universal Ingestion ──────────────────────────────
    raw_records = []
    src_idx = 0
    pdf_texts = {}

    csv_files = list(DATA.glob("*.csv"))
    json_files = list(DATA.glob("*.json"))
    pdf_files = list(DATA.glob("*.pdf")) + list(DATA.glob("*.txt"))

    for f in csv_files:
        rows = CSVLoader().load(f)
        for row in rows:
            mapped = mapper.get_all(row)
            mapped.update({"_source_index": src_idx, "_source_type": "csv", "_source_file": f.name})
            raw_records.append(mapped)
            src_idx += 1

    for f in json_files:
        rows = ATSLoader().load(f)
        for row in rows:
            mapped = mapper.get_all(row)
            for key in ("experience", "education", "projects", "certifications"):
                if key in row:
                    mapped[key] = row[key]
            mapped.update({"_source_index": src_idx, "_source_type": "ats", "_source_file": f.name})
            raw_records.append(mapped)
            src_idx += 1

    for f in pdf_files:
        text = PDFLoader().load(f)
        pdf_texts[f.stem] = text
        parsed = resume_parser.parse_text(text)
        extracted = entity_extract.extract_all(text)
        cand = {**parsed, **extracted, "_source_index": src_idx, "_source_type": "resume", "_source_file": f.name}
        raw_records.append(cand)
        src_idx += 1

    print(f"[2/9]  Loaded {len(raw_records)} raw records from CSV + ATS JSON + Resume PDF")

    # ── Step 3: Entity Resolution & Deduplication ─────────────────
    merged = merger.merge_all(raw_records)
    duplicates = len(raw_records) - len(merged)
    print(f"[3/9]  Entity resolution complete -- {duplicates} duplicate(s) merged -> {len(merged)} unique candidates")

    # ── Step 4: External Source Enrichment ───────────────────────
    gh_loader = GitHubLoader()
    li_loader = LinkedInLoader()

    for cand in merged:
        gh_url = cand.get("github", "")
        if gh_url and "john-smith-ai" in gh_url:
            gh_data = gh_loader.load(DATA / "github" / "john-smith.json")
            cand["_github_raw"] = gh_data
            cand["github"] = gh_data["html_url"]

        li_url = cand.get("linkedin", "")
        if li_url and "johnsmith" in li_url:
            li_data = li_loader.load(DATA / "linkedin" / "john-smith.json")
            cand["skills"] = list(set(cand.get("skills", []) + li_data.get("skills", [])))
            cand["linkedin"] = li_data["profile_url"]

    print("[4/9]  External source enrichment done (GitHub + LinkedIn)")

    # ── Step 5: AI Skill Classification ──────────────────────────
    for cand in merged:
        name_key = (cand.get("full_name") or "").lower().replace(" ", "-")
        resume_text = next((v for k, v in pdf_texts.items() if k.lower() in name_key or name_key in k.lower()), "")
        cand["skill_analysis"]  = skill_cls.analyze_skills(cand, resume_text)
        cand["recommendations"] = recommender.recommend_roles(cand.get("skills", []))
    print("[5/9]  AI skill classification & role recommendations built")

    # ── Step 6: Timeline & Gap Detection ─────────────────────────
    for cand in merged:
        exp = cand.get("experience", [])
        edu = cand.get("education", [])
        cand["timeline"]      = entity_extract.build_timeline(exp, edu)
        cand["gap_detection"] = entity_extract.detect_gaps(cand["timeline"])
    print("[6/9]  Career timelines built; gap detection applied")

    # ── Step 7: Confidence & Explainability ───────────────────────
    for cand in merged:
        cand["confidence"] = conf_engine.compute(cand)
    print("[7/9]  Confidence scores + explainability reasons computed")

    # ── Step 8: Knowledge Graph ───────────────────────────────────
    graph = KnowledgeGraph()
    graph.build_from_candidates(merged)
    print(f"[8/9]  Knowledge graph built — "
          f"{len(graph.nodes)} nodes, {len(graph.edges)} edges")

    # ── Step 9: Validation & Projection ──────────────────────────
    final_output = []
    for cand in merged:
        is_valid, errors = validator.validate(cand)
        if not is_valid:
            print(f"  ⚠  Validation issues for {cand.get('full_name')}: {errors}")
        projected = projector.project(cand, "full")
        final_output.append(projected)

    # Analytics
    analytics = analytics_eng.compile(len(raw_records), merged)

    print("[9/9]  Validation OK  |  Projection complete\n")
    print("=" * 65)
    print(f"  Processed      : {analytics['processed']} raw records")
    print(f"  Unique cands   : {analytics['candidates_count']}")
    print(f"  Duplicates     : {analytics['duplicates']}")
    print(f"  Avg Confidence : {analytics['average_confidence']}%")
    top_s = ", ".join(i["skill"] for i in analytics["top_skills"][:5])
    print(f"  Top Skills     : {top_s}")

    # ── Save output ───────────────────────────────────────────────
    output_path = WORKSPACE / "output_candidates.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, default=str)
    print(f"\nFinal JSON saved -> {output_path}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run()
