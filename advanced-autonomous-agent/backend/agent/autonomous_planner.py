"""
Autonomous Planning Engine
Makes routing descision dynamiticlly based on state and goals
"""
import structlog
from typing import List, Dict, Optional , Tuple
from datetime import datetime
import numpy as np


logger = structlog.get_logger()

class AutonomousPlanner:
    """
    Dynamic Planner that Decides actions based on":
    - Current State
    - Goal Progress
    - Hitorical Performance
    - Meta-reasonong output
    """
    def __init__(self, agent_nodes):
        self.nodes = agent_nodes


        ## Nodes effectiveness tracking
        self.node_performance = {
            'job_scraper': {'success_rate': 0.8, 'avg_quality': 0.7 },
            'job_matcher': {'success_rate': 0.85, 'avg_quality': 0.75},
            'skill_analysis': {'success_rate': 0.9, 'avg_quality': 0.8},
            'intelligent_ranker': {"success_rate": 0.85, 'avg_quality': 0.8}
        }

        self.decision_history = []

        logger.info(f"Autonomous Planner Initialized")

    def decide_next_action(self, state:Dict, goal_evaluation: Optional[Dict] = None) -> Tuple[Dict, str]:
        """
        Decide next node to execute based on state analysis
        """

        decision_reasoning = {
            'timestamp': datetime.now().isoformat(),
            'state_analysis': self._analyze_state(state),
            'options_considered': [],
            'decision': None,
            'confidence': 0.0
        }

        ## Get Current Context
        workflow = state.get('task_type', 'research')
        current_node = state.get('last_executed_node', None)
        iteration = state.get('iteration', 0)


        ## Job Workflow decisions
        if workflow in ['job_matching', 'job_search', 'career']:
            decision = self._decide_job_workflow(state, goal_evaluation, decision_reasoning)
        
        else:
            decision = self._decide_research_workflow(state, goal_evaluation, decision_reasoning)

            ## log decision
        decision_reasoning['decision'] = decision
        self.decision_history.append(decision_reasoning)

        logger.info(f" Decision execute: {decision}  (confidence: {decision_reasoning['confidence']:.2f})")
        logger.info(f" Reason: {decision_reasoning.get('primary_reason', 'N/A')}")

        return decision , decision_reasoning

    def _decide_job_workflow(self, state: Dict, goal_eval: Optional[Dict], reasoning: Dict) ->str:
        """Decide next action in job workflow"""


        ## State Analysis
        matched_jobs = state.get('matched_jobs', [])
        jobs_count = len(matched_jobs)
        quality = state.get('quality_check', {})
        meta = state.get('meta_reasoning', {})
        iteration = state.get('iteration', 0)
        retry_count = state.get('retry_count', 0)


        MAX_RETRIES =3
        MAX_ITERATIONS = 10

        if retry_count >= MAX_RETRIES:
            reasoning['primary_reason'] = f" Max retries ({MAX_RETRIES}) reached - Generating report"
            reasoning['confidence'] = 0.5
            return 'job_report_generator'

        ## Safety Stop if too many iteration
        if iteration >= MAX_ITERATIONS:
            reasoning['primary_reason'] = f" Max Iterations ({MAX_ITERATIONS}) reached - Finalizing"
            reasoning['confidence'] = 0.5
            return 'job_report_generator'

        options = []

        if jobs_count < 5 and retry_count < MAX_RETRIES:
            options.append({
                'action': 'job_scraper',
                'score': 0.9,
                'reason': f"Only {jobs_count} jobs - retry {retry_count + 1}/{MAX_RETRIES}"
            })

        # Options 2
        if jobs_count > 0 and jobs_count < 15:
            avg_score = np.mean([j.get('composite_score', 0) for j in matched_jobs])
            if avg_score < 0.6:
                options.append({
                    'action': 'skills_analysis',
                    'score': 0.95,
                    'reason': f"Low match quality: ({avg_score:.2f}) - refine skills"
                })

        
        ## Options Rerank with adjusted weights
        if goal_eval and goal_eval.get('progress', 0) < 0.7:
            options.append({
                'action': 'intelligent_ranker',
                'score': 0.75,
                'reason': 'Goal Progress <70& - adjust ranking'
            })

        ## Option 4 quality check 
        if jobs_count >=10 and not quality:
            options.append({
                'action': 'job_quality_checker',
                'score': 0.95,
                'reason': "Have Enough jobs - validate quality"
            })
        

        # Option 5 meta reasoning to evalute stretgy
        if state.get('iteration', 0) and not meta:
            options.append({
                'action': 'meta_reasoner',
                'score': 0.8,
                'reason': ' Multiple iterations -  need eval stretegy'
            })
        

        ## Genrate report if quality passed
        if quality.get('passed', False) or jobs_count >=15:
            options.append({
                'action': 'job_report_generator',
                'score': 0.7,
                'reason': 'quality validate or sufficient jobs'
            })
        
        ## Option 7 Memory Learning after Successfull matching
        if matched_jobs and not state.get('learning_completed'):
            options.append({
                'action': 'memory_learning',
                'score': 0.65,
                'reason': 'store Successful matches for future'
            }) 
        
        ## Select Best Options
        if options:
            best =  max(options, key =lambda x: x['score'])
            reasoning['confidence'] =best['score']
            reasoning['primary_reason'] =best['reason']
            return best['action']

        # Default Continue flow
        return 'job_report_generator'
    
    def _decide_research_workflow(self, state: Dict, goal_eval: Optional[Dict], reasoning: Dict) ->str:
        """Decide Next Action in research workflow"""

        insights = state.get('extracted_insights', [])
        confidence = state.get('confidence_score', 0)
        iteration = state.get('iteration', 0)


        options = []

        # Option 1 Need more data
        if len(insights) < 3:
            options.append({
                'action': 'researcher',
                'score': 0.9,
                'reason': f' {len(insights)} insights need more data'
            })
        
        ## Option 2 Analyze Collected Data
        if state.get('research_results') and len(insights) <5:
            options.append({
                'action': 'analyzer',
                'score': 0.85,
                'reason': 'Have research results - extract insights'
            })
        
        ## Option 3 Meta reasoning
        if iteration >2 and confidence < 0.7:
            options.append({
                'action': 'reasoner',
                'score': 0.8,
                'reason': 'Multiple iterations, low confidence  - reflect'
            })
        
        #  OPtions 4 Generate if confidence
        if confidence >=0.75 or len(insights) >=5:
            options.append({
                'action': 'generate',
                'score': 0.95,
                'reason': f' High Confidence {confidence:.2f} or insufficient insights'
            })
        
        ## Option 5 - Re-plan if stuck
        if iteration >=4 and confidence <=0.5:
            options.append({
                'action': 'planner',
                'score': 0.7,
                'reason': 'Stuck with low confidence - re-plan stretegy'
            })
        
        reasoning['options_considered'] = options

        if options:
            best = max(options, key= lambda x: x['score'])
            reasoning['confidence'] = best['score']
            reasoning['primary_reason'] = best['reason']
            return best['action']
        
        return 'generator'
    
    def _analyze_state(self, state: Dict) ->str:
        """Analyze current state to inform Decisions"""

        analysis = {
            'data_sufficiency': 0.0,
            'quality_level': 0.0,
            'confidence_level': state.get('confidence_score', 0),
            'iteration_count': state.get('iteration', 0),
            'errors_count': len(state.get('errors', [])),
            'bottlenecks': []
        }

        ## Job workflow analysis
        if 'matched_jobs' in state:
            jobs_count = len(state.get('matched_jobs',[]))
            analysis['data_sufficiency'] = min(1.0, jobs_count /10)

            if jobs_count > 0:
                avg_score = np.mean([
                    j.get('composite_score', 0)
                    for j in state['matched_jobs']
                ])

                analysis['quality_level'] =avg_score

            if jobs_count <5:
                analysis['bottlenecks'].append('insufficient_jobs')
            
            if analysis['quality_level'] < 0.6:
                analysis['bottlenecks'].append('low_match_quality')
            
            ## Research Workflow Analysis

            if 'extracted_insights' in state:
                insights_count = len(state.get('extracted_insights', []))
                analysis['data_sufficiency'] = min(1.0, insights_count /6)

                if insights_count < 3:
                    analysis['bottlenecks'].append('insufficient_insights')
            
            ## Common checks
            if analysis['errors_count'] > 3:
                analysis['bottlenecks'].append('High_error_count')
            
            if analysis['iteration_count'] > 5:
                analysis['bottlenecks'].append('too_many_iterations')
            
            return analysis
        
    def learn_from_outcomes(self, node: str, state: Dict, success: bool):
        """
        Learn From node execution outcomes
        """
        if node not in self.node_performance:
            self.node_performance[node] = {
                'success_rate': 0.5,
                'avg_quality': 0.5,
                'execution_count': 0
            }

            perf = self.node_performance[node]
            perf['execution_count'] = perf.get('execution_count', 0) + 1

            # Update success rate (moving average)
            alpha = 0.3
            if success:
                perf['success_rate'] = (1 - alpha) * perf['success_rate'] + alpha * 1.0
            else:
                perf['success_rate'] = (1- alpha) * perf['success_rate'] + alpha * 0.0
            

            ## Update quality check (if available in state)
            if 'quality_check' in state:
                quality = state['quality_check'].get('quality_score', 0.5)
                perf['avg_quality'] = (1 - alpha) * perf['avg_quality'] + alpha * quality

            logger.debug(f" Node {node} Performance Success={perf['success_rate']:.2f} quality={perf['avg_quality']:.2f}")
    
    def get_decision_report(self) -> str:
         """Generate report of autonomous decisions made"""

         if not self.decision_history:
            return "No decision made yet."

         report = f"""
    # Autonomous Planning Report

        Total Decisions: {len(self.decision_history)}

    ## Decision Timeline
    """
         for i, decision in enumerate(self.decision_history[-10:], 1):
            report += f"""
    {i}. Action: {decision.get('decision', 'N/A')}
    - Confidence: {decision.get('confidence', 0):.2%}
    - Reason: {decision.get('primary_reason', 'N/A')}
    - Options Considered: {len(decision.get('options_considered', []))}
    """
         return report


