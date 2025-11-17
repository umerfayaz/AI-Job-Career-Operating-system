"""
Self improvement controller 
Automatically applies improvments based on meta reasoning
"""

import structlog
from typing import List, Dict, Optional
from datetime import datetime
import numpy as np

logger = structlog.get_logger()


class SelfImprovementController:
    """
    Analyzes meta_reasoning output and automatically applies improvements
    """
    def __init__(self):
        self.improvements_history = []
        self.learn_optimizations = {
            'keyword_expansions': [],
            'ranking_adjustments': {},
            'source_priorities': {},
            'skill_weights': {}
        }

        logger.info(f"Self improvements - Controller initialized ")
    
    async def analyze_and_improve(self, state: Dict, meta_reasoning: Dict)->Dict:
        """Analyze state and apply improvements"""

        logger.info(f"Analyzing Performance for improvements...")

        ## Extract Meta reasoning
        meta = meta_reasoning or {}
        if not meta:
            logger.warning(f" No meta-reasoning found - Skipping improvements")
            return state
        
        evaluation = meta.get('evaluation', {})
        insights = meta.get('insights', [])
        suggestions = meta.get('suggestions',[])

        improvements_applied = []

        # fix low search quality
        if evaluation.get('state_quality', 1.0) < 0.6:
            improvement = await self._improve_search_quality(state, evaluation)

            if improvement:
                improvements_applied.append(improvement)
                state = improvement['updated_state']
            
        # Improvment Low skill quality
        if evaluation.get('skill_coverage', 1.0) < 0.7:
            improvement = await self._improve_skill_coverage(state, evaluation)

            if improvement:
                improvements_applied.append(improvement)
                state = improvement['updated_state']
        
        # Improvment Fix low Diversity
        if evaluation.get('diversity_score', 1.0) < 0.5:
            improvement = await self._improve_diversity(state, evaluation)

            if improvement:
                improvements_applied.append(improvement)
                state = improvement['updated_state']
        
        ## Improvment apply meta-reasoning suggestions
        for suggestion in suggestions:
            improvement = await self._apply_suggestion(state, suggestion)

            if improvement:
                improvements_applied.append(improvement)
                state = improvement['updated_state']
        
        ## Improvement Learn from high performance matches
        if evaluation.get('matched_jobs'):
            improvement = await self._learn_from_success(state)

            if improvement:
                improvements_applied.append(improvement)
                state = improvement['updated_state']

        ## Store improvement
        if improvements_applied:
            logger.info(f"Applied  {len(improvements_applied)} improvements")

            state['improvements_applied']  = improvements_applied
            state['improvement_timestamp'] = datetime.now().isoformat()

            self.improvements_history.append({
                'state_id': state.get('task_id'),
                'improvements': improvements_applied,
                'timestamp': datetime.now().isoformat()
            })

            for imp in improvements_applied:
                logger.info(f" {imp['type']}: {imp['description']}")
        
        return state
    
    async def _improve_search_quality(self, state: Dict, evaluation: Dict) -> Optional[Dict]:
        """Improve search quality by adjusting parameters"""

        matched_jobs = state.get('matched_jobs', [])
        if not matched_jobs:
            # broacder serach immediatly if not matched jobs
            new_keywords = state.get('job_keywords', []) + [
                'developer', 'software', 'ml', 'engineer', 'ai', 'ml'
            ]

            state['job_keywords'] = list(set(new_keywords))
            state['location'] = 'Remote'


            return {
                'type': 'search_expansion',
                'description': 'Broader search keywords and location',
                'changes': {
                    'added_keywords': ['developer', 'engineer', 'software', 'remote', 'ai', 'ml'],
                    'location_changed': 'Remote'
                },
                'updated_state': state
            }

        else: 

            avg_score = float(np.mean([j.get('composite_score', 0) for j in matched_jobs ]))

            if avg_score < 0.5:
                state['ranking_adjustments'] = {
                    'skill_match_weight': 0.5,
                    'embedding_similarity_weight': 0.2,
                    'location_match_weight': 0.10
                }

                return {
                    'type': 'ranking_optimization',
                    'description': f" Adjusted ranking weights (avg score was{avg_score:.2f})",
                    'changes': state['ranking_adjustments'],
                    'updated_state': state
                }

        return None
    
    async def _improve_skill_coverage(self, state:Dict, evaluation: Dict) -> Optional[Dict]:
       """Improve skill allignment between resume and jobs"""

       resume_skills = state.get('resume_skills', {})
       job_skill_analysis = state.get('job_skills_analysis', [])

       if not resume_skills or not job_skill_analysis:
        return None

       ## Extract most common required skills from jobs
       all_required_skills = []
       for job_analysis in job_skill_analysis[:10]:
           comparison = job_analysis.get('skill_comparison', {})
           missing = comparison.get('missing_skills', [])
           all_required_skills.extend(missing) 
        
       ## Find most common missing skills

       from collections import Counter

       skills_count = Counter(all_required_skills)
       common_missing = [skill for skill, count in skills_count.most_common(5)]

       if common_missing:

        # Add additional keywords
          current_keywords = state.get('job_keywords', [])
          expanded_keywords = list(set(current_keywords + common_missing))


          state['job_keywords'] = expanded_keywords

          ## Also Store for learning
          self.learn_optimizations['keyword_expansions'].extend(common_missing)

          return {
              'type': 'skill_alignment',
              'description': f" Added {len(common_missing)} High Demand Skill search",
              'changes': {
                  'added_skills': common_missing,
              },
              "updated_state": state
           }

       return None
    
    async def _improve_diversity(self, state: Dict, evaluation: Dict) -> Optional[Dict]:
        """Improve diversity of search results"""

        ## Enable alternative job sources
        state['enable_alternative_sources'] = True
        state['max_results_per_source'] = 15

        # Vary search parameters sligtly
        keywords = state.get('job_keywords', [])

        if keywords:
            expanded = keywords.copy()

            keyword_synonyms = {
                'developer': ['engineer', 'code', 'programmer'],
                'ai': ['artificial_intelligence', 'machine learning', 'ml', 'agentic', 'generative', 'automation' ],
                'remote': ['distributed', 'work_from_home', 'wfh']
            }

            for keyword in keywords[:3]:
                if keyword in keyword_synonyms:
                    expanded.extend(keyword_synonyms[keyword])
            
            state['job_keywords'] = list(set(expanded))

            return {
                'type': 'diversity_enhancement',
                'description': 'Enable alternative sources and expanded keyword synonyms',
                'changes': {
                    'alternative_sources': True,
                    'keyword_expansion': len(expanded) - len(keywords)
                },
                'updated_state': state
            }
        return None
    
    async def apply_suggestion(self, state: Dict, suggestion: str) -> Optional[Dict]:
        """Apply suggestion for meta reasoner"""

        suggestion_lower = suggestion.lower()

        if 'keyword' in suggestion_lower or 'search' in suggestion_lower:
            potential_skills = self._extract_skills_from_text(suggestion)

            if potential_skills:
                current_keywords = state.get('job_keywords', [])
                state['job_keywords'] = list(set(current_keywords + potential_skills))

                return {
                    'type': 'suggestion_applied',
                    'description': f' Applied meta-reasoner suggestion: {suggestion[:50]}',
                    'changes': {
                        'added_keywords': potential_skills
                    },
                    'updated_state': state
                }

        elif 'location' in suggestion_lower or 'expand' in suggestion_lower:
            state['job_location'] = 'Remote'

            return {
                'type': 'suggestion_applied',
                'description': 'Expand location to Remote based on suggestion',
                'changes': {'location': 'Remote'},
                'updated_state': state
            }
        
        return None

    async def _learn_from_success(self, state: Dict ) -> Optional[Dict]:
        """Learn from High-Performing job matches"""

        matched_jobs = state.get('matched_jobs', [])

        if not matched_jobs:
            return None
        
        top_jobs = [j for j in matched_jobs if j.get('composite_score', 0) >=0.75]

        if not top_jobs:
            return None

        successful_patterns = {
            'companies': [],
            'titles': [],
            'locations': [],
            'sources': []
        }


        for job in top_jobs:
            successful_patterns['companies'].append(job.get('company', ''))
            successful_patterns['titles'].append(job.get('title', ''))
            successful_patterns['locations'].append(job.get('location', ''))
            successful_patterns['sources'].append(job.get('source',''))

        # Prioritized these source for future
        from collections import Counter
        best_sources = Counter(successful_patterns['sources']).most_common(2)

        for source, count in best_sources:
            self.learn_optimizations['source_priorities'][source] = count / len(top_jobs)

        ## Extract keywords from job title
        title_keywords =[]
        for title in successful_patterns['titles']:
            words = title.lower().split()
            title_keywords.extend([w for w in words if len(w) > 3])

        common_title_keywords = [
            word for word, count in Counter(title_keywords).most_common(3)
        ]

        if common_title_keywords:
            self.learn_optimizations['keyword_expansions'].extend(common_title_keywords)
        
        return {
            'type': 'success_learning',
            'description': f' Learn patterns from {len(top_jobs)} High-Performing matches',
            'changes': {
                'successful_sources': [s for s, _ in best_sources],
                'learned_keywords': common_title_keywords
            },
            'updated_state': state
        }
    
    def _extract_skills_from_text(self, text:str) ->List[str]:
        """Extract Potential skill keywords from text"""

        common_skills = [
            'python', 'javascript', 'react', 'aws', 'node', 'docker',
            'kubernetes', 'java', 'go', 'rust', 'typescript', 'sql',
            'postgresql', 'mongodb', 'redis', 'django', 'flask', 'fastapi',
            'langgraph', 'crewai', 'agents' 
        ]

        text_lower = text.lower()
        found_skills = [skill for skill in common_skills if skill in text_lower]

        return found_skills
    
    def get_improvement_report(self) ->str:
        """Generate report of all improvements made"""

        if not self.improvements_history:
            return "No improvments made yet"
        
        report = f"""

    # Self improvement Report

    Total improvements Sessions: {len(self.improvment_history)}
    Total improvements Applied: {sum(len(h['improvments']) for h in self.improvement_history)}

    ## Recent Improvements History
    """

        for session in self.improvement_history[-5:]:
           report += f"\n### Session: {session['timestamp']}\n"
        for imp in session['improvements']:
            report += f"{imp['type']}: {imp['description']}\n"

        report +=f"""

    ## Learned Optimizations

    keyword Expansions: {len(self.learn_optimizations['keyword_expansions'])}
    - {', '.join(self.learn_optimizations['keyword_expansions'][:10])}

    Source Priorities: {len(self.learn_optimizations['source_priorities'])}
    """

        for source, priority in self.learn_optimizations['source_priorities'].items():
            report += f"- {source}: {priority:.1%}\n"

        return report
    
    def export_learned_config(self,)->Dict:
        """Export Learned Optimization as Configuration"""

        return {
            'version': '1.0',
            'timestamp': datetime.now().isoformat(),
            'optimizations': self.learn_optimizations,
            'performance_metrics': {
                'total_improvements': len(self.improvements_history),
                'avg_improvements_per_session': float(np.mean([
                    len(h['improvements']) for h in self.improvements_history
                ])) if self.improvements_history else 0
            }
        }


    



















            








        



