"""
Prifle NLP based skills extration and taxamony systems.
"""

import os
import spacy
import re
import json
from groq import AsyncGroq
from typing import List, Dict, Set, Any
import structlog
from collections import defaultdict
logger = structlog.get_logger()

class SkillsExtractor:
    """Extract Skills  Using NLP and rule_based methods"""
    def __init__(self ):
        """Initialize NLP model with skills taxamony"""
        logger.info(f"Initialzing Skills extractor...")

        # Laod spacy
        try:
          self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning(f"Spacy model not found: Run: python -m spacy download en_core_web_sm")
            self.nlp =None
        
        # LLM For Roles 
        self.llm_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"
        
        ## Skills taxamony
        self.skills_taxonomy = self._build_skills_taxonomy()

        ## Profieceincy Indicators

        self.proficiency_indicators = {
            'expert': ['expert', 'advanced', 'mastery', 'proficient', 'extensive'],
            'senior': ['senior', 'experienced', 'strong', 'solid', 'deep'],
            'intermediate': ['intermediate', 'working', 'good', 'competent'],
            'junior': ['junior', 'basic', 'familiar', 'learning', 'beginner']
        }

        logger.info("skills extractor Ready")

    def _build_skills_taxonomy(self) -> Dict:
        """Build comprehensive skills taxonomy with synonyms and relationships"""

        return{
            # Prigramming languages
        'programming_languages':{
            'python': ['python', 'py', 'python3'],
            'javascript': ['javascript', 'js', 'ecmascript', 'es6', 'es2025'],
            'typescript': ['typescript', 'ts'],
            'java': ['java'],
            'cpp': ['c++', 'cpp', 'cplusplus'],
            'cssharp': ['c#', 'csharp','dotnet'],
            'go': ['goland', 'go'],
            'rust': ['rust'],
            'ruby': ['ruby'],
            'php': ['php'],
            'swift': ['swift'],
            'kotlin': ['kotlin']
           },
           ## Frontend
        'frontend':{
            'react': ['react', 'reactjs', 'react.js'],
            'vue': ['vue', 'vuejs', 'vue.js'],
            'angular': ['angular', 'angularjs'],
            'html': ['html', 'html5'],
            'css': ['css', 'css3', 'cascading style sheets'],
            'sass': ['sass', 'scss'],
            'tailwind': ['tailwind', 'tailwindcss'],
            'bootstrap': ['bootstrap'],
            'webpack': ['webpack'],
            'vite': ['vite']
          },

        'backend': {
            'nodejs': ['node.js', 'nodejs', 'node'],
            'express': ['express', 'expressjs'],
            'django': ['django'],
            'flask': ['flask'],
            'fastapi': ['fastapi'],
            'spring': ['spring', 'spring boot'],
            'rails': ['rails', 'ruby on rails'],
            'laravel': ['laravel']
        },

        'databases':{
            'postgresql': ['postgresql', 'postgres', 'psql'],
            'mysql': ['mysql'],
            'mongodb': ['mongodb', 'mongo'],
            'redis': ['redis'],
            'elasticsearch': ['elasticsearch', 'elastic'],
            'cassandra': ['cassandra'],
            'dynamodb': ['dynamodb']
        },

        'cloud': {
            'aws': ['aws', 'amazon web services'],
            'azure': ['azure', 'microsoft azure'],
            'gcp': ['gcp', 'google cloud'],
            'docker': ['docker'],
            'kubernetes': ['kubernetes', 'k8s'],
            'terraform': ['terraform'],
            'jenkins': ['jenkins'],
            'github_actions': ['github actions', 'gh actions']
        },

        'ai_ml': {
            'machine_learning': ['machine learning', 'ml'],
            'deep_learning': ['deep learning', 'dl'],
            'tensorflow': ['tensorflow', 'tf'],
            'pytorch': ['pytorch'],
            'langchain': ['langchain'],
            'llm': ['llm', 'large language model'],
            'nlp': ['nlp', 'natural language processing'],
            'computer_vision': ['computer vision', 'cv']
        },

        'soft_skills': {
            'leadership': ['leadership', 'team lead', 'mentoring'],
            'communication': ['communication', 'presentation'],
            'problem_solving': ['problem solving', 'analytical'],
            'agile': ['agile', 'scrum', 'kanban'],
            'remote_work': ['remote', 'distributed', 'async']
        }
      }
    
    def extract_from_text(self, text:str, include_proficiency: bool =True,) -> Dict[str, Any]:
        """
        Extrcat Skills from text with profiecinecy and categories 
        """

        if not text:
            return []
        text_lower = text.lower()

        extracted ={
            'skills': [],
            'categorized': defaultdict(list),
            'proficiency_map': {},
            'total_count': 0
        }

        # Extract Skills by category
        for category, skills_dict in self.skills_taxonomy.items():
            for skill_name, synonyms in skills_dict.items():
                for synonym in synonyms:
                    if self._find_skills_in_text(synonym, text_lower):

                        # Detect Profiency
                        proficiency = 'intermediate'
                        if include_proficiency:
                            proficiency = self._detect_proficiency(synonym, text)

                        skills_info = {
                            'name':skill_name,
                            'category': category,
                            'found_as': synonym,
                            'proficiency': proficiency
                        }

                        extracted['skills'].append(skills_info)
                        extracted['categorized'][category].append(skill_name)
                        extracted['proficiency_map'][skill_name] = proficiency

                        break

        ## Remove Duplicates


        seen =set()
        unique_skills = []
        for skill in extracted['skills']:
            if skill['name'] not in seen:
                seen.add(skill['name'])
                unique_skills.append(skill)
        
        extracted['skills'] = unique_skills
        extracted['total_count'] = len(unique_skills)

        if self.nlp:
            ner_skills = self._extract_with_ner(text)
            for skill in ner_skills:
                if skill not in seen:
                    extracted['skills'].append({
                        'name':skill,
                        'category': 'other',
                        'found_as': 'skill',
                        'proficiency': 'intermediate'
                    })
        
        return extracted
    
    def _find_skills_in_text(self, skill: str, text:str) -> bool:
        """
        Find skills in text with word boundary matching
        """
        pattern = r'\b' + re.escape(skill) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    def _detect_proficiency(self, skill: str, text: str) ->str:
        """
        Detect Proficiency level based on context
        """

        ## Look for proficiency indicators

        context_window = 50

        skill_pos = text.lower().find(skill.lower())
        if skill_pos == -1:
            return 'intermediate'

        start = max(0, skill_pos - context_window)
        end = min(len(text), skill_pos + len(skill) + context_window)
        context = text[start:end].lower()


        # Checks for Proficiency Indicators
        year_match = re.search(r'(\d+)\+?\s*years?', context, re.IGNORECASE)
        if year_match:
            years = int(year_match.group(1))
            if years >=7:
                return 'expert'
            
            if years >=5:
                return 'senior'
            
            if years >=2:
                return 'intermediate'
            else:
                return 'junior'
        
        return 'intermediate'
    
    def _extract_with_ner(self, text: str) -> List[str]:
        """
        Extract Potential skills using name Entity Recognization
        """
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        skills = []

        for chunk  in doc.noun_chunks:
            if len(chunk.text) > 2 and chunk.text.lower() not in ['the', 'a', 'en']:
                skills.append(chunk.text)
        
        return skills[:10]
    
    def compare_skills(self, resume_skills: List[Dict], job_skills: List[Dict]) -> Dict:
        """
        Compare resume skills vs job requirments
        """
        critical_missing = []
        nice_to_have_missing = []
        matched = set()

        resume_skills_names = {s['name'] for s in resume_skills}
        job_skills_names = {s['name'] for s in job_skills}

        matched = resume_skills_names & job_skills_names
        missing = job_skills_names - resume_skills_names
        extra = resume_skills_names - job_skills_names

        # Calculate match percentage
        if job_skills_names:
            matched_percentage = (len(matched) / (len(job_skills_names)) * 100)
        else:
            matched_percentage = 0

        for skill in missing:
            job_skill = next((s for s in job_skills if s['name'] == skill), None)
            if job_skill and job_skill.get('category') in ['programming_languages', 'frontend', 'backend']:
                critical_missing.append(skill)
            else:
                nice_to_have_missing.append(skill)
        
        return{
            'matched_skills': list(matched),
            'matched_count': len(matched),
            'missing_skill': list(missing),
            'missing_count': len(missing),
            'critical_missing': critical_missing,
            'nice_to_have_missing': nice_to_have_missing,
            'extra_skill': len(extra),
            'matched_percentage': matched_percentage,
            'strength_score': self._calculate_strength_score(resume_skills, matched)
        }
    
    def _calculate_strength_score(self, resume_skills: List[Dict], matched_skills: Set[str])->float:
        """
        Calculate the strength score based on Proficiency level
        """
        if not matched_skills:
            return 0.0
        
        prificiency_weight = {
            'expert': 1.0,
            'senior': 0.8,
            'intermediate': 0.6,
            'junior': 0.4
        }

        total_weights = 0.0

        for skill in resume_skills:
            if skill['name'] in matched_skills:
                prof = skill.get('proficiency', 'intermediate')
                total_weights += prificiency_weight.get(prof, 0.6)

        return min(1.0 , total_weights / len(matched_skills))
    
    def build_skill_graph(self, skills: List[Dict]) ->Dict:
        """Build Skill relationship graph"""
        
        graph = defaultdict(list)

        # Default by category
        by_category = defaultdict(list)

        for skill in skills:
              category = skill.get('category', 'Uncategorized')  # use 'Uncategorized' if missing
              by_category[category].append(skill['name'])

            

        ## Build Realtionships
        relationships= {
            'complements':[],
            'require': [],
            'alternatives': []
        }

        if 'react' in [s['name'] for s in skills] and 'node.js' in [s['name'] for s in skills]:
            relationships['complements'].append(('react', 'node.js'))
        
        ## Frontend skill
        frontend_skills = by_category.get('frontend', [])
        if frontend_skills and ('html' in by_category.get('frontend', []) or 'css' in by_category.get('frontend', [])):
            for skill in frontend_skills:
                if skill not in ['html', 'css']:
                    relationships['require'].append((skill, 'html'))
                    relationships['require'].append((skill, 'css'))
        
        return {
            'category': dict(by_category),
            'relationships': relationships,
            'skill_count_by_category': {cat: len(skills) for cat, skills in by_category.items()}
        }

    async def fallback_roles(self, skills: list):
        skill_set = set([s.lower() for s in skills])

        # light inference only (NOT full domain AI)
        if any(s in skill_set for s in ["python", "react", "fastapi", "django", "node"]):
            return ["software engineer"]

        if any(s in skill_set for s in ["seo", "ads", "marketing", "content"]):
            return ["marketing specialist"]

        if any(s in skill_set for s in ["excel", "finance", "accounting"]):
            return ["finance analyst"]

        # LAST RESORT ONLY
        return ["professional"]

    async def generate_base_roles_llm(self, resume_text: str, skills: list):

        prompt = f"""
    You are a career classification AI.

    Your task:
    Convert a candidate profile into 3–6 realistic job titles.

    STRICT RULES:
    - Output ONLY valid JSON
    - No explanations
    - No extra text
    - No markdown
    - No duplicates
    - Keep roles realistic and industry-standard
    - Do NOT generate keywords or skill lists

    INPUT:

    Resume:
    {resume_text}

    Skills:
    {skills}

    OUTPUT FORMAT:
    {{
    "base_roles": [
        "role 1",
        "role 2",
        "role 3"
    ]
    }}
    """

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You output only strict JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )

            content = response.choices[0].message.content.strip()

            data = json.loads(content)

            roles = data.get("base_roles", [])

            # safety cleanup
            roles = list(set([r.strip().lower() for r in roles if r]))

            if not roles:
                logger.warning("LLM returned empty roles, fallback triggered in Skill Extractor")
                return await self.fallback_roles(skills)

            return roles

        except Exception as e:
            logger.warning("Base roles LLM failed", error=str(e))

            # fallback (VERY IMPORTANT)
            logger.warning("LLM Failed, fallback triggered in Skill Extractor")
            return await self.fallback_roles(skills)

        

 









