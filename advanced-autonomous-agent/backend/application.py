"""
application.py - Unified Application with Both Brains Integrated

This file connects:
- Brain 1: LangGraph workflow (existing)
- Brain 2: Multi-agent system (new)

Both work independently BUT share data and can trigger each other.
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import structlog
from threading import Lock
from langchain_groq import ChatGroq
from backend.agent.graph import AgentGraph
from backend.agent.nodes import AgentNodes
from backend.core.safeRunner import SafeRunner
from backend.core.recovery_manager import RecoveryManager
from backend.core.event_bus import get_event_bus
from backend.config.settings import Settings
from backend.systen_brain.decider import CognitiveBrain
from backend.core.memory_system import MemoryRAGSystem
from backend.multiagents.agents_orchestrator import AutonomousOrchestrator
from backend.redis.redis_memory import redis_client


logger = structlog.get_logger()
settings =Settings()
pending_workflows: dict = {}
workflow_lock = Lock()

class AgentApplication:
    """
    Unified Application: Manages BOTH brains
    - Brain 1: LangGraph (goal-based, planning, self-improvement)
    - Brain 2: Multi-agents (24/7 monitoring, event-driven)
    """
    
    def __init__(self, agentic_mode: bool = True, autonomous_24_7: bool = True):
        """
        Initialize the unified system
        
        Args:
            agentic_mode: Enable Brain 1 (LangGraph workflows)
            autonomous_24_7: Enable Brain 2 (Multi-agent system)
        """
        self.agentic_mode = agentic_mode
        self.event_bus = None
        self.recover_manager = None
        self.safe_runner = None
        self.autonomous_24_7 = autonomous_24_7
        self._autonomous_task = None
        self._autonomous_started = False
        
        # Shared components (both brains use these)
        self.memory_system: Optional[MemoryRAGSystem] = None
        self.llm: Optional[ChatGroq] = None

        self.Settings = Settings()
        # Brain 1: LangGraph components
        self.orchestrator: Optional[AgentOrchestrator] = None
        self.agent_graph: Optional[AgentGraph] = None
        self.graph_initialized: bool = False
        
        # Brain 2: Multi-agent components
        self.multi_agent_orchestrator: Optional[AutonomousOrchestrator] = None
        # The decider brain
        self.cognitive_brain: Optional[CognitiveBrain] =  None


        logger.info(f"AgentApplication initialized")
        logger.info(f"   Agentic Mode (Brain 1): {agentic_mode}")
        logger.info(f"   Autonomous 24/7 (Brain 2): {autonomous_24_7}")
        logger.info(f" Initialzed Brain 3 in AgentApplication")
    
    async def initialize(self):
        """Initialize all components"""
        logger.info("=" * 60)
        logger.info(" Initializing Unified Agent System")
        logger.info("=" * 60)
        
        # 1. Initializing shared components
        await self._initialize_shared_components()

        #1 Brain 3 the decider
        await self._initialize_cognitive_brain3()
        
        # 2. Initialize Brain 1 (LangGraph)
        if self.agentic_mode:
            await self._initialize_langgraph_brain()
        
        # 3. Initializing Brain 2 (Multi-agents) 
        if self.autonomous_24_7:
            await self._initialize_multiagent_brain()
        
        # 4. Connecting the brains
        await self._connect_brains()
        
        logger.info("=" * 60)
        logger.info(" Unified Agent System Ready")
        logger.info("=" * 60)
    
    async def _initialize_shared_components(self):
        """Initialize components shared by both brains"""
        logger.info("Initializing shared components...")
        
        # Memory system 
        self.memory_system = MemoryRAGSystem()
        self.memory = self.memory_system
        logger.info("   Memory system initialized")
        
        # LLM 
        self.llm = ChatGroq(
            model=self.Settings.PRIMARY_MODEL,
            api_key=self.Settings.GROQ_API_KEY
        )
        logger.info("   LLM initialized")
    
    async def _initialize_cognitive_brain3(self):
        """Initializeing brain 3 the header"""
        try:
            self.cognitive_brain = CognitiveBrain()
        
        except Exception as e:
            logger.warning("Failed to initialize Brain 3 in Agent Application file{e}")
    
    async def _initialize_langgraph_brain(self):
        """Initialize Brain 1: LangGraph workflow"""
        logger.info(" Initializing Brain 1 (LangGraph)...")
        
        try:
            self.event_bus = get_event_bus()
            self.safe_runner = SafeRunner(self.event_bus)
            self.recover_manager = RecoveryManager(
              orchestrator = self,
              multi_agent_orchestrator = self.multi_agent_orchestrator
            )

            self.event_bus.subscribers_topic("RECOVERY_ACTION", self.recover_manager.handle_recovery_action)
            self.event_bus.subscribers_topic("SYSTEM_ACTION", self.cognitive_brain.autonomous_recovery)
            self.event_bus.subscribers_topic("SYSTEM_ERROR", self.cognitive_brain.autonomous_recovery)
            
            # Initializing nodes and graph
            nodes = AgentNodes(agent_app=self, llm=self.llm, memory=self.memory_system)
            self.agent_graph = AgentGraph(nodes)
            
            self.graph_initialized = True
            logger.info(" LangGraph brain initialized")
            logger.info(" - Goal Manager: Ready")
            logger.info(" - Planner: Ready")
            logger.info(" - Self-Improvement: Ready")
            logger.info(" - Orchestrator: Ready")
            
        except Exception as e:
            logger.error(f" Failed to initialize LangGraph: {e}")
            raise

    
    async def _initialize_multiagent_brain(self):
        """Initialize Brain 2: Multi-agent system"""
        logger.info(" Initializing Brain 2 (Multi-agents)...")
        
        try:
            self.multi_agent_orchestrator = AutonomousOrchestrator(
                memory=self.memory_system,
                orchestrator=self.orchestrator
            )
            
            # Giving multi-agents access to this application instance
            self.multi_agent_orchestrator.initialize_agents_with_app(self)
            if self.recover_manager and self.multi_agent_orchestrator:
                self.recover_manager.multi_agent_orchestrator = self.multi_agent_orchestrator
            
            logger.info(" Multi-agent brain initialized")
            logger.info(" - JobScraperAgent: Ready")
            logger.info(" - ResumeMatcherAgent: Ready")
            logger.info(" - ReportGeneratorAgent: Ready")
            logger.info(" - MemoryMaintenanceAgent: Ready")
            logger.info(" - NotificationAgent: Ready")
            logger.info(" - Episodic Memory: Active")
            logger.info(" - Shared Context: Active")
            
        except Exception as e:
            logger.error(f" Failed to initialize Multi-agents: {e}")
            raise
    
    async def _connect_brains(self):
        logger.info("Connceting Brains")

        if self.agentic_mode and self.autonomous_24_7:
                
                logger.warning("Brain 2 can now call brain 1 nodes")

                if self.orchestrator and self.multi_agent_orchestrator:
                    self.orchestrator.shared_context = self.multi_agent_orchestrator.shared_context
                    logger.info("brain 1 can now access brain shared context")
            
        if self.autonomous_24_7 and self.multi_agent_orchestrator:
              if self.cognitive_brain:

                self.multi_agent_orchestrator.cognitive_brain = self.cognitive_brain
                logger.info(f"Brain3 add  to brain2")
        
        if self.agentic_mode and self.autonomous_24_7:
            if self.orchestrator and self.multi_agent_orchestrator:

                self.multi_agent_orchestrator.brain1 = self.orchestrator
                logger.info(f" Brain 3 -> Brain 1 connected (via brain 2)")
        
        logger.info("All brains connected")

    async def run_langgraph_workflow(self, initial_state: Dict, config: Dict) -> Dict:
        """
        Running LangGraph workflow directly (without orchestrator)
        Used by API endpoints for job matching
        """
        if not self.agent_graph:
            raise RuntimeError("Agent graph not initialized")
        
        logger.info("Running LangGraph workflow")
      
        result = await self.agent_graph.graph.ainvoke(initial_state, config)
        
      
        if self.multi_agent_orchestrator:
            await self._notify_brain2_workflow_completed(result)
        return result
  
    
    async def start_autonomous_system(self):
        """Start Brain 2 (24/7 multi-agent system)"""

        if self._autonomous_started:
            logger.info("Autonomous system already started - Skipping")
            return
        
        self._autonomous_started = True

        if not self.multi_agent_orchestrator:
            raise RuntimeError("Multi-agent orchestrator Initialized")
        
        logger.info("Starting 24/7 autonomous system (Brain 2)")
        
        self._autonomous_task =  asyncio.create_task(self.multi_agent_orchestrator.start())
        logger.info("Brain2 mulit-agent orchestrator started")
        
    
    async def stop_autonomous_system(self):
        """Stop Brain 2"""
        if self.multi_agent_orchestrator and self.multi_agent_orchestrator.is_running:
            logger.info("🛑 Stopping autonomous system")
            await self.multi_agent_orchestrator.stop()

    
    async def _notify_brain2_workflow_completed(self, result: Dict, user_id: str = None):
        """Notify Brain 2 about workflow completion"""
        try:
            resume_id =( 
                result.get("user_id") or
                user_id
            )
            
            # Notify about jobs found
            jobs_count = len(result.get("jobs_data", []))
            if jobs_count > 0:
                await self.multi_agent_orchestrator.notify_new_jobs(
                    job_count=jobs_count,
                    source="langgraph_workflow",
                    target_resume_id=resume_id,
                )
                logger.info(f" Notified Brain 2: {jobs_count} jobs found for {resume_id}")
            
            # Notify about matches created
            matches_count = len(result.get("matched_jobs", []))
            if matches_count > 0 and resume_id:
                await self.multi_agent_orchestrator.notify_matches_created(
                    match_count=matches_count,
                    resume_id=resume_id
                )
                logger.info(f" Notified Brain 2: {matches_count} matches created")
                
        except Exception as e:
            logger.error(f"Failed to notify Brain 2: {e}")
    

    async def update_stats(self, key: str, user_id: str, run_id:str, value: int = 1):

        VALID_KEYS = {"tasks_completed", "jobs_matched", "reports_generated"}
        if not key in VALID_KEYS:
            raise ValueError(f"Invalid stats key {key}")
        
        if not user_id or not run_id:
            raise ValueError("user_id and run_id required")

        await redis_client.incrby(f"user:{user_id}:{key}", value)
        await redis_client.incrby(f"run:{run_id}:{key}", value)


        tasks = await redis_client.get(f"user:{user_id}:tasks_completed") or 0
        jobs = await redis_client.get(f"user:{user_id}:jobs_matched") or 0
        reports = await redis_client.get(f"user:{user_id}:reports_generated") or 0


            # Emit update to frontend
        await self.event_bus.emit({
            "type": "stats_update",
            "user_id": user_id,
            "payload":{
                "tasks_completed": int(tasks),
                "jobs_matched": int(jobs),
                "reports_generated": int(reports),
            }
        })

    # SYSTEM MANAGEMENT
    
    async def shutdown(self):
        """Shutdown both brains gracefully"""
        logger.info("🛑 Shutting down unified system...")
        
        # Stop Brain 2
        if self.multi_agent_orchestrator:
            await self.multi_agent_orchestrator.stop()
        
        if self._autonomous_task:
            self._autonomous_task.cancel()
        
        self._autonomous_started = False
        
        # Clean up Brain 1
        if self.orchestrator:
            # Export learned state
            try:
                self.orchestrator.export_state('agent_learned_state.json')
                logger.info(" Saved learned state")
            except:
                pass
        
        logger.info(" Shutdown complete")

# Main APP Running
    
app_instance: AgentApplication | None = None

async def get_agent_app() -> AgentApplication:
    global app_instance
    if app_instance is None:
        app_instance = AgentApplication()
        await app_instance.initialize()
        
    return app_instance

