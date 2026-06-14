
import asyncio
import logging
from typing import Any, Dict, List
from backend.config.settings import Settings

try:
    import structlog

    logger = structlog.get_logger()
except Exception:
    logger = logging.getLogger("cognitive_orchestrator")
    logging.basicConfig(level=logging.INFO)

settings = Settings() 

class CognitiveOrchestrator:
    def __init__(
        self,
        agents: Dict[str, Any],
        decision_engine: Any,
        episodic_memory: Any,
        shared_context: Any,
        guardrails: Any,
        memory: Any,
        settings: Any,
    ):

        self.agents = agents or {}
        self.decision_engine = decision_engine
        self.episodic_memory = episodic_memory
        self.settings = settings
        self.shared_context = shared_context
        self.guardrails = guardrails
        self.memory = memory
        self.plan_lock = asyncio.Lock()

        # basic message bus: channel -> list of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

        # runtime tracking
        self.running_tasks: Dict[str, asyncio.Task] = {}

    # Message bus
   
    async def publish(self, channel: str, message: Dict[str, Any]):
        queues = self._subscribers.get(channel, [])
        for q in list(queues):
            try:
                await q.put(message)
            except Exception:
                logger.exception("publish failed", channel=channel)

    def subscribe(self, channel: str) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.setdefault(channel, []).append(q)
        return q
    
    async def _determine_agents(self, event_type: str, event_data: Dict) -> List[str]:
        """
        FIXED: Determine which agents should run based on event
        """
        
        if event_type == "new_jobs":
            logger.warning("Event new jobs detected triggering resume matcher + report + notification")
            return ["ResumeMatcherAgent", "ReportGeneratorAgent", "NotificationAgent"]
            
        logger.info("✅ No agents needed")
        return []

    # Top-level event handling
 
    async def decide(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        FIXED: Main decision-making function with target resume support
        """
        event_type = event.get("type", "unknown")
        event_data = event.get("data", {})
        
        logger.info(f" CognitiveOrchestrator processing: {event_type}")
        
        try:
            # Determine which agents to run
            agents_to_run = await self._determine_agents(event_type, event_data)
            
            if not agents_to_run:
                logger.info(f" No agents needed for {event_type}")
                return {
                    "agents": [],
                    "reasoning": f"No action needed for {event_type}",
                    "status": "no_action"
                }
            
            # HANDLE TARGET RESUME FOR NEW_JOBS EVENT
            if event_type == "new_jobs":
                target_resume_id = event_data.get("target_resume_id")

                if not target_resume_id:
                    target_resume_id = await self.shared_context.read("ResumeMatcherAgent_target_resume")

                if target_resume_id:                   
                    # Store target in shared context for ResumeMatcherAgent
                    await self.shared_context.write(
                        "ResumeMatcherAgent_target_resume",
                        target_resume_id,
                        "WorkflowExecutor"
                    )
                
                    logger.info(f" Set target resume: {target_resume_id}")           
                else:
                    logger.info(f" No jobs without target_resumes:  - skipping resume_matcher")
                    agents_to_run  = [a for a in agents_to_run if a !="ResumeMatcherAgent"]
                           
            # Execute agents
            results = []
            for agent_name in agents_to_run:
                try:
                    agent = self.agents.get(agent_name)
                    if not agent:
                        logger.warning(f" Agent {agent_name} not found")
                        continue
                    
                    logger.info(f" Running {agent_name}")
                    
                    # Run the agent
                    result = await agent.run_cycle(payload=event_data)
                    results.append({
                        "agent": agent_name,
                        "result": result,
                        "status": result.get("status", "unknown")
                    })
                    
                    logger.info(f" {agent_name} completed: {result.get('status')}")
                    
                    # Record in episodic memory
                    self.episodic_memory.record_experiences(
                        agent_name=agent_name,
                        action="orchestrated_run",
                        result=result,
                        context={"event_type": event_type}
                    )
                    
                except Exception as e:
                    logger.error(f" {agent_name} failed: {e}", exc_info=True)
                    results.append({
                        "agent": agent_name,
                        "result": {"status": "error", "error": str(e)},
                        "status": "error"
                    })
            
            return {
                "agents": agents_to_run,
                "results": results,
                "reasoning": f"Processed {event_type} with {len(agents_to_run)} agents",
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f" Orchestrator failed: {e}", exc_info=True)
            return {
                "agents": [],
                "reasoning": f"Error: {str(e)}",
                "status": "error"
            }

    async def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an event (alias for decide)"""
        return await self.decide(event)

   
