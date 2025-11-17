from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .autonomous_planner import AutonomousPlanner, DynamicRouter 
from .nodes import AgentNodes
from .state import AgentState
import structlog
from langgraph.checkpoint.memory import MemorySaver
logger = structlog.get_logger()
class AgentGraph:
    """Complete Langgraph implementation with conditional edges"""

    def __init__(self, nodes: AgentNodes):

        self.nodes = nodes
        self.planner = AutonomousPlanner(nodes)
        self.router = DynamicRouter(self.planner)

        self.graph = self._build_graph()


    
    def _build_graph(self) ->StateGraph:
        """
        Build the agent with ReAct loop and conditional routing
        """
        workflow = StateGraph(AgentState)

        workflow.add_node('planner', self.nodes.planner_node)
        workflow.add_node('memory', self.nodes.memory_node)
        workflow.add_node('researcher', self.nodes.researcher_node)
        workflow.add_node('analyzer', self.nodes.analyzer_node)
        workflow.add_node('reasoner', self.nodes.reasoner_node)
        workflow.add_node('generator', self.nodes.generator_node)


        ##Job matching Node

        workflow.add_node('job_planner', self.nodes.job_planner_node)
        workflow.add_node('job_scraper', self.nodes.job_scraper_node)
        workflow.add_node('job_matcher', self.nodes.job_matcher_node)
        workflow.add_node('job_quality_checker', self.nodes.job_quality_checker_node)
        workflow.add_node('job_report_generator', self.nodes.job_report_generator_node)

        # memory node

        workflow.add_node('memory_storage', self.nodes.memory_storage_node)
        workflow.add_node('memory_retrieval', self.nodes.memory_retrieval_node)
        workflow.add_node('memory_job_storage', self.nodes.memory_job_storage_node)
        workflow.add_node('memory_learning', self.nodes.memory_learning_node)


        # Skills Nodes

        workflow.add_node('skills_analysis', self.nodes.skills_analysis_node )
        workflow.add_node('intelligent_ranker', self.nodes.intelligent_ranker_node)
        workflow.add_node('meta_reasoner', self.nodes.meta_reasoner_node)


        ### Entry Point

        workflow.set_entry_point("planner")

        workflow.add_conditional_edges(
            "planner",
            self._route_after_planning,
            {
                "job_workflow": "job_planner",
                "research_workflow": "memory"
            }
        )

        ## Job Matching worflow

        workflow.add_edge("job_planner", "memory_storage")
        workflow.add_edge("memory_storage", "job_scraper")
        workflow.add_edge("job_scraper", "memory_job_storage")
        workflow.add_edge("memory_job_storage", "memory_retrieval")
        workflow.add_edge("memory_retrieval", "skills_analysis")
        workflow.add_edge("skills_analysis", "job_matcher")
        workflow.add_edge("job_matcher", "intelligent_ranker")
        workflow.add_edge("intelligent_ranker", "job_quality_checker")
        

        ## Quality check with logic
        workflow.add_conditional_edges(
            "job_quality_checker",
            self._autonomous_quality_routing,
            {
                "retry": "job_scraper",
                "improve": "meta_reasoner",
                "generate": "memory_learning",
                "END": END
            }
        )


        workflow.add_edge("meta_reasoner", "memory_learning")
        workflow.add_edge("memory_learning", "job_report_generator")
        workflow.add_edge("job_report_generator", END)


        ## Conditional Edges

        workflow.add_edge("memory", "researcher")
        workflow.add_edge("researcher", "analyzer")
        workflow.add_edge("analyzer", "reasoner")

        

        ## Conditional routing after reflecktion

        workflow.add_conditional_edges(
            "reasoner",
            self._autonomous_research_routing,
            {
                "continue": "researcher",
                "generate": "generator",
                "replan": "planner",
                "end": END
            }
        )

        workflow.add_edge("generator", END)

        ## ADD Persistant

        memory = MemorySaver()
        return workflow.compile(checkpointer=memory, debug=False)


    def _route_after_planning(self, state: dict) ->str:
        """Route to job workflow or Research workflow based on task type"""

        task_type = state.get('task_type', '').lower()
        task = state.get('task', '').lower()

        # Check if this is a job related task

        job_keywords = ['resume', 'hiring', 'job', 'career', 'position', 'employment']

        # Explicit Task Type
        if task_type in ['job_matching', 'job_search', 'resume_analysis', 'career']:
            return "job_workflow"

        ## check for resume upload
        if state.get('resume_text'):
            return "job_workflow"
        
        # Check task description for job kewords
        if any(keyword in task for keyword in job_keywords):
            return "job_workflow"

        return "research_workflow"
    
    def _autonomous_quality_routing(self, state: dict) ->str:
        """Agentic: Decide what to do after quality check"""



        retry_count = state.get('retry_count', 0)
        iteration = state.get('iteration', 0)


        matched_jobs = state.get('matched_jobs', 0)
        if not isinstance(matched_jobs, list):
            matched_jobs = []

        if retry_count >= 3:
            logger.warning("Max retries reached - forcing report")
            return 'generate'
        
        if iteration >= 10:
            logger.warning("Max iterations reached - forcing raport")
            return 'generate'
        
        if len(matched_jobs) > 0:
            return 'generate'

        # use autonomous planner for decision

        next_action, reasoning = self.planner.decide_next_action(state)

        logger.info(f" Autonomous decision: {next_action}")
        logger.info(f" Reason: {reasoning.get('primary_reason', 'N/A')}")

        # Map planner decision to get graph

        action_map = {
            'job_scraper': 'retry',
            'meta_reasoner': 'improve',
            'memory_learning': 'generate',
            'job_report_generator': 'generate'
        }

        return action_map.get(next_action, 'generate')

    def _autonomous_research_routing(self, state: dict) ->str:
        """Agentic: agent Decide what to do after reasoning"""

        next_action, reasoning = self.planner.decide_next_action(state)

        logger.info(f" Autonomous Decision: {next_action}")

        action_map = {
            'researcher': 'continue',
            'generate': 'generate',
            'planner': 'replan'
        }

        return action_map.get(next_action, 'generate')


    def _should_retry_job_research(self, state: dict) -> str:
        """Decide whether to retry job or generate report"""

        quality_check = state.get('quality_check', {})
        retry_count = state.get('retry_count', 0)
        max_retries = 2

        matched_jobs = state.get("matched_jobs", [])

        ## Stop Infinite Loop
        if retry_count >= max_retries:
            logger.warning(f"Max retries ({max_retries}) reached generating report anyway")
            return "generate"

        # if have any matched jobs
        if len(matched_jobs) > 0:
            logger.info(f" Have {len(matched_jobs)} Jobs Proceeding to report")
            return "generate"
        
        ## Check quality passed
        if quality_check.get('passed', False):
            logger.info(f" Quality check passed generating report")
            return "generate"
        
        ## Only retry if NO matched jobs
        if len(matched_jobs) == 0 and retry_count < max_retries:
            logger.warning(f"No jobs found retring count ({retry_count + 1}/{max_retries})")
            state['retry_count'] = retry_count + 1

        ## Broaden search Paramters 
            current_keywords = state.get('job_keywords', [])
            state['job_keywords'] = current_keywords + ['developer', 'Ai', 'engineer', 'remote', 'Agentic Ai', 'mern stack', 'web developer']

            return "retry"
    
        logger.info(f"Generating report with available data")
        return "generate"

            
    def _should_continue(self, state: dict) -> str:
        """Routing Logic Based On validation"""
        # Access state safely
        iteration = state.get('iteration', 0)
        max_iteration = state.get('max_iteration', 10)
        confidence_score = state.get('confidence_score', 0.0)
        retry_count = state.get('retry_count', 0)
        current_step = state.get('current_step', 0)
        plan = state.get('plan', [])
        validation_results = state.get('validation_results', {})
        errors = state.get('errors', [])

    # CRITICAL: Check max iterations FIRST
        if iteration >= max_iteration:
          return "generate"

    # Safety valve: Force generate after 5 iterations
        if iteration >= 5:
          return "generate"

    # Too many errors - replan
        if len(errors) > 5:
          return "replan"

    # High confidence - generate
        if confidence_score > 0.75:
          return "generate"

    # Low confidence - retry with limit
        if confidence_score < 0.6 and retry_count < 3:
           state['retry_count'] = retry_count + 1
           state['iteration'] = iteration + 1  # ← CRITICAL: Increment here!
           return "continue"

    # Max retries reached
        if retry_count >= 3:
          return "generate"

    # More steps in plan
        if current_step < len(plan) - 1:
           state['current_step'] = current_step + 1
           state['iteration'] = iteration + 1  # ← CRITICAL: Increment here!
           return "continue"

    # Need more data
        if validation_results.get('get_more_data', False):
           state['iteration'] = iteration + 1  # ← CRITICAL: Increment here!
           return "continue"

    # Default to generate
        return "generate"


        















