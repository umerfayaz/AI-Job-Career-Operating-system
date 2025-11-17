"""Agentic Orchestrator"""

import asyncio
from typing import Callable,Dict, Optional
from ..core.memory_system import MemoryRAGSystem
from datetime import datetime
import structlog
import json
from pathlib import Path

logger = structlog.get_logger()

class AgentOrchestrator:
    """Main Orchestrator that combines all agentic Goals"""
    def __init__(self, agent_graph, goal_manager, autonomous_planner, improvement_controller):

        self.agent_graph =agent_graph
        self.goal_manager = goal_manager
        self.planner = autonomous_planner
        self.memory_system = MemoryRAGSystem()
        self.improvement = improvement_controller

        self.is_running = False
        self.run_history =[]
        self.autonomous_decisions = 0

        logger.info(f" Agentic Orchestrator Initialized")
    
    def generate_meta_reasoning(self, result_state: Dict, goal_evaluation: Dict) -> Dict:
        """
        Generate structured meta-reasoning for the last cycle
        """
        meta = {
            'goal_progress': goal_evaluation.get('progress', 0),
            'goal_achieved': goal_evaluation.get('achieved', False),
            'matched_jobs_count': len(result_state.get('matched_jobs', [])),
            'skill_coverage': result_state.get('skill_coverage', 0),
            'diversity_score': result_state.get('diversity_score', 0),
            'issues': []
        }

        if meta['skill_coverage'] < 0.7:
            meta['issues'].append('low_skill_coverage')
        if meta['diversity_score'] < 0.6:
            meta['issues'].append('low_diversity')

        result_state.setdefault('meta_reasoning', []).append(meta)
        return meta


    async def run_autonomous_cycle(self, initial_state: Dict, continuous: bool = False, max_cycles: int =10) -> Dict:
        """
        Run Fully autonous cycle
        """
        logger.info(" Starting full autonomous cycle")

        cycle = 0
        current_state = initial_state
        goal_achieved = False

        ## Create goal
        goal = self.goal_manager.create_goal_from_task(current_state)
        self.goal_manager.active_goal.append(goal)

        logger.info(f" Goal {goal.description}")
        logger.info(f"Success Criteria: {goal.success_criteria}")

        while cycle < max_cycles and not goal_achieved:
            cycle += 1
            logger.info(f"\n{'='*60}")
            logger.info(f" Autonomous Cycle {cycle}/ {max_cycles}")
            logger.info(f"{'='*60}\n")

            # Step 1 execute agent with current state
            logger.info("Executing agent workflow...")
            result_state = await self._execute_agent_intelligently(current_state)

            # Step 2 evaluate Goal Progress
            logger.info(F" Evaluating goal Progess...")
            goal_evaluation = goal.evaluate(result_state)

            meta = self.generate_meta_reasoning(result_state, goal_evaluation)

            logger.info(f" Goal Progress: {goal_evaluation['progress']:.1%}")
            logger.info(f" Goal Achieved: {goal_evaluation['achieved']}")

            for reason in goal_evaluation.get('reason', []):
                logger.info(f"  {reason}")

            ## Check if goal achieved
            if goal_evaluation['achieved']:
                logger.info(" Goal Achieved")
                goal_achieved = True
                result_state['goal_achieved'] = True
                result_state['cycles_required'] = cycle
                break

            ## Step 4 Apply self improvements
            if cycle < max_cycles:
                logger.info(" Applying Self Improvements...")
                result_state = await self.improvement.analyze_and_improve(result_state, meta)

            ## Step 5 Autonomous planning for next cycle
            if continuous and cycle < max_cycles:
                logger.info("Planning Next Continous action....")


                next_action, reasoning = self.planner.decide_next_action(
                    result_state,
                    goal_evaluation
                )

                logger.info(f" Next action: {next_action}")
                logger.info(f" Confidence {reasoning['confidence']:.1%}")

                ## Apply goal adjustments

                adjustments = goal.suggest_adjustments(result_state, goal_evaluation)

                if adjustments:
                    logger.info(f" Applying {len(adjustments)} goal adjustments ....")

                    for adj in adjustments:
                        logger.info(f" {adj['action']} {adj['reason']}")
                        result_state = self.goal_manager._apply_adjustments(
                            result_state, adj
                        )
                
                self.autonomous_decisions += 1

                ## Update for next cycle
                current_state = result_state
                current_state['autonomous_cycle'] = cycle

                ## Store in history
                self.run_history.append({
                    'cycle': cycle,
                    'goal_progress': goal_evaluation['progress'],
                    'improvements_applied': len(result_state.get('improvements_applied', [])),
                    'autonomous_decision': self.autonomous_decisions,
                    'timestamp': datetime.now().isoformat()
                })

                if not continuous:
                    break

                ## Final Reporting

            logger.info(f"\n{'='*60}")
            logger.info("Autonomous Cycle Complete")
            logger.info(f"{'='*60}")
            logger.info(f"Total Cycle {cycle}")
            logger.info(f" Goal achieved {goal_achieved}")
            logger.info(f"Autonomous Decisions made: {self.autonomous_decisions}")


            result_state['autonomous_execution'] = {
                'goal_achieved': goal_achieved,
                'total_cycles': cycle,
                'autonomous_decision': self.autonomous_decisions,
                'final_progress': goal_evaluation['progress'],
                'run_history': self.run_history
            }


                ## Generate Report
            result_state['goal_report'] = self.goal_manager.get_goal_report(goal)
            result_state['planning_report'] = self.planner.get_decision_report()
            result_state['improvement_report'] = self.improvement.get_improvement_report()

            return result_state

    async def _execute_agent_intelligently(self, state: Dict) ->Dict:
        """Execute agent with intelligent routing"""


        # Fix Add Recursion Limit

        config = {
            "configurable":{
                "thread_id": state.get('task_id', 'default')
            },
            "recursion_limit":50
        }
        ### Existing graph execution

        result = await self.agent_graph.graph.ainvoke(state, config)

        return result

    async def run_continous_montitoring(self, user_id:str, check_interval_hours: int = 24, callback: Optional[Callable] = None):
        """
        Run agent continously in the background
        Check for new opportunities
        """

        logger.info(f" Starting continous monitoring for user {user_id}")
        logger.info(f" Checking for interval hours: {check_interval_hours}")

        self.is_running = True
        last_check = datetime.now()

        while self.is_running:

            try:
                # Wait for interval

                await asyncio.sleep(check_interval_hours * 420)

                logger.info(f" Scheduled check triggered for {user_id}")

                ## Create a state for background checl

                state = {
                    'task': f'Find new job opportunities for user {user_id}',
                    'task_type':'job_matching',
                    'task_id': f'auto_{user_id}_{datetime.now().timestamp()}',
                    'user_id': user_id,
                    'priority': 5,
                    'iteration': 0,
                    'max_iteration':3,
                    'autonomous_mode': 0
                }

                ## Load User resum's and preferences from memory

                state = await self._load_user_context(user_id, state)

                result = await self.run_autonomous_cycle(
                    state,
                    continuous= True,
                    max_cycles= 3,
                )

                new_matches = result.get('matched_jobs', [])
                high_quality  = [j for j in new_matches if j.get('composite_score', 0) >=0.7]

                if high_quality:
                    logger.info(f" Found {len(high_quality)} high-quality matches")
                
                   # Notify user via callbacl

                    if callback:
                       await Callable(user_id, high_quality, result)

                last_check = datetime.now()

            except Exception as e:
                logger.error(f" Error in continous monitoring {e}")
                await asyncio.sleep(300)
    
    async def _load_user_context(self, user_id: str, state: Dict) ->Dict:
        """Load user's resume and preferences from memory"""

        resume_text = state.get('resume_text', '')
        current_jobs = state.get('current_jobs', [])


        ## Calling existing rag context memory file
        rag_context = await self.memory_system.get_rag_context_for_matching(
            user_id =user_id,
            current_jobs = current_jobs,
            resume_text =resume_text
        ) 

        state["rag_context"] = rag_context
        state["similar_resumes"] = rag_context.get("similar_resumes", [])
        state["similar_jobs"] = rag_context.get("similar_jobs", [])
        state["match_history"] = rag_context.get("match_history", [])
        state["user_preferences"] = rag_context.get("user_preferences", {})
        state["context_quality"] = rag_context.get("context_quality", 0)

        return state

    
    def stop_monitoring(self):
        """Stop continous monitoring"""
        self.is_running = False
        logger.info("Stopping Continous Monitoring")
    
    def get_comprehensive_report(self):
        """Generate Comprehensive report of all agentic Activities"""

        report = f"""
    # Agentic agent - Comprehensive report
    Generated: {datetime.now().isoformat()}

    ## Autonmous execution summary
    - Total Autonomous Decisions: {self.autonomous_decisions}
    - Cycles executed: {len(self.run_history)}
    - Currently Running:{self.is_running}

    ## Goal Management
    {self.goal_manager.get_goal_report(self.goal_manager.active_goal[0] if self.goal_manager.active_goal else "No active goals")}

    # Autonomous Planner
    {self.planner.get_decision_report()}

    ## Self-Improvement
    {self.improvement.get_improvement_report()}

    ## Run History
         
    """
        for run in self.run_history[-10:]:
            report += f"""
         {run.get('cycle')}
    - Goal Progress: {run.get('goal_progress'):.2f}
    - Improvements: {run.get('improvements_applied')}
    - Time: {run['timestamp']}
    """
        return report

    def export_state(self, filepath: str):
        """Export agent state for persistance"""

        export_data = {
            'timestamp': datetime.now().isoformat(),
            'autonomous_decisions': self.autonomous_decisions,
            'run_history': self.run_history,
            'learned_optimizations': self.improvement.export_learned_config(),
            'node_performance': self.planner.node_performance
        }

        Path(filepath).write_text(json.dumps(export_data, indent=2))
        logger.info(f"Agent Exported {filepath}")

    def load_state(self, filepath:str):
        """Load Previous saved agent state"""


        data = json.loads(Path(filepath).read_text())

        self.autonomous_decisions = data.get('autonomous_decisions', 0)
        self.run_history = data.get('run_history', [])

        if 'learned_optimizations' in data:
            self.improvement.learned_optimizations = data['learned_optimizations'].get('optimizations', {})
        
        if 'node_planner' in data:
            self.planner.node_performance = data['node_performance']
        
        logger.info(f" Agent state learned from {filepath}")
    


       
                

















