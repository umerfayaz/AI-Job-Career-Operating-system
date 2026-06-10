from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .nodes import AgentNodes
from .state import AgentState
import structlog
from langgraph.checkpoint.memory import MemorySaver
logger = structlog.get_logger()
class AgentGraph:
    """Complete Langgraph implementation with conditional edges"""

    def __init__(self, nodes: AgentNodes):

        self.nodes = nodes
        self.graph = self._build_graph()


    def _build_graph(self) ->StateGraph:
        """
        Build the agent with ReAct loop and conditional routing
        """
        workflow = StateGraph(AgentState)

        # workflow.add_node('memory', self.nodes.memory_node)
        # workflow.add_node('researcher', self.nodes.researcher_node)
        # workflow.add_node('analyzer', self.nodes.analyzer_node)
        # workflow.add_node('reasoner', self.nodes.reasoner_node)
        # workflow.add_node('generator', self.nodes.generator_node)

        ##Job matching Node

        workflow.add_node('job_planner', self.nodes.job_planner_node)
        workflow.add_node('job_scraper', self.nodes.job_scraper_node)
        workflow.add_node('job_matcher', self.nodes.job_matcher_node)
        workflow.add_node('job_quality_checker', self.nodes.job_quality_checker_node)
        workflow.add_node('job_report_generator', self.nodes.job_report_generator_node)

        # memory node

        workflow.add_node('ensure_resume_node', self.nodes.ensure_resume_node)
        workflow.add_node('memory_storage', self.nodes.memory_storage_node)
        workflow.add_node('memory_retrieval', self.nodes.memory_retrieval_node)
        workflow.add_node('memory_job_storage', self.nodes.memory_job_storage_node)
        workflow.add_node('memory_learning', self.nodes.memory_learning_node)

        # Skills Nodes

        workflow.add_node('skills_analysis', self.nodes.skills_analysis_node )
        workflow.add_node('intelligent_ranker', self.nodes.intelligent_ranker_node)
        workflow.add_node('meta_reasoner', self.nodes.meta_reasoner_node)

        ### Entry Point

        # Entry
        workflow.set_entry_point("job_planner")

        workflow.add_edge("job_planner", "memory_storage")
        workflow.add_edge("memory_storage", "job_scraper")
        workflow.add_edge("job_scraper", "memory_job_storage")
        workflow.add_edge("memory_job_storage", "memory_retrieval")

        workflow.add_edge("memory_retrieval", "ensure_resume_node")
        workflow.add_edge("ensure_resume_node", "skills_analysis")

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


        memory = MemorySaver()
        return workflow.compile(checkpointer=memory, debug=False)
    
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
        
        return "retry"