class DynamicRouter:
    """
    Dynamic Router for bigger decision-making.
    Routes agent behavior dynamically based on current state and goals.
    """

    def __init__(self, planner: AutonomousPlanner):
        self.planner = planner

    def route(self, state: Dict, goal_evaluation: Optional[Dict] = None) -> str:
        """Dynamic Routing function to replace static conditions"""

        next_node, reasoning = self.planner.decide_next_action(state, goal_evaluation)

        # Store routing decisions in state for transparency
        if 'routing_history' not in state:
            state['routing_history'] = []

        state['routing_history'].append({
            'from_node': state.get('last_executed_node', 'START'),
            'to_node': next_node,
            'reasoning': reasoning,
            'timestamp': datetime.now().isoformat()
        })

        # Update last executed node
        state['last_executed_node'] = next_node

        return next_node
    
def wrap_node_with_learning(node_func, node_name: str, planner: AutonomousPlanner):
    """Wraps exisitng node functions to add learning capability"""

    async def wrapped_node(self, state:dict) ->str:
        
        try:
            result_state = await node_func(state)

            ## Learn from success
            planner.learn_from_outcomes(node_name, result_state, success=True)

            return result_state
        except Exception as e:
            logger.error(f"Node {node_name} failed: {e}")
        
        planner.learn_from_outcomes(node_name, state, success=False)

        raise

    
    return wrapped_node

        



    

