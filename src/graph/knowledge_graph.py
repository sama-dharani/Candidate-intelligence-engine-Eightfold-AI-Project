from typing import Dict, List, Any, Set, Tuple

class KnowledgeGraph:
    """In-memory Candidate Knowledge Graph mapping entities and their relationships.

    Entities: Candidate, Skill, Company, School, Project, Location, Certification, Repo
    Relationships: knows, worked_at, studied_at, built, certified, lives_in, contributed
    """

    def __init__(self):
        # Nodes: dict mapping node_id -> {type: str, properties: dict}
        self.nodes: Dict[str, Dict[str, Any]] = {}
        # Edges: list of tuples (source_id, target_id, relation_type)
        self.edges: Set[Tuple[str, str, str]] = set()

    def add_node(self, node_id: str, node_type: str, properties: Dict[str, Any] = None) -> None:
        """Add an entity node to the graph."""
        if not node_id:
            return
        node_id = str(node_id).strip()
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "id": node_id,
                "type": node_type,
                "properties": properties or {}
            }

    def add_edge(self, source_id: str, target_id: str, relation: str) -> None:
        """Add a directed edge between two entity nodes."""
        if not source_id or not target_id:
            return
        s_id = str(source_id).strip()
        t_id = str(target_id).strip()
        
        # Ensure nodes exist
        if s_id in self.nodes and t_id in self.nodes:
            self.edges.add((s_id, t_id, relation))

    def build_from_candidates(self, candidates: List[Dict[str, Any]]) -> None:
        """Construct the knowledge graph from a list of candidate profiles."""
        for cand in candidates:
            c_name = cand.get("full_name")
            if not c_name:
                continue
            
            # 1. Add Candidate Node
            email_val = cand.get("emails", [""])[0] if cand.get("emails") else ""
            c_id = email_val if email_val else c_name
            self.add_node(c_id, "Candidate", {
                "name": c_name,
                "email": email_val,
                "phone": cand.get("phones", [""])[0] if cand.get("phones") else "",
                "linkedin": cand.get("linkedin", ""),
                "github": cand.get("github", "")
            })

            # 2. Add Location Node & Edge
            loc = cand.get("location")
            if loc:
                self.add_node(loc, "Location")
                self.add_edge(c_id, loc, "lives_in")

            # 3. Add Skill Nodes & Edges
            for skill in cand.get("skills", []):
                self.add_node(skill, "Skill")
                self.add_edge(c_id, skill, "knows")

            # 4. Add Company Nodes & Edges
            for job in cand.get("experience", []):
                company = job.get("company")
                if company:
                    self.add_node(company, "Company", {"industry": "Technology"})
                    self.add_edge(c_id, company, "worked_at")

            # 5. Add School Nodes & Edges
            for edu in cand.get("education", []):
                school = edu.get("institution")
                if school:
                    self.add_node(school, "School")
                    self.add_edge(c_id, school, "studied_at")

            # 6. Add Project Nodes & Edges
            for proj in cand.get("projects", []):
                p_name = proj.get("name")
                if p_name:
                    self.add_node(p_name, "Project", {"description": proj.get("description", "")})
                    self.add_edge(c_id, p_name, "built")

            # 7. Add Certification Nodes & Edges
            for cert in cand.get("certifications", []):
                self.add_node(cert, "Certification")
                self.add_edge(c_id, cert, "certified")

            # 8. Add GitHub Repo / URL Nodes & Edges
            gh = cand.get("github")
            if gh:
                self.add_node(gh, "Repo")
                self.add_edge(c_id, gh, "contributed")

    def get_candidate_triples(self, cand_id: str) -> List[Dict[str, Any]]:
        """Query relations specifically connected to a single candidate."""
        triples = []
        for s, t, r in self.edges:
            if s == cand_id or t == cand_id:
                triples.append({
                    "source": s,
                    "source_type": self.nodes[s]["type"],
                    "target": t,
                    "target_type": self.nodes[t]["type"],
                    "relation": r
                })
        return triples

    def get_all_triples(self) -> List[Dict[str, Any]]:
        """Return all triples representing the full candidate knowledge graph."""
        triples = []
        for s, t, r in self.edges:
            triples.append({
                "source": s,
                "source_type": self.nodes[s]["type"],
                "target": t,
                "target_type": self.nodes[t]["type"],
                "relation": r
            })
        return triples
