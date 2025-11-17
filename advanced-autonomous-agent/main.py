## Main Entry File
import asyncio
from datetime import datetime
from langchain_groq import ChatGroq
from backend.agent.graph import AgentGraph
from backend.agent.nodes import AgentNodes
from backend.agent.autonomous_planner import AutonomousPlanner
from backend.agent.goal_manager import GoalManager
from backend.agent.self_improvement import SelfImprovementController
from backend.agent.orchestrator import AgentOrchestrator
from backend.config.settings import Settings
import structlog

logger = structlog.get_logger()


async def main():
    """Agentic : Fully autonomous execution"""

    logger.info(" Starting Agentic Ai Agent")
    logger.info("="*60)

    ## Initialize Existing Components

    settings = Settings()
    llm = ChatGroq(
        model = settings.PRIMARY_MODEL,
        api_key = settings.GROQ_API_KEY
    )

    from backend.mcp.web_search_server import WebSearchMCPServer
    from backend.mcp.database_server import DataMCPServer

    mcp_servers = {
        'web_search': WebSearchMCPServer(),
        'database': DataMCPServer(db_path= settings.CHROMA)
    }


    tools = {'websearch': mcp_servers['web_search']}

    nodes = AgentNodes(llm=llm, tools=tools, mcp_client=mcp_servers)
    agent_graph = AgentGraph(nodes)


    ## New agentic Components

    goal_manager = GoalManager(agent_graph, max_goal_iterations=5)
    planner = AutonomousPlanner(nodes)
    improvement = SelfImprovementController()


    ## New Orchestration
    orchestrator = AgentOrchestrator(
        agent_graph,
        goal_manager,
        planner,
        improvement
    )

    logger.info("ll Components Initialize")

    initial_state = {
        'task': 'Find the  best remote AI/ML engineer jobs matching my skills',
        'task_type': 'job_matching',
        'task_id': f"agentic_{int(datetime.now().timestamp())}",
        'priority': 9,
    

        ## params
        'resume_text': f"""
        Senior ML engineer with 5 years of experience
        Skills: Python, TensorFlow, kubernetes, PyTorch, AWS, Docker
        Built Production ML Systems serving 1m+ users
        """,

        'job_keywords': ['ai', 'ml engineer', 'machine learning'],
        'job_location': 'Remote',
        'experience_level': 'senior',
        'user_id': 'user_demo',

        ## State Initialized
        'plan': [],
        'current_step': 0,
        'reasoning_history': [],
        'search_quaries': [],
        'search_results': [],
        'extracted_insights': [],
        'analysis_results': {},
        'errors': [],
        'retry_count': 0,
        'iteration': 0,
        'max_iteration': 10,
        'status': 'running',
        'jobs_data': [],
        'mactched_jobs':[],
        'confidence_score': 0.0,
        'validation_results': {},
        'artifacts': [],
        'final_output': None
    }

    logger.info("\n Running fully autonomous agent...")


    result = await orchestrator.run_autonomous_cycle(
        initial_state,
        continuous = True,
        max_cycles =5,
    )


    # Results
    logger.info(f"\n" + "="*60)
    logger.info("Autonomous Execution Complete")
    logger.info("="*60)
    logger.info(f" Goal Achieved: {result.get('goal_achieved', False)}")
    logger.info(f" Cycles useed {result.get('autonomous_execution', {}).get('total_cycles',0)}")
    logger.info(f"Matched jobs {len(result.get('matched_jobs', []))}")
    logger.info(f" Final Confidence {result.get('confidence_score', 0)}")

    ## Comprehensive Report
    print(f"\n" + orchestrator.get_comprehensive_report())

    ## Save Learned Optimizations
    orchestrator.export_state('agent_learned_state.json')

    return result


if __name__ == "__main__":
    asyncio.run(main())

    











