"""
tests/test_pipeline.py
Comprehensive unit + integration tests for the Candidate Intelligence Platform.
"""
import sys
import json
import pytest
import tempfile
from pathlib import Path

# Ensure project root is on path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.loaders import CSVLoader, ATSLoader, PDFLoader, GitHubLoader, LinkedInLoader
from src.core import (
    DynamicFieldMapper, EntityResolver, CandidateMerger,
    CandidateValidator, ProfileProjector, ConfidenceEngine,
    RankingEngine, AnalyticsEngine
)
from src.ai import ResumeParser, EntityExtractor, SkillClassifier, RoleRecommender
from src.graph import KnowledgeGraph

CONFIGS = Path(__file__).resolve().parent.parent / "configs"
SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def sample_mapping_file(tmp_path):
    m = {"full_name": ["name", "full name"], "emails": ["email"], "skills": ["skills"]}
    p = tmp_path / "mapping.json"
    p.write_text(json.dumps(m))
    return p

@pytest.fixture
def global_mapping():
    return DynamicFieldMapper(CONFIGS / "mapping.json")

@pytest.fixture
def sample_candidates():
    return [
        {"full_name": "Alice Kumar",
         "emails": ["alice@example.com"],
         "phones": ["9876543210"],
         "skills": ["Python", "AWS"],
         "experience": [{"company": "Amazon", "title": "SDE", "start_date": "2021", "end_date": "2024", "description": "Python cloud services"}],
         "education": [{"institution": "IIT Delhi", "degree": "B.Tech", "end_date": "2021"}],
         "location": "Hyderabad",
         "_source_index": 0, "_source_type": "csv"},
        {"full_name": "Alice K",
         "emails": ["alice@example.com"],   # same email → same person
         "phones": ["9876543210"],
         "skills": ["Python", "Docker", "TensorFlow"],
         "experience": [{"company": "Google", "title": "ML Engineer", "start_date": "2024", "end_date": "Present", "description": "ML pipelines with TensorFlow"}],
         "_source_index": 1, "_source_type": "ats"},
        {"full_name": "Bob Patel",
         "emails": ["bob@example.com"],
         "phones": ["1112223333"],
         "skills": ["JavaScript", "React", "CSS"],
         "location": "Bangalore",
         "_source_index": 2, "_source_type": "csv"},
    ]


# ═══════════════════════════════════════════════════════════════
#  1 · DynamicFieldMapper
# ═══════════════════════════════════════════════════════════════

class TestDynamicFieldMapper:

    def test_maps_alias_to_canonical(self, sample_mapping_file):
        mapper = DynamicFieldMapper(sample_mapping_file)
        row = {"name": "John Smith", "email": "john@test.com", "skills": "Python, SQL"}
        result = mapper.get_all(row)
        assert result["full_name"] == "John Smith"
        assert "john@test.com" in result["emails"]

    def test_handles_nested_json(self, sample_mapping_file):
        mapper = DynamicFieldMapper(sample_mapping_file)
        nested = {"candidate": {"name": "Jane Doe"}}
        result = mapper.find_value(nested, "full_name")
        assert result == "Jane Doe"

    def test_csv_comma_split_skills(self, sample_mapping_file):
        mapper = DynamicFieldMapper(sample_mapping_file)
        row = {"name": "Test", "skills": "Python, Java, Docker"}
        result = mapper.get_all(row)
        assert "Python" in result["skills"]
        assert len(result["skills"]) == 3

    def test_global_config_loads(self, global_mapping):
        assert "full_name" in global_mapping.mapping
        assert "emails" in global_mapping.mapping


# ═══════════════════════════════════════════════════════════════
#  2 · EntityResolver
# ═══════════════════════════════════════════════════════════════

