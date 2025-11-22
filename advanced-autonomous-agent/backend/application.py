import os
import asyncio
from langchain_groq import ChatGroq
from typing import List, Dict
import structlog
from datetime import datetime


from .agent.graph import AgentGraph
from .agent.nodes import AgentNodes

from .agent.autonomous_planner import AutonomousPlanner
from .agent.goal_manager import GoalManager
from .agent.self_improvement import SelfImprovementController
from .agent.orchestrator import AgentOrchestrator

from .config.settings import Settings
from .core.monitoring import setup_observability
from .core.email_sender import EmailSender
from .tools.pdf_generator import PDFGenerator
from .core.orchestrator import AutonomousOrchestration
from .mcp.web_search_server import WebSearchMCPServer
from .mcp.database_server import DataMCPServer
from .tools.analyzer import AnalysisTools


from .multiagents.agents_orchestrator import AutonomousOrchestrator as  MultiAgentOrchestrator
from .core.memory_system import MemoryRAGSystem


logger = structlog.get_logger()


class AgentApplication:
    def __init__(self):
        self.agents =[]
    """
    Main Application class orchestrate all components
    """
    def init_orchestrator(self):
        from backend.multiagents.agents_orchestrator import AutonomousOrchestrator
        self.orhestrator = AutonomousOrchestrator()

    def __init__(self, agentic_mode: bool = True, autonomous_24_7: bool = False):
        self.settings = Settings()
        self.tracer = setup_observability()
        self.agent_graph = None
        self.email_sender = EmailSender()
        self.pdf_generator = PDFGenerator()

        self.mcp_servers = {}

        self.agentic_mode = agentic_mode
        self.orchestrator = None
        self.orchestration = None
        self.autonomous_24_7 = autonomous_24_7
        self.multi_agent_orchestrator = None
        self.memory_system = None

    
    async def initialize(self):
        """Initialize Components"""
        logger.info("Initializing Autonomous Agent")

        llm = ChatGroq(
            model = self.settings.PRIMARY_MODEL,
            api_key = self.settings.GROQ_API_KEY,
            temperature = self.settings.TEMPERATURE,
            max_tokens = self.settings.MAX_TOKENS
        )
        logger.info(f"Initialized info: {self.settings.PRIMARY_MODEL}")


        # Initialized MCP SERVERS

        await self._initialize_mcp_servers()

        # Initialze Tools

        tools = self._initialize_tools()


        # New Intialize Memory Syetem

        self.memory_system = MemoryRAGSystem(persistent_directory=self.settings.CHROMA)
        logger.info("Mmeory System Initialized")

        # Create Agent

        nodes = AgentNodes(llm=llm, tools=tools, mcp_client=self.mcp_servers )
        self.agent_graph = AgentGraph(nodes)


        ## New agentic Layer
        if self.agentic_mode:
            logger.info("Enabling Agentic Mode")

            goal_manager = GoalManager(self.agent_graph)
            planner = AutonomousPlanner(nodes)
            improvement = SelfImprovementController()

            self.orchestrator = AgentOrchestrator(
                self.agent_graph,
                goal_manager,
                planner,
                improvement
            )

            logger.info("Agentic Capabilities Activated")

        logger.info("Agent Initialized Successfully")

        ## Autonomous 24_7 Agent System
        if self.autonomous_24_7:
            logger.info("Enabling Autonomous System")
        
            self.multi_agent_orchestrator =MultiAgentOrchestrator(
              agent_app=self,
              memory=self.memory_system
            )

            logger.info("Multi Agent orchestrator Ready")
        
        logger.info("="*60)
        logger.info("MultiAgent Syetem Operational")
        logger.info("="*60)


    async def run_task(self, state: Dict, agentic: bool = None)->Dict:
        """Run task with Optional enhancement"""

        use_agentic = agentic if agentic is not None else self.agentic_mode

        if use_agentic and self.orchestrator:
            logger.inf("Running with agentic orchestration")

            ## Run with fully autonomy
            result = await self.orchestrator.run_autonomous_cycle(
                state,
                continous = True,
                max_cycles = 5
            )

            return result
        
        else:
            logger.info("Running standard Execution")

            # Standard Execution
            config = {"configurable": {"thread_id": state.get('task_id')}}
            result = await self.agent_graph.graph.ainvoke(state, config)

        ## Initalize Orchestration
        scheduler_config = self._load_scheduler_config()
        self.orchestration = AutonomousOrchestration(
            agent_graph = self.agent_graph,
            scheduler_config = scheduler_config, 
            email_sender = self.email_sender,
            pdf_generator= self.pdf_generator
        )

        self.orchestration.start_time = datetime.now()

        logger.info(f"Graph Initialized Successfully")

    
    async def start_autonomous_system(self):
        """Start 24_7 autonomous multi-agent-System"""
        if not self.multi_agent_orchestrator:
            raise RuntimeError("MutiAgent Orchestrator not initialzed . Set autonomous_24_7=True")
        
        logger.info("Starting 24_7 Autonomous System...")
        await self.multi_agent_orchestrator.start()

    async def stop_autonomous_agent(self):
        """Stop Autonomous 24_7 Syetm"""

        if self.multi_agent_orchestrator:
            logger.info("Stopping Autonomous System...")   
        return await self.multi_agent_orchestrator.stop()

    async def get_autonomous_status(self):
        """Get status of 24_7 System"""

        if not self.multi_agent_orchestrator:
            return {"enambled": False}

        return self.multi_agent_orchestrator.get_status()

    
    async def _initialize_mcp_servers(self):
        """Start All MCP Servers"""

        logger.info("Starting MCP Servers ....")

        ## Web Search MCP Server

        web_search = WebSearchMCPServer()
        self.mcp_servers['web_search'] = web_search
        logger.info("Web Search MCP Server Ready")


        ## DATABase MCP Servers

        database =DataMCPServer(db_path=self.settings.CHROMA)
        self.mcp_servers['database'] = database
        logger.info("Database MCP Servers")

        ## Analytics Server (Simplified Server)

        self.mcp_servers['analytics'] = AnalysisTools()
        logger.info("Analytics tools ready")


        logger.info(f"ALL {len(self.mcp_servers)} MCP Servers Operational")

    def _initialize_tools(self):
        """Initialize Tools"""

        tools = {
            'web_search': self.mcp_servers['web_search'],
            'database': self.mcp_servers['database'],
            'analytics': self.mcp_servers['analytics']
        }

        logger.info(f"Initialize {len(tools)} Tool Categories")
        return tools
    
    def _load_scheduler_config(self) -> Dict:
        """Load Task Scheduling configuration"""

        return {
            'recurring_tasks':[
                {
                    'name': 'daily_market_scan',
                    'type': 'market_research',
                    'description': 'Scan top competitiors for product/price changes',
                    'schedule': {
                        'type': 'interval',
                        'interval_minutes': 5 
                    },
                    'priority': 8,
                    'targets' : ['competitor_a', 'competitor_b', 'competitor_c']
                },
                {
                    'name': 'hourly_news_monitoring',
                    'type':  'news_monitoring',
                    'description': 'monitor industry news and trends',
                    'schedule': {
                        'type': 'interval',
                        'interval_minutes': 2,
                    },
                    'priority': 6,
                    'keywords': ['AI', 'automation', 'tech layoffs']
                },
                {
                    'name': 'weekly_lead_generation',
                    'type': 'lead generation',
                    'description': 'Find and qualify new leads',
                    'schedule': {
                        'type': 'interval',
                        'interval_minutes':6
                    },
                    'priority': 7,
                    'criteria': {
                        'industry': 'SaaS',
                        'size': '50-100 employees',
                        'funding_stage': 'Series A+'
                    }                
                }
            ]
        }
    
    async def run(self):
        """Start The autonomous Agent"""
        try:
            logger.info("=" * 60)
            logger.info("Starting the autonomous agent")
            logger.info("="* 60)

            await self.orchestration.start()
        
        except KeyboardInterrupt:
            logger.info("Shutdown Requested")
            await self.shutdown()
    
        except Exception as e:
            logger.error(f"Fatal Error: {e}", exc_info=True)
            await self.shutdown()

    async def shutdown(self):
        """Gracefully Shutdown"""

        logger.info("Initiating Shutting down gracefully ...")

        if self.orchestration:
            await self.orchestration.stop()
        
        logger.info("Shutdown Complete")

    



