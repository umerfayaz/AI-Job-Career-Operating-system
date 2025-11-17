"""
Goal manager System for agentic Ai
"""
import structlog
from typing import List, Dict , Optional , Callable
from datetime import datetime
from enum import Enum
import asyncio

logger = structlog.get_logger()

class GoalStatus:
    """Goal LifeCycle"""
    PENDING ="pending"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    FAILED = "failed"
    ADJUSTED = "adjusted"

class Goal:
    """Represents an autonomous goal with criteria"""

    def __init__(
       self,
       goal_id: str,
       description: str,
       success_criteria: Dict,
       priority: int =5,
       max_iteration: int =5,
       timeout_minutes: int =30
    ):

       self.goal_id = goal_id
       self.description = description
       self.success_criteria = success_criteria
       self.priority = priority
       self.max_iteration = max_iteration
       self.timeout_minutes = timeout_minutes

       self.status = GoalStatus.PENDING
       self.created_at = datetime.now()
       self.attempts = 0
       self.adjustments = []
       self.reasoning_log= []
    
    def evaluate(self, state: Dict) ->Dict:
        """
        Evalauate if Goal is achieved based on state
        """

        results = {
            'achieved': True,
            'progress': 0.0,
            'reason': [],
            'criteria_met': {}
        }

        criteria_count = len(self.success_criteria)
        met_count = 0

        for criterion , threshold in self.success_criteria.items():
            met = self._check_criterion(criterion, threshold, state)
            results['criteria_met'][criterion] =met

            if met:
                met_count +=1
                results['reason'].append(f"{criterion} met ({threshold})")
            else:
                results['achieved'] = False
                results['reason'].append(f"{criterion} not met {threshold}")
        
        results['progress'] = met_count / criteria_count if criteria_count > 0  else 0

        return results
    
    def _check_criterion(self, criterion: str, threshold, state:Dict) -> bool:
        """"Check Individual Success Criteria"""

        ## JOb matching criteria
        if criterion == 'min_matched_jobs':
            return len(state.get('matched_jobs', [])) >=threshold
        
        elif criterion  == 'min_composite_score':
            jobs = state.get('matched_jobs', [])
            if not jobs:
               return False
            avg_score = sum(j.get('composite_score', 0) for j in jobs) / len(jobs)
            return avg_score >=threshold

        elif criterion == 'min_skill_coverage':
            meta = state.get('meta_reasoning', {})
            eval_data = meta.get('evaluation', {})
            coverage = eval_data.get('skill_coverage', 0)
            return coverage >= threshold

        elif criterion == 'min_diversity_score':
            meta = state.get('meta_reasoning', {})
            eval_data = meta.get('evaluation', {})
            diversity = eval_data.get('diversity_score', 0)
            return diversity >=threshold

        elif criterion == 'min_quality_score':
            quality = state.get('quality_check', {})
            return quality.get('quality_score', 0) >=threshold
        
        elif criterion == 'max_critical_missing_skills':
            job_skills = state.get('job_skills_analysis', [])
            if not job_skills:
                return True
            max_missing = max(
                len(j.get('skill_comparison',{}).get('critical_missing', []))
                for j in job_skills
            )
            return max_missing <=threshold

            ## Research workflow criteria 
        elif criterion == 'min_insights':
            return len(state.get('extracted_insights', [])) >=threshold
        
        elif criterion  == 'min_confidence':
            return state.get('confidence_score', 0) >=threshold

        return False
    
    def suggest_adjustments(self, state:Dict, evaluation: Dict) ->List[Dict]:
        """Suggest Adjustments to achieve goal based on current state"""

        adjustments = []

        ## Low matched jobs
        if not evaluation['criteria_met'].get('min_matched_jobs', True):
            adjustments.append({
                'action': 'expand_search',
                'reason': 'Insufficient matchedjobs',
                'params':{
                    'add_keywords': ['developer','engineer', 'remote'],
                    'broader_search': True
                }
            })

            ## Low composite Scroe
            if not evaluation['criteria_met'].get('min_composite_score', True):
                adjustments.append({
                    'action': 'adjust_ranking_weights',
                    'reason': 'Low match quality',
                    'params': {
                        'increase_skill_weight': 0.5,
                        'reduce_location_weight': 0.1
                    }
                })

            ## Low Skill Coverage
            if not evaluation['criteria_met'].get('min_skill_coverage', True):
                adjustments.append({
                    'action': 'refine_skill_coverage',
                    'reason': 'poor skill alignment',
                    'params': {
                        'extract_more_skills': True,
                        'include_related_skills': True
                    }
                })

            ## low Diversity
            if not evaluation['criteria_met'].get('min_diversity_score', True):
                adjustments.append({
                    'action': 'diversity_score',
                    'reason':'Results too concentrated',
                    'params': {
                        'enable_alternative_sources': True,
                        'vary_search_parameters': True
                    }
              })
            
            return adjustments
    