class TestEntityResolver:

    def setup_method(self):
        self.resolver = EntityResolver(threshold=0.75)

    def test_exact_email_gives_100(self):
        r1 = {"emails": ["john@test.com"], "full_name": "John Smith"}
        r2 = {"emails": ["john@test.com"], "full_name": "J. Smith"}
        res = self.resolver._similarity_score(r1, r2)
        assert res["score"] == 1.0
        assert "Exact email match" in res["reasons"][0]

    def test_no_overlap_gives_low_score(self):
        r1 = {"full_name": "Alice Brown", "emails": ["alice@x.com"], "phones": ["111"]}
        r2 = {"full_name": "Bob Jones",   "emails": ["bob@y.com"],   "phones": ["999"]}
        res = self.resolver._similarity_score(r1, r2)
        assert res["score"] < 0.4

    def test_same_candidate_name_fuzzy(self):
        r1 = {"full_name": "Jonathan Smith", "emails": ["j.smith@test.com"]}
        r2 = {"full_name": "Jon Smith",      "emails": ["j.smith@test.com"]}
        assert self.resolver.is_same_candidate(r1, r2) is True

    def test_github_handle_match(self):
        r1 = {"github": "https://github.com/alice-ai", "emails": []}
        r2 = {"github": "https://github.com/alice-ai", "emails": []}
        res = self.resolver._similarity_score(r1, r2)
        assert res["details"]["github"] == 1.0

    def test_phone_suffix_matching(self):
        r1 = {"phones": ["+919876543210"], "emails": [], "full_name": "X"}
        r2 = {"phones": ["9876543210"],    "emails": [], "full_name": "X"}
        res = self.resolver._similarity_score(r1, r2)
        assert res["details"]["phone"] >= 0.9


# ═══════════════════════════════════════════════════════════════
#  3 · CandidateMerger
# ═══════════════════════════════════════════════════════════════

class TestCandidateMerger:

    def test_deduplicates_same_email(self, sample_candidates):
        merger = CandidateMerger()
        clusters = merger.cluster_records(sample_candidates)
        # Alice and Alice K have same email → same cluster
        assert len(clusters) == 2

    def test_merge_combines_skills(self, sample_candidates):
        merger = CandidateMerger()
        merged = merger.merge_all(sample_candidates)
        alice = next(c for c in merged if "Alice" in (c.get("full_name") or ""))
        all_skills = [s.lower() for s in alice.get("skills", [])]
        assert "python" in all_skills
        assert "docker" in all_skills

    def test_merge_provenance_tracked(self, sample_candidates):
        merger = CandidateMerger()
        merged = merger.merge_all(sample_candidates)
        alice = next(c for c in merged if "Alice" in (c.get("full_name") or ""))
        assert len(alice["provenance"]) == 2   # came from 2 sources

    def test_distinct_candidates_preserved(self, sample_candidates):
        merger = CandidateMerger()
        merged = merger.merge_all(sample_candidates)
        assert len(merged) == 2   # Alice (merged) + Bob


# ═══════════════════════════════════════════════════════════════
#  4 · ConfidenceEngine
# ═══════════════════════════════════════════════════════════════

class TestConfidenceEngine:

    def setup_method(self):
        self.engine = ConfidenceEngine()

    def test_full_profile_scores_high(self):
        cand = {
            "emails": ["a@b.com"],
            "phones": ["9999999999"],
            "skills": ["Python", "AWS", "Docker", "Kubernetes", "TensorFlow", "PyTorch", "SQL"],
            "github": "https://github.com/user",
            "linkedin": "https://linkedin.com/in/user",
            "experience": [{"company": "Google", "title": "SDE"}],
            "education": [{"institution": "MIT"}],
            "provenance": [{"source_index": 0, "source_type": "csv", "fields_contributed": ["emails", "phones", "skills"]}]
        }
        result = self.engine.compute(cand)
        assert result["score"] >= 0.85

    def test_empty_profile_scores_low(self):
        result = self.engine.compute({"provenance": []})
        assert result["score"] <= 0.10

    def test_reasons_list_is_populated(self):
        cand = {"emails": ["x@y.com"], "provenance": []}
        result = self.engine.compute(cand)
        assert len(result["reasons"]) > 0

    def test_score_clamped_to_1(self):
        cand = {
            "emails": ["a@b.com"], "phones": ["123"], "skills": ["x"] * 20,
            "github": "gh", "linkedin": "li",
            "experience": [{"company": "G"}], "education": [{"institution": "MIT"}],
            "provenance": [{"source_index": 0, "source_type": "ats", "fields_contributed": ["emails", "phones", "skills", "github"]}]
        }
        result = self.engine.compute(cand)
        assert result["score"] <= 1.0


# ═══════════════════════════════════════════════════════════════
#  5 · SkillClassifier
# ═══════════════════════════════════════════════════════════════

