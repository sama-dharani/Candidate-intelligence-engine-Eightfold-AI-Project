from typing import List, Dict, Any

class RoleRecommender:
    """Enriches candidate profile by recommending matching job roles based on skills profile."""

    def __init__(self):
        # Define target roles and their key skills requirements
        self.role_requirements = {
            "AI Engineer": ["python", "pytorch", "tensorflow", "langchain", "crewai", "llm", "transformers", "openai"],
            "ML Engineer": ["python", "pytorch", "tensorflow", "scikit-learn", "docker", "machine learning", "deep learning"],
            "Data Scientist": ["python", "sql", "machine learning", "scikit-learn", "pandas", "nlp", "statistics"],
            "Prompt Engineer": ["langchain", "crewai", "openai", "prompt engineering", "llm", "transformers"],
            "DevOps Engineer": ["docker", "kubernetes", "k8s", "aws", "gcp", "azure", "jenkins", "ci/cd", "helm"],
            "Backend Engineer": ["python", "java", "go", "redis", "postgresql", "mysql", "mongodb", "docker", "sql", "nosql"],
            "Frontend Engineer": ["javascript", "typescript", "react", "html", "css", "vue", "angular"],
            "Full Stack Engineer": ["react", "javascript", "typescript", "python", "node", "sql", "css", "html"]
        }

    def recommend_roles(self, skills: List[str]) -> List[str]:
        """Examine candidate skills and return matching job roles sorted by match score."""
        cand_skills = [s.lower().strip() for s in skills if isinstance(s, str)]
        if not cand_skills:
            return ["General Software Engineer"]

        recommendations = []
        for role, req_skills in self.role_requirements.items():
            matches = 0
            for req in req_skills:
                # Direct check or substring check (safe)
                if req in cand_skills:
                    matches += 1
                else:
                    for cs in cand_skills:
                        if len(req) >= 4 and len(cs) >= 4 and (req in cs or cs in req):
                            matches += 1
                            break
            
            # If candidate matches at least 2 required skills or 30% of skills, recommend it
            match_ratio = matches / len(req_skills)
            if matches >= 2 or (len(req_skills) <= 5 and matches >= 1):
                score = round(match_ratio * 100)
                recommendations.append((role, score))

        # Sort recommendations by score descending
        recommendations.sort(key=lambda x: x[1], reverse=True)
        
        results = []
        for r, score in recommendations:
            results.append(f"{r} (Match: {score}%)")
            
        if not results:
            results.append("Software Engineer (General Match)")
            
        return results