class GoalManager:
        """
        Manages the goals and drives the autonomous agent behavior
        """
        def __init__(self, agent_graph, max_goal_iterations: int =5):
            self.agent_graph = agent_graph
            self.max_goal_iterations = max_goal_iterations

            self.active_goal: List[Goal] = []
            self.completed_goals: List[Goal] = []

            logger.info("Goal manager Initilized")

        def create_goal_from_task(self, state:Dict) ->Dict:
            """Automatically create approporiate goal based on task type"""

            task_type = state.get('task_type', '').lower()

            if task_type in ['job_matching', 'job_search', 'career']:
                return Goal(
                    goal_id = f"job_goal_{state['task_id']}",
                    description = f" Find high quality jobs for: {state['task'][:50]}",
                    success_criteria = {
                        'min_matched_jobs': 10,
                        'min_composite_score': 0.65,
                        'min_skill_coverage': 0.7,
                        'min_diversity_score': 0.6,
                        'max_critical_missing_skills': 2
                    },
                    priority =9,
                    max_iteration =4
                )

            else :
                return Goal (
                    goal_id = f"reasearch_goal_{state['task_id']}",
                    description = f"Research and analyze: {state['task'][:50]}",
                    success_criteria={
                        'min_insights': 5,
                        'min_confidence': 0.7,
                    },
                    priority =7,
                    max_iterations =3
                )
        
        async def execute_with_goal(self, state:Dict) ->Dict:
            """Execute agent with goal oreinted autonomy"""

            goal = self.create_goal_from_task(state)
            self.active_goal.append(goal)
            goal.status = GoalStatus.IN_PROGRESS


            logger.info(f"Starting goal oriented execution {goal.description}")
            logger.info(f"Success Criteria: {goal.success_criteria}")

            iteration = 0

            while iteration < goal.max_iterations:
                iteration += 1
                goal.attempts = iteration

                logger.info(f" Goal  iteration {iteration}/ {goal.max_iterations}")


                result_state = await self._execute_agent_workflow(state)

                ## Evaluate Goal Achievement
                evaluation = goal.evaluate(result_state)

                logger.info(f"Progress {evaluation['progress']:.1%}")
                for reason in evaluation['reason']:
                    logger.info(f" {reason}")
                    goal.reasoning_log.append({
                        'iteration': iteration,
                        'evaluation': evaluation,
                        'state_snapshot': {
                            'matched_jobs': len(result_state.get('matched_jobs', [])),
                            'confidence': result_state.get('confidence_score', 0)
                        },
                        'timestamp': datetime.now().isoformat() 
                    })

                    ## Check if Gaol Achieved
                    if evaluation['achieved']:
                        goal.status = GoalStatus.ACHIEVED
                        self.completed_goals.append(goal)
                        logger.info(f" Goal Achieved: {iteration}")


                        ## Add goal achievements to state
                        result_state['goal_achieved'] = True
                        result_state['goal_iterations'] = iteration
                        result_state['goal_reasoning'] = goal.reasoning_log

                        return result_state
                    
                    ## Suggest and apply Adjustmenta
                    adjustments = goal.suggest_adjustments(result_state, evaluation)

                    if adjustments and iteration < goal.max_iterations:
                        logger.info(f" Applying {len(adjustments)} adjustments...")
                    
                        for adj in adjustments:
                            logger.info(f" {adj['action']}: {adj['reason']}")
                            state = self._apply_adjustment(state, adj)
                            goal.adjustments.append(adj)

                        goal.status = GoalStatus.ADJUSTED

                        continue

                    else:

                        ## MAX iteration reahe
                        logger.info (f" Goal not fully achieved {iteration} iterations")
                        goal.status = GoalStatus.FAILED

                        result_state['goal_achieved'] = False
                        result_state['goal_progress'] = evaluation['progress']
                        result_state['goal_reasoning'] = goal.reasoning_log

                        return result_state
        
            return result_state
        
        async def _execute_agent_workflow(self, state: Dict) ->Dict:
            """Execute the existing agent graph"""
            result = await self.agent_graph.graph.ainvoke(state)

            return result
        
        def _apply_adjustments(self, state: Dict, adjustments: Dict) ->Dict:
            """Apply Suggested Adjustments to State"""

            action = adjustments['action']
            params = adjustments['params']

            # ADD More Keywords
            if action == 'expand_search':
                current_keywords = state.get('job_keywords', [])
                new_keywords = params.get('add_keywords', [])
                state['job_keywords'] = list(set(current_keywords + new_keywords))

                ## Broader Loation
                if params.get('broader_location'):
                    state['job_location'] = 'Remote'
                
            elif action ==  'adjust_ranking_weights':
                state['ranking_adjustments'] = params
            
            elif action == 'refine_skill_keywords':
                state['deep_skill_extraction'] = True
            
            elif action == 'diversity_sources':
                state['enable_alternative_sources'] = True
            
            state['retry_count'] = state.get('retry_count', 0) + 1

            return state
        
        def get_goal_report(self, goal: Goal) ->str:
            """Generate human readable_goal achievement report"""

            report = f"""

        # Goal Achievement Report

              Goal: {goal.description}
              Status: {goal.status.upper()}
              Attempts: {goal.attempts}/{goal.max_iteration}
           """
            for criterion, threshold in goal.success_criteria.items():
                report += f" {criterion}: {threshold}\n"

            if goal.reasoning_log:
                last_eval = goal.reasoning_log[-1]['evaluation']
                report += f"\n## Final Progress: {last_eval['progress']:.1%}\n\n"
                for reason in last_eval['reason']:
                    report += f"{reason}\n"
            
            if goal.adjustments:
                report += f"\n## Adjustments made ({len(goal.adjustments)})\n"
                for i, adj in enumerate(goal.adjustments, 1):
                    report += f"{i} {adj['action']}: {adj['reason']}\n"
            
            return report