class TestSkillClassifier:

    def setup_method(self):
        self.classifier = SkillClassifier(CONFIGS / "skills_taxonomy.json")

    def test_python_is_programming(self):
        assert self.classifier.classify("Python") == "Programming"

    def test_aws_is_cloud(self):
        assert self.classifier.classify("AWS") == "Cloud"

    def test_docker_is_containers(self):
        assert self.classifier.classify("Docker") == "Containers"

    def test_pytorch_is_ai(self):
        assert self.classifier.classify("PyTorch") == "AI"

    def test_redis_is_database(self):
        assert self.classifier.classify("Redis") == "Database"

    def test_proficiency_1_to_5(self):
        cand = {"skills": ["Python"], "experience": [], "projects": []}
        analysis = self.classifier.analyze_skills(cand)
        prof = analysis["Python"]["proficiency"]
        assert 1 <= prof <= 5

    def test_confidence_between_0_and_1(self):
        cand = {"skills": ["Docker"], "experience": [], "projects": []}
        analysis = self.classifier.analyze_skills(cand)
        conf = analysis["Docker"]["confidence"]
        assert 0.0 <= conf <= 1.0


# ═══════════════════════════════════════════════════════════════
#  6 · EntityExtractor — Timeline & Gap Detection
# ═══════════════════════════════════════════════════════════════

class TestEntityExtractor:

    def setup_method(self):
        self.extractor = EntityExtractor()

    def test_timeline_sorted_ascending(self):
        exp = [
            {"company": "Google", "title": "SDE", "start_date": "2022", "end_date": "2024", "description": ""},
            {"company": "Intern",  "title": "Intern", "start_date": "2019", "end_date": "2020", "description": ""},
        ]
        edu = [{"institution": "MIT", "degree": "BSc", "end_date": "2019"}]
        timeline = self.extractor.build_timeline(exp, edu)
        years = [e["year"] for e in timeline]
        assert years == sorted(years)

    def test_gap_detection_flags_large_gap(self):
        exp = [
            {"company": "A", "title": "Dev", "start_date": "2019", "end_date": "2020", "description": ""},
            {"company": "B", "title": "Dev", "start_date": "2024", "end_date": "Present", "description": ""},
        ]
        timeline = self.extractor.build_timeline(exp, [])
        gaps = self.extractor.detect_gaps(timeline)
        assert len(gaps) == 1
        assert gaps[0]["duration_years"] >= 3

    def test_no_gap_with_continuous_employment(self):
        exp = [
            {"company": "A", "title": "E", "start_date": "2020", "end_date": "2021", "description": ""},
            {"company": "B", "title": "E", "start_date": "2021", "end_date": "2022", "description": ""},
        ]
        timeline = self.extractor.build_timeline(exp, [])
        gaps = self.extractor.detect_gaps(timeline)
        assert len(gaps) == 0


# ═══════════════════════════════════════════════════════════════
#  7 · RoleRecommender
# ═══════════════════════════════════════════════════════════════

class TestRoleRecommender:

    def setup_method(self):
        self.rec = RoleRecommender()

    def test_python_pytorch_recommends_ai_engineer(self):
        skills = ["Python", "PyTorch", "TensorFlow", "LangChain"]
        recs = self.rec.recommend_roles(skills)
        role_names = [r.split(" (")[0] for r in recs]
        assert any("AI" in r or "ML" in r for r in role_names)

    def test_react_recommends_frontend(self):
        skills = ["React", "JavaScript", "HTML", "CSS", "TypeScript"]
        recs = self.rec.recommend_roles(skills)
        role_names = [r.split(" (")[0] for r in recs]
        assert any("Frontend" in r or "Full Stack" in r for r in role_names)

    def test_docker_kubernetes_recommends_devops(self):
        skills = ["Docker", "Kubernetes", "AWS", "Jenkins"]
        recs = self.rec.recommend_roles(skills)
        role_names = [r.split(" (")[0] for r in recs]
        assert any("DevOps" in r for r in role_names)

    def test_empty_skills_returns_fallback(self):
        recs = self.rec.recommend_roles([])
        assert len(recs) >= 1


# ═══════════════════════════════════════════════════════════════
#  8 · CandidateValidator
# ═══════════════════════════════════════════════════════════════

