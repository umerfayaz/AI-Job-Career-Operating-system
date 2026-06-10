## Main Entry File
import asyncio
from datetime import datetime
from langchain_groq import ChatGroq
from backend.agent.graph import AgentGraph
from backend.agent.nodes import AgentNodes
from backend.application import AgentApplication
from backend.config.settings import Settings
import structlog

logger = structlog.get_logger()


async def run_agentic_task():
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
        'database': DataMCPServer(db_path= settings.CHROMA_PATH)
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

async def run_24_7_system():
    """Mode 24_7 system multi_agent system"""
    logger.info("24_7 Autonomous System")
    logger.info("="*60)

    # Initialize both system
    agent_app = AgentApplication(agentic_mode=True, autonomous_24_7=True)
    await agent_app.initialize()

    logger.info("Starting 24_7 autonomous System")

    try:
        await agent_app.start_autonomous_system()
    except KeyboardInterrupt:
        logger.info("Starting autonomous system")
        await agent_app.stop_autonomous_system()

async def run_hybrid():
    """Run agentic Task and 24_7 Hubrid System"""

    logger.info("Mode: Hybrid (agentic + 24_7)")

    agent_app = AgentApplication(agentic_mode=True, autonomous_24_7=True)
    await agent_app.initialize()

    # Starting 
    logger.info("Strting 24_7 hybrid system")
    asyncio.create_task(agent_app.start_autonomous_system())

    ## Wait for a bit to start
    await asyncio.sleep(2)

    # Keep runinig the system
    logger.info("System Continue Running")
    logger.info("Press to stop everything\n")

    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("Stopping all systems..")
        await agent_app.stop_autonomous_system()

async def main():
    """Choose your Node"""

    import sys

    if len(sys.argv) > 1:
        mode = sys.argv[1]
    
    else:
        print("\nChoose Node")
        print("1 - Single agentic task (goal_based)")
        print("2- 24_7 autonomous System")
        print("3 - Hybrid(both)")
        choice = ("\nEnter Choice (1/2/3)")
        mode = {'1': 'agentic', '2': '24/7', '3': 'hybride'}.get(choice, 'agentic')
    
    if mode == 'agentic':
        await run_agentic_task()
    
    if mode == '24_7' or mode == '247':
        await run_24_7_system()
    
    if mode == 'run_hybrid':
        await run_hybrid()
    
    else:
        print("Unknown Mode")




if __name__ == "__main__":
    asyncio.run(main())

    