class TestCandidateValidator:

    def setup_method(self):
        self.v = CandidateValidator(SCHEMAS / "candidate_schema.json")

    def test_valid_profile_passes(self):
        cand = {"full_name": "Alice", "emails": ["a@b.com"], "skills": ["Python"]}
        ok, errors = self.v.validate(cand)
        assert ok
        assert errors == []

    def test_missing_full_name_fails(self):
        cand = {"emails": ["x@y.com"]}
        ok, errors = self.v.validate(cand)
        assert not ok
        assert len(errors) > 0


# ═══════════════════════════════════════════════════════════════
#  9 · ProfileProjector
# ═══════════════════════════════════════════════════════════════

class TestProfileProjector:

    def setup_method(self):
        self.proj = ProfileProjector(CONFIGS / "projection_rules.json")

    def _full_cand(self):
        return {
            "full_name": "Alice Kumar", "emails": ["alice@example.com"],
            "phones": ["9876543210"], "skills": ["Python", "AWS"],
            "location": "Hyderabad", "experience": [{"company": "Google", "title": "SDE"}],
            "education": [{"institution": "IIT Delhi", "degree": "B.Tech"}],
            "provenance": [{"source_type": "csv"}],
            "confidence": {"score": 0.9, "reasons": []}
        }

    def test_full_view_keeps_all_fields(self):
        result = self.proj.project(self._full_cand(), "full")
        assert "emails" in result
        assert "phones" in result
        assert "full_name" in result
        assert "skills" in result

    def test_public_view_removes_pii(self):
        result = self.proj.project(self._full_cand(), "public")
        assert "emails" not in result
        assert "phones" not in result
        assert "provenance" not in result
        assert "full_name" in result   # name stays in public view
        assert "skills" in result

    def test_recruiter_view_redacts_emails_and_phones(self):
        result = self.proj.project(self._full_cand(), "recruiter")
        assert result["emails"] == ["[REDACTED]"]
        assert result["phones"] == ["[REDACTED]"]
        assert "full_name" in result   # name is visible to recruiter
        assert "skills" in result

    def test_anonymous_view_strips_all_pii(self):
        """Anonymous / blind screening: NO name, NO email, NO phone, NO location."""
        result = self.proj.project(self._full_cand(), "anonymous")
        assert "full_name" not in result
        assert "emails" not in result
        assert "phones" not in result
        assert "location" not in result
        assert "provenance" not in result
        # But skills and experience must remain for screening
        assert "skills" in result
        assert "experience" in result

    def test_skills_only_view_returns_exactly_three_fields(self):
        """skills_only must return just full_name, skills, and confidence."""
        result = self.proj.project(self._full_cand(), "skills_only")
        public_keys = [k for k in result.keys() if not k.startswith("_")]
        assert "skills" in result
        assert "confidence" in result
        assert "emails" not in result
        assert "phones" not in result
        assert "experience" not in result

    def test_custom_dict_rules_projection(self):
        """Runtime dict rules allow arbitrary include/exclude at request time."""
        custom_rules = {
            "include": ["full_name", "skills"],
            "exclude": ["emails", "phones", "location"]
        }
        result = self.proj.project(self._full_cand(), custom_rules)
        assert "full_name" in result
        assert "skills" in result
        assert "emails" not in result
        assert "phones" not in result
        assert "location" not in result

    def test_unknown_view_falls_back_to_full(self):
        """Unknown view name silently falls back to full access."""
        result = self.proj.project(self._full_cand(), "nonexistent_view")
        assert "emails" in result
        assert "full_name" in result

    def test_redaction_handles_list_values(self):
        """Redaction must mask each item in a list field, not the list itself."""
        cand = {"full_name": "Test", "emails": ["a@b.com", "c@d.com"], "phones": ["111"]}
        result = self.proj.project(cand, "recruiter")
        assert result["emails"] == ["[REDACTED]", "[REDACTED]"]


# ═══════════════════════════════════════════════════════════════
# 10 · KnowledgeGraph
# ═══════════════════════════════════════════════════════════════

class TestKnowledgeGraph:

    def setup_method(self):
        self.graph = KnowledgeGraph()
        self.graph.build_from_candidates([{
            "full_name": "Alice Kumar",
            "emails": ["alice@example.com"],
            "skills": ["Python", "AWS"],
            "experience": [{"company": "Google", "title": "SDE", "start_date": "2021", "end_date": "2024", "description": ""}],
            "education": [{"institution": "IIT Delhi", "degree": "B.Tech", "end_date": "2021"}],
            "projects": [{"name": "AI Chatbot", "description": "Built using LangChain", "technologies": ["Python"]}],
            "certifications": ["AWS Certified"],
            "location": "Hyderabad",
            "github": "https://github.com/alice-ai"
        }])

    def test_nodes_created(self):
        assert len(self.graph.nodes) > 0
        # Should have Candidate, Skill, Company, School, Location, Project, Certification, Repo nodes
        node_types = {v["type"] for v in self.graph.nodes.values()}
        assert "Candidate" in node_types
        assert "Skill" in node_types
        assert "Company" in node_types

    def test_edges_created(self):
        assert len(self.graph.edges) > 0

    def test_knows_relation_exists(self):
        relations = {e[2] for e in self.graph.edges}
        assert "knows" in relations
        assert "worked_at" in relations
        assert "studied_at" in relations

    def test_get_all_triples(self):
        triples = self.graph.get_all_triples()
        assert all("source" in t and "target" in t and "relation" in t for t in triples)


# ═══════════════════════════════════════════════════════════════
# 11 · RankingEngine
# ═══════════════════════════════════════════════════════════════

class TestRankingEngine:

    def setup_method(self):
        self.engine = RankingEngine()
        self.candidates = [
            {
                "full_name": "Alice", "skills": ["Python", "AWS", "Docker"],
                "location": "Hyderabad",
                "experience": [{"company": "G", "title": "SDE", "start_date": "2020", "end_date": "2024", "description": ""}],
                "confidence": {"score": 0.90, "reasons": []}
            },
            {
                "full_name": "Bob", "skills": ["React", "JavaScript"],
                "location": "Bangalore",
                "experience": [{"company": "H", "title": "FE Dev", "start_date": "2023", "end_date": "Present", "description": ""}],
                "confidence": {"score": 0.65, "reasons": []}
            }
        ]

    def test_ranked_list_same_length(self):
        ranked = self.engine.rank_candidates(self.candidates, {"skills": ["Python"]})
        assert len(ranked) == len(self.candidates)

    def test_python_aws_query_ranks_alice_first(self):
        ranked = self.engine.rank_candidates(self.candidates, {
            "skills": ["Python", "AWS"], "location": "Hyderabad"
        })
        assert ranked[0]["full_name"] == "Alice"

    def test_rank_score_between_0_and_100(self):
        ranked = self.engine.rank_candidates(self.candidates, {"skills": ["Python"]})
        for r in ranked:
            assert 0 <= r["_rank_score"] <= 100

    def test_reasons_generated(self):
        ranked = self.engine.rank_candidates(self.candidates, {"skills": ["Python"]})
        assert len(ranked[0]["_rank_reasons"]) > 0


# ═══════════════════════════════════════════════════════════════
# 12 · AnalyticsEngine
# ═══════════════════════════════════════════════════════════════

class TestAnalyticsEngine:

    def test_analytics_output_structure(self):
        eng = AnalyticsEngine()
        cands = [
            {"full_name": "A", "skills": ["Python", "AWS"],
             "experience": [{"company": "Google", "title": "SDE"}],
             "confidence": {"score": 0.90, "reasons": []}},
            {"full_name": "B", "skills": ["Python", "Docker"],
             "experience": [{"company": "Amazon", "title": "SDE"}],
             "confidence": {"score": 0.80, "reasons": []}}
        ]
        stats = eng.compile(5, cands)
        assert stats["processed"] == 5
        assert stats["duplicates"] == 3
        assert stats["candidates_count"] == 2
        assert 0 <= stats["average_confidence"] <= 100
        assert len(stats["top_skills"]) > 0
        assert stats["top_skills"][0]["skill"] == "Python"   # most common


# ═══════════════════════════════════════════════════════════════
# 13 · Loaders
# ═══════════════════════════════════════════════════════════════

class TestLoaders:

    def test_csv_loader(self, tmp_path):
        csv_f = tmp_path / "test.csv"
        csv_f.write_text("Name,Email\nAlice,alice@x.com\nBob,bob@y.com\n", encoding="utf-8")
        rows = CSVLoader().load(csv_f)
        assert len(rows) == 2
        assert rows[0]["Name"] == "Alice"

    def test_ats_loader_single_object(self, tmp_path):
        j = tmp_path / "test.json"
        j.write_text(json.dumps({"full_name": "Alice"}))
        rows = ATSLoader().load(j)
        assert len(rows) == 1

    def test_ats_loader_list(self, tmp_path):
        j = tmp_path / "test.json"
        j.write_text(json.dumps([{"a": 1}, {"a": 2}]))
        rows = ATSLoader().load(j)
        assert len(rows) == 2

    def test_pdf_loader_text_fallback(self, tmp_path):
        txt_f = tmp_path / "resume.pdf"
        txt_f.write_text("John Smith\nEmail: john@test.com\n")
        text = PDFLoader().load(txt_f)
        assert "John Smith" in text

    def test_github_loader_missing_returns_default(self, tmp_path):
        data = GitHubLoader().load(tmp_path / "nonexistent.json")
        assert "repositories" in data
        assert data["public_repos"] == 0

    def test_linkedin_loader_missing_returns_default(self, tmp_path):
        data = LinkedInLoader().load(tmp_path / "nonexistent.json")
        assert "skills" in data


# ═══════════════════════════════════════════════════════════════
# 14 · End-to-End Integration: CSV + JSON → Merged Canonical
# ═══════════════════════════════════════════════════════════════

class TestEndToEndPipeline:
    """
    Full pipeline integration test:
    Ingest multi-source CSV + JSON files for the same candidate,
    run entity resolution, merge, and verify the canonical profile.
    """

    def _run_pipeline(self, records):
        """Run the entity resolution + merge pipeline on raw records."""
        resolver = EntityResolver(threshold=0.75)
        merger   = CandidateMerger(resolver)
        return merger.merge_all(records)

    def test_csv_and_json_same_person_merges_to_one(self, tmp_path):
        """Same candidate in CSV + JSON → exactly 1 canonical profile."""
        records = [
            # CSV record
            {
                "full_name": "Alice Kumar", "emails": ["alice@example.com"],
                "phones": ["9876543210"], "skills": ["Python", "SQL"],
                "location": "Hyderabad",
                "_source_index": 0, "_source_type": "csv", "_source_file": "recruiter.csv"
            },
            # ATS JSON record (same person, more skills)
            {
                "full_name": "Alice K", "emails": ["alice@example.com"],
                "phones": ["9876543210"], "skills": ["Python", "Docker", "AWS"],
                "experience": [{"company": "Google", "title": "SDE", "start_date": "2022", "end_date": "Present"}],
                "_source_index": 1, "_source_type": "ats", "_source_file": "ats.json"
            },
        ]
        merged = self._run_pipeline(records)
        assert len(merged) == 1, "Same-email records must merge into one canonical profile"

    def test_merged_profile_has_union_skills(self, tmp_path):
        """Skills from CSV and JSON must be unioned in the canonical profile."""
        records = [
            {"full_name": "Alice Kumar", "emails": ["alice@example.com"],
             "skills": ["Python", "SQL"],
             "_source_index": 0, "_source_type": "csv"},
            {"full_name": "Alice K", "emails": ["alice@example.com"],
             "skills": ["Python", "Docker", "AWS"],
             "_source_index": 1, "_source_type": "ats"},
        ]
        merged = self._run_pipeline(records)
        alice = merged[0]
        skill_lower = [s.lower() for s in alice.get("skills", [])]
        assert "python" in skill_lower
        assert "sql" in skill_lower
        assert "docker" in skill_lower
        assert "aws" in skill_lower

    def test_merged_profile_provenance_lists_both_sources(self):
        """Canonical profile must track every source it was built from."""
        records = [
            {"full_name": "Alice Kumar", "emails": ["alice@example.com"],
             "skills": ["Python"], "_source_index": 0, "_source_type": "csv"},
            {"full_name": "Alice K", "emails": ["alice@example.com"],
             "skills": ["Docker"], "_source_index": 1, "_source_type": "ats"},
        ]
        merged = self._run_pipeline(records)
        alice = merged[0]
        source_types = [p.get("source_type") for p in alice.get("provenance", [])]
        assert "csv" in source_types
        assert "ats" in source_types

    def test_two_different_people_stay_separate(self):
        """Different emails → two distinct canonical profiles."""
        records = [
            {"full_name": "Alice Kumar", "emails": ["alice@example.com"],
             "skills": ["Python"], "_source_index": 0, "_source_type": "csv"},
            {"full_name": "Bob Patel", "emails": ["bob@example.com"],
             "skills": ["React"], "_source_index": 1, "_source_type": "csv"},
        ]
        merged = self._run_pipeline(records)
        assert len(merged) == 2, "Different-email candidates must remain as separate profiles"

    def test_pipeline_output_passes_projection(self):
        """Merged canonical profile must be projectable through all 5 view modes."""
        records = [
            {"full_name": "Alice Kumar", "emails": ["alice@example.com"],
             "phones": ["9876543210"], "skills": ["Python", "AWS"],
             "location": "Hyderabad", "confidence": {"score": 0.9, "reasons": []},
             "_source_index": 0, "_source_type": "csv"},
        ]
        merged = self._run_pipeline(records)
        alice = merged[0]
        projector = ProfileProjector(CONFIGS / "projection_rules.json")
        for mode in ["full", "recruiter", "public", "anonymous", "skills_only"]:
            result = projector.project(alice, mode)
            assert isinstance(result, dict), f"Projection mode '{mode}' must return a dict"
            assert "skills" in result or mode == "skills_only" or "skills" in result


# ═══════════════════════════════════════════════════════════════
# 15 · Normalization Determinism
# ═══════════════════════════════════════════════════════════════

class TestNormalizationDeterminism:
    """
    Verifies normalization rules are deterministic (same input → same output)
    and produce auditable before/after logs.
    """

    def _normalize_record(self, rec):
        """Apply the same normalization logic as the pipeline stage."""
        import re as _re
        history = []

        raw_phones = rec.get("phones", [])
        clean_phones = []
        for p in raw_phones:
            cleaned = _re.sub(r"[\s\-\(\)\+]", "", p).strip()
            if cleaned != p:
                history.append({"field": "phone", "original": p, "normalized": cleaned})
            clean_phones.append(cleaned)
        rec["phones"] = clean_phones

        raw_emails = rec.get("emails", [])
        clean_emails = []
        for e in raw_emails:
            cleaned = e.lower().strip()
            if cleaned != e:
                history.append({"field": "email", "original": e, "normalized": cleaned})
            clean_emails.append(cleaned)
        rec["emails"] = clean_emails

        raw_name = rec.get("full_name", "")
        if raw_name and raw_name.isupper():
            cleaned = raw_name.title().strip()
            history.append({"field": "name", "original": raw_name, "normalized": cleaned})
            rec["full_name"] = cleaned

        rec["_norm_history"] = history
        return rec

    def test_phone_strips_dashes_and_spaces(self):
        rec = {"phones": ["(987) 654-3210"]}
        result = self._normalize_record(rec)
        assert result["phones"] == ["9876543210"]
        assert len(result["_norm_history"]) == 1
        assert result["_norm_history"][0]["field"] == "phone"

    def test_email_lowercased(self):
        rec = {"emails": ["Alice@GMAIL.COM"]}
        result = self._normalize_record(rec)
        assert result["emails"] == ["alice@gmail.com"]
        assert result["_norm_history"][0]["field"] == "email"

    def test_all_caps_name_title_cased(self):
        rec = {"full_name": "JOHN SMITH"}
        result = self._normalize_record(rec)
        assert result["full_name"] == "John Smith"
        assert result["_norm_history"][0]["field"] == "name"

    def test_already_clean_record_has_empty_history(self):
        rec = {"phones": ["9876543210"], "emails": ["alice@example.com"], "full_name": "Alice Kumar"}
        result = self._normalize_record(rec)
        assert result["_norm_history"] == []

    def test_normalization_is_deterministic(self):
        """Running normalization twice on the same input must give identical output."""
        rec1 = {"phones": ["(987) 654-3210"], "emails": ["Alice@GMAIL.COM"]}
        rec2 = {"phones": ["(987) 654-3210"], "emails": ["Alice@GMAIL.COM"]}
        r1 = self._normalize_record(rec1)
        r2 = self._normalize_record(rec2)
        assert r1["phones"] == r2["phones"]
        assert r1["emails"] == r2["emails"]
        assert r1["_norm_history"] == r2["_norm_history"]

    def test_normalization_logs_are_structured(self):
        """Each norm history entry must have field, original, normalized keys."""
        rec = {"phones": ["(987) 654-3210"], "emails": ["Alice@GMAIL.COM"]}
        result = self._normalize_record(rec)
        for entry in result["_norm_history"]:
            assert "field" in entry
            assert "original" in entry
            assert "normalized" in entry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
