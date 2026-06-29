"""
Autonomous Orchestrator
Runs 24/7 and coordinates all agents with Cognitive Orchestrator
"""
import asyncio
import time
from typing import Dict
from datetime import datetime
import structlog
from backend.multiagents.guardrails import JobReportGuardrails
from .agents_team import (
    # JobScraperAgent,
    ResumeMatcherAgent,
    ReportGeneratorAgent,
    MemoryMaintenanceAgent,
    NotificationAgent,
    EpisodicMemory,
    SharedContext,
)

from backend.brain_outcomeLoop.email_config import load_email_config
from backend.postgreSQL.database import PostgresDatabase
from backend.brain_outcomeLoop.brain4outcomeLoop import OutComeLoop
from backend.core.event_bus import get_event_bus
from backend.multiagents.backend_listener import RefetchJobListener
from backend.core.safeRunner import SafeRunner
from .event_monitor import EventMonitor
from backend.postgreSQL.agent_context_layer import DecisionWorkflow, UserIntelligence
from ..core.memory_system import MemoryRAGSystem, settings
from backend.config.settings import Settings
from backend.redis.redis_memory import redis_client



logger = structlog.get_logger()


class AutonomousOrchestrator:
    """Main system orchestrator handling all agents and LLM decision making"""

    def __init__(self, memory: MemoryRAGSystem, orchestrator):
        self.event_bus = get_event_bus()
        email_config = load_email_config()
        self.outcome_database =PostgresDatabase(
            email_config ={
                "email": email_config["email"],
                "password": email_config["password"],
                "imap_server": email_config["imap_server"],
                "folder": email_config["folder"],
            }
        )

        self.orchestrator = orchestrator
        self.memory = memory
        self.settings = Settings()
        self.decision_workflow = DecisionWorkflow()
        self.safe_runner = SafeRunner(self.event_bus)
        self.guardrails = JobReportGuardrails()
        self.episodic_memory = EpisodicMemory(memory)
        self.shared_context = SharedContext(
            memory_system=memory,
            redis_client=redis_client
        )

        self.user_intelligence = UserIntelligence(
            outcome_database = self.outcome_database,
            decision_workflow = self.decision_workflow,
        )

        self.start_time = time.time()
        self.issue_attempts = {}
        self.max_self_heal_attempts =2
        self.event_processed = 0
        self.trigger_refetch_jobs = None
        self.agent_app = None
        self.cognitive = None
        self.last_event = None
        self.last_refetch_time = {}
        self.last_refetch_hours = 2

        # Event monitoring
        self.event_monitor = EventMonitor(memory)
        self.event_queue = asyncio.Queue()
        self.outcome_loop = OutComeLoop(
            shared_context=self.shared_context,
            event_bus=self.event_bus,
            outcome_database=self.outcome_database,
            user_intelligence = self.user_intelligence,
            re_fetch_event_emitter=self.trigger_refetch_jobs
        )

        # Agents dictionary
        self.agents: Dict[str, object] = {}
        self._agents_initialized = False
        # Memory Maintenance 
        self.maintenance_running = False

        self.memory.postgres_db = self.outcome_database 

        self.system_metrics = {
            "failure_rate": 0.0,
            "avg_response_time": 0.0,
            "memory_pressure": 0.0,
            "agent_utilization": {},
            "error_count_last_hour": 0,
            "stuck_tasks": 0,
            "match_jobs_count": 0.0,
            "jobs_scraped_today": 0.0,

            # Progress Outcomes Updates
            "task_completed_last_hour": 0,
            "task_started_last_hour": 0,
            "progress_rate": 0.0,
            "idle_agents": [],
            "no_progress_minutes": 0,
            "last_updated": datetime.now().isoformat()
        }

        from backend.systen_brain.decider import CognitiveBrain
        self.cognitive_brain = CognitiveBrain(orchestrator=self)

        # System state
        self.is_running = False
        self._started = False
        self.started_lock = asyncio.Lock()
        self._tasks = []
        self.stats = {
            'events_processed': 0,
            'agents_activated': 0,
            'start_time': None,
            'uptime_seconds': 0
        }

    def initialize_agents_with_app(self, agent_app):
        """Initialize agents after the agent_app is available"""
        self.agent_app = agent_app

        self.agents = {
            'ResumeMatcherAgent': ResumeMatcherAgent(agent_app, self.memory, self.episodic_memory, self.shared_context, self.guardrails, multi_agents_orchestrator=self),
            'ReportGeneratorAgent': ReportGeneratorAgent(
                agent_app,
                self.memory,
                self.episodic_memory,
                self.shared_context,
                self.guardrails
            ),
            'NotificationAgent': NotificationAgent(agent_app, self.memory, self.episodic_memory, self.shared_context, self.guardrails),
            'MemoryMaintenanceAgent': MemoryMaintenanceAgent(agent_app, self.memory, self.episodic_memory, self.shared_context, self.guardrails),

        }

        report_gen = self.agents['ReportGeneratorAgent']
        notification = self.agents['NotificationAgent']
        report_gen.link_notification_agent(notification)
        logger.info("Agents Linked: ReportGen -> Notification")

        from .cognitive_orchestrator import CognitiveOrchestrator

        self.cognitive = CognitiveOrchestrator(
            agents = self.agents,
            memory = self.memory,
            shared_context= self.shared_context,
            decision_engine=None,
            episodic_memory= self.episodic_memory,
            settings= self.settings,
            guardrails =self.guardrails
        )

        logger.info("Cognitive Orchtrator Initialzed")
    
    def initialize_refetch_loop(self):
        self.listener = RefetchJobListener(
            shared_context = self.shared_context,
            event_bus=self.event_bus,
            safe_runner=self.safe_runner,
            outcome_database=self.outcome_database
        )
        self.outcome_loop.refetch_listener = self.listener
    
    async def apply_control(self, signal):
        logger.info(f"Applying Control: {signal.action} to {signal.apply_to}")

        try:
            if signal.apply_to == "brain1":
                await self._control_brain1(signal)
                await self.shared_context.write(
                    "brain1_allowed",
                    signal.action !="pause",
                    "brain3"
                )
            
            elif signal.apply_to == "brain2":
                await self._control_brain2(signal)
            
            elif signal.apply_to == "system":
                await self._control_system(signal)
        except Exception as e: 
             logger.info(f"Control Signal Failed {e}")
    
    async def _control_brain1(self, signal):
        """Controlling langgraph Orchestrator"""

        allowed = await self.shared_context.read("brain1_allowed")
        if allowed is False:
            logger.info("brain1 execution blocked by Brain3")
            return

        if not hasattr(self, "brain1"):
            logger.warning("Brain-1 not available")
        
        if signal.action == "pause":
            self.brain1.is_running = False
            logger.info("Brain-1 is Paused")
        
        elif signal.action == "resume":
            self.brain1.is_running = True
            logger.info("Brain-1 resumed")
        
        elif signal.action == "reduce":

            if signal.value:
                self.brain1.planner.max_depth = int(signal.value)
                logger.info(f"Brain-1 depth reduced to {signal.value}")
        
        elif signal.action == "boost":

            if signal.value:
                self.brain1.planner.max_depth = int(signal.value)
                logger.info(f"Brain-1 depth boosted to {signal.value}")
    
    async def _control_brain2(self, signal):
        """Control multi-agent System (brain2)"""

        if signal.action == "pause":
            if signal.target and signal.target in self.agents:
                agent = self.agents[signal.target]
                agent.paused = True
                logger.info(f"Agent {signal.target} paused")
        
        elif signal.action == "resume":
            if signal.target and signal.target in self.agents:
                agent = self.agents[signal.target]
                agent.paused = False
                logger.info(f" Agent {signal.target} resumed")
        
        elif signal.action == "retry":

            await self._retry_failed_tasks(signal.target)
        
        elif signal.action == "escalate":

            await self._escalate_priority(signal.target)
    
    async def _control_system(self, signal):

        if signal.action == "reduce":

            self.settings.max_concurrent_agents =  int(signal.value or 1)
            logger.info("system resource reduced")
        
        elif signal.action == "boost":

            self.settings.max_concurrent_agents = int(signal.value or 3)
            logger.info("system resources boosted")
    
    async def _update_system_metrics(self):
        """Updating Syste, health Metrics"""

        jobs = await self.shared_context.read("recent_jobs") or []

        urls = [j.get("url") for j in jobs if j.get("url")]

        if urls:
            duplicates  = len(urls) - len(set(urls))
            self.system_metrics["job_repitation_rate"] = duplicates / len(urls)
        
        else:
            self.system_metrics["job_repitation_rate"] = 0.0

        total_tasks = sum(a.metrics['task_completed'] + a.metrics['task_failed']
           for a in self.agents.values()
        )

        failed_tasks = sum(a.metrics['task_failed'] for a in self.agents.values())

        self.system_metrics["failure_rate"] = (
            failed_tasks / total_tasks if total_tasks > 0 else 0.0
        )

        # Calculating agent Utilization
        for name, agent in self.agents.items():
            total = agent.metrics['task_completed'] + agent.metrics['task_failed']
            self.system_metrics['agent_utilization'][name] =total
        
        # check for stuck tasks
        active_tasks = await self.shared_context.read("active_tasks")
        if active_tasks:
            now = datetime.now()
            stuck_count = 0
            for task_id, task in active_tasks.items():
                created_at = datetime.fromisoformat(task["created_at"])
                if (now - created_at).total_seconds() > 3600:
                    stuck_count +=1
            self.system_metrics["stuck_tasks"] =stuck_count

        self.system_metrics["last_updated"] = datetime.now().isoformat()

    def calculate_memory_pressure(self):

        mma = self.agents["MemoryMaintenanceAgent"] 

        job_count = len(self.memory.job_collection.get().get("ids",[]))
        match_count = len(self.memory.match_collection.get().get("ids", []))
        resume_count = len(self.memory.resume_collection.get().get("ids", []))

        job_pressure = job_count / max(mma.max_jobs, 1)
        match_pressure = match_count / max(mma.max_matches, 1)
        resume_pressure = resume_count / max(mma.max_resume, 1)

        capacity_pressure = max(job_pressure, match_pressure, resume_pressure)

        stagnation_pressure = 0.0
        if self.system_metrics.get("no_progress_minutes", 0.0) >30:
            stagnation_pressure = 0.4

        error_pressure = min(
            self.system_metrics.get("failure_rate", 0.0) * 2,
            1.0
        )

        memory_pressure = (
            0.6 * capacity_pressure +
            0.25 * stagnation_pressure +
            0.15 * error_pressure
        )

        return min(memory_pressure, 1.0)

    async def brain3_reflection_loop(self):
        """Brain3 reflection loop and control"""
        logger.info("Brain3 reflection loop started")

        HIGH_PRESSURE = 0.7
        LOW_PRESSURE = 0.4
        

        while self.is_running:
            try:

                now = datetime.now()
                await asyncio.sleep(60)

                await self._update_system_metrics()

                global_metrics = await self.shared_context.get_all_metrics()

                users =  await self.shared_context.get_active_users()
                for user_id in users:
                    resume_upload=await self.shared_context.read(f"new_resume_upload_{user_id}")
                    if not isinstance(resume_upload, dict):
                        continue
                    
                    reflection_window = resume_upload.copy()
                
                    has_new_evidence = any([
                        global_metrics.get("jobs_scraped_today", 0) >0,
                        global_metrics.get("matches_created_today", 0) >0,
                        global_metrics.get("reports_generated_today", 0) >0,
                    ])

                    if not has_new_evidence:
                        logger.info("No new evidemce found brain3 reflection idle")
                        continue

                    outcome_metrics = await self.shared_context.pop(f"outcome_metrics_{user_id}")
                    if outcome_metrics:
                        await self.cognitive_brain.learn_from_outcomes(outcome_metrics)

                    # TASKS RECORVER BRAIN3 STARTS HERE 
                    errors = await self.cognitive_brain.detected_errors(self.system_metrics)

                    await self.cognitive_brain.autonomous_recovery(errors)

                    for error in errors:
                        issue = error.get("issue", "unknown")

                        attempts = self.issue_attempts.get(issue, 0)

                        if attempts < self.max_self_heal_attempts:
                            self.issue_attempts[issue] =  attempts + 1
                            error["human_required"] = False
                        else:
                            error["human_required"] = True
                            error["severity"] = "critical"
                    
                    await self.cognitive_brain.check_signals_notification(errors)

                    memory_pressure = self.calculate_memory_pressure()
                    memory_pressure = max(0.0, min(memory_pressure, 1.0))
                    self.system_metrics["memory_pressure"] = memory_pressure

                    maintenance_allowed = (
                    await self.shared_context.read("maintenance_allowed")
                    )

                    if memory_pressure >= HIGH_PRESSURE and not maintenance_allowed:
                        await self.shared_context.write(
                            "maintenance_allowed",
                            True,
                            "brain3"
                        )

                        await self.shared_context.write(
                            "maintenance_command",
                            {"run": True},
                            "brain3"
                        )
                        logger.warning(
                            f"brain3 triggered MaintenanceAgent due to High Pressure"
                            f"(pressure={memory_pressure:.2})"
                        )
                    
                    elif memory_pressure <=LOW_PRESSURE and maintenance_allowed:
                        await self.shared_context.write(
                            "maintenance_allowed",
                            False,
                            "brain3"
                        )

                        logger.info(
                            f"Brain3 released maintenance agent"
                            f"(pressure{memory_pressure:.2})"
                        )                 

                    if not self.cognitive_brain.should_reflect(self.system_metrics):
                        logger.debug("Brain3 No reflection needed yet")
                        continue

                    business_metrics = await self.shared_context.get_all_metrics()
                    
                    # Gathering context
                    recent_events = list(self.episodic_memory.get_recent_summary(limit=10))
                    memory_summary = f"""

        System Health Metrics:
        -Failure rate: {self.system_metrics['failure_rate']:.1%}
        -Stuck Tasks: {self.system_metrics['stuck_tasks']}
        -Agent_utilization: {self.system_metrics['agent_utilization']}
        -Memory Maintenance: {self.system_metrics['memory_pressure']}

        Business Metrics:
        -Jobs Scraped Today: {business_metrics.get('jobs_scraped_today', 0)}
        -Matches Created Today: {business_metrics.get('matches_created_today', 0)}
        -Reports Generated Today: {business_metrics.get('reports_generated_today', 0)}
        """

                    logger.info("Brain 3 Reflecting on system state...")

                    decision = await self.cognitive_brain.think(
                        system_metrics = self.system_metrics,
                        recent_events=recent_events,
                        memory_summary= str(memory_summary),
                    )

                    decision.has_evidence = has_new_evidence

                    remaining = reflection_window.get("remaining_cycles", 0) -1

                    if remaining <=0:
                        await self.shared_context.pop(f"new_resume_upload_{user_id}")
                        logger.info("brain3 reasoning window closed")
                    
                    else:
                        resume_upload["remaining_cycles"]  = remaining
                        await self.shared_context.write(
                            f"new_resume_upload_{user_id}",
                            resume_upload,
                            "brain3"
                        )
                    
                    logger.info(f" Brain-3 Decision {decision.intent}")
                    logger.info(f"Reasoning {decision.reasoning}")
                    logger.info(f" Confidence {decision.confidence:.1%}")


                    control_signals =  await self.cognitive_brain.apply_decision(decision)

                    for signal in control_signals:
                        await self.apply_control(signal)
                    
                    await self.shared_context.write("maintenance_allowed",
                        not any(
                            s.apply_to == "system" and s.action == "pause"
                            for s in control_signals
                        ),
                        "brain3"
                    )
                    self.cognitive_brain.ingest_feedback({
                        "decision": decision.intent,
                        "signal_applied": len(control_signals),
                        "system_metrics": self.system_metrics.copy(),
                        "business_metrics": business_metrics,
                        "timestamp": datetime.now().isoformat()
                    })

            except Exception as e:
                logger.info(f" Brain3 refelction loop error{e}", exc_info=True)

    
    async def _retry_failed_tasks(self, agent_name: str = None):
        """For retrying tasks that failed"""
        if agent_name:
            agent = self.agents.get(agent_name)
            if agent:

                logger.info(f"Retrying tasks for {agent_name}")
        else:
            logger.info("Retrying all Failed tasks")
    
    async def _escalate_priority(self, task_id: str):
        """Escalate task Priority"""
        logger.info(f"Escalating priority for {task_id}")


    def get_status(self):
        return {
            "orchestrator": "brain_2",
            "running": True,
            "uptime_seconds": int(time.time() - self.start_time),
            "agents_registered": list(self.agents.keys()),
            "agents_count": len(self.agents),
            "event_processed": self.event_processed,
            "last_event": self.last_event
        }

    # Core Event Processing 

    async def event_process(self, event: Dict):
        """FIXED: Process events through Cognitive Orchestrator"""
        logger.info(f"📥 Processing event: {event.get('type')}")

        try:
            # Cognitive orchestrator decides and executes
            decision = await self.cognitive.decide(event)
            
            agents_run = decision.get("agents", [])
            reasoning = decision.get("reasoning", "")
            status = decision.get("status", "unknown")

            if status == "error":
                logger.error(f" Orchestration error: {reasoning}")
                return

            if agents_run:
                logger.info(f" Orchestration complete: {len(agents_run)} agents ran")
                logger.info(f" Reasoning: {reasoning}")
                self.stats["agents_activated"] += len(agents_run)
            else:
                logger.info(f" No agents needed: {reasoning}")

            self.stats["events_processed"] += 1

        except Exception as e:
            logger.error(f" Event processing error: {e}", exc_info=True)
          
    async def event_processed_loop(self):
        """Continuously process events from the queue"""
        logger.info("Event processing loop started")

        while self.is_running:
            try:
                event = await self.event_queue.get()
                await self.event_process(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                await asyncio.sleep(0.1)
 
    async def memory_maintenance_loop(self):
        """Memory Maintenance Worker only act on Command of Brain3"""

        self.maintenance_running = True
        logger.info("Maintenance worker started on Commands of Brain3")

        while self.maintenance_running:
            try:
                allowed = await self.shared_context.read("maintenance_allowed")
                if allowed is False:
                    logger.info("Maintenance Blocked by Brain3")
                    await asyncio.sleep(5)
                    continue

                decision =  await self.shared_context.read("maintenance_command")
                if not decision or not decision.get("run", False):
                    await asyncio.sleep(2)
                    continue


                logger.info("Brain3 authorized maintenance run")

                memory_agent = self.agents.get("MemoryMaintenanceAgent")
                if not memory_agent:
                    logger.warning("No Memory agent is found")
                    await asyncio.sleep(5)
                    continue

                result = await memory_agent.run_cycle()

                await self.shared_context.write(
                    "maintenance_command",
                    {"run": False},
                    "MaintenanceWorker"
                )

                logger.info(f"Maintenance result {result}")
            except Exception as e:
                logger.error(f"Maintenance Loop error", exc_info=True)
                await asyncio.sleep(3)
        
        self.maintenance_running = False
        logger.info(f"MaintenanceWorker stopped")
    #  Stats Reporting 
    async def stats_reporter_loop(self):
        """Periodically report system stats"""
        while self.is_running:
            try:
                await asyncio.sleep(getattr(self.settings, "stats_interval", 300)) 
                if self.stats['start_time']:
                    self.stats['uptime_seconds'] = (datetime.now() - self.stats['start_time']).total_seconds()

                global_metrics = await self.shared_context.read("global_metrics")
                logger.info("=" * 60)
                logger.info("AUTONOMOUS SYSTEM STATS")
                logger.info(f"Events Processed: {self.stats['events_processed']}")
                logger.info(f"Agents Activated: {self.stats['agents_activated']}")
                logger.info(f"Uptime Hours: {self.stats['uptime_seconds']/3600:.2f}")

                if global_metrics:
                    logger.info(f"Today's metrics: {global_metrics}")

                for name, agent in self.agents.items():
                    success_rate = self.episodic_memory.get_success_rate(name, "any")
                    logger.info(f"{name} - Completed: {agent.metrics['task_completed']}, Failed: {agent.metrics['task_failed']}, Success rate: {success_rate:.2%}")

                logger.info("=" * 60)
            except Exception as e:
                logger.error("stats reporter loop error: {e}")

    async def start(self):
        """Start autonomous orchestrator and all loops"""
        async with self.started_lock:
            if self._started:
                logger.warning(f"AutonomousOrchestrator already started - Skipping deduplication start")
                return
            self._started = True

        logger.info("="*60)
        logger.info("Autonomous System Starting")
        logger.info("brain-3 Starting")
        logger.info("="*60)

        self.is_running = True
        self.stats['start_time'] = datetime.now()


        self.initialize_refetch_loop()

        tasks = [
            self.safe_runner.create_task(
                name = "event_processed_loop",
                coro = self.event_processed_loop(),
                severity = "critical",
                issue = "event_processed_loop_crash",
                source = "brain2"
            ),

            self.safe_runner.create_task(
                name = "memory_maintenance_loop",
                coro = self.memory_maintenance_loop(),
                severity = "critical",
                issue = "memory_maintenance_loop_crash",
                source = "brain2"
            ),
            self.safe_runner.create_task(
                name = "stats_reporter_loop",
                coro = self.stats_reporter_loop(),
                severity = "critical",
                issue = "stats_reporter_loop_crash",
                source= "brain2"
            ),
            # self.safe_runner.create_task(
            #     name="brain3_reflection_loop",
            #     coro=self.brain3_reflection_loop(),
            #     severity="critical",
            #     issue="brain3_reflection_loop_crashed",
            #     source="brain3"
            # ),
            # self.safe_runner.create_task(
            #     name="brain4_outcome_loop",
            #     coro=self.outcome_loop.run_loop(internal_seconds=120),
            #     severity="critical",
            #     issue="brain4_outcome_loop_creash",
            #     source="brain4"
            # ),
            self.safe_runner.create_task(
                name="langgraph_refetch_loop",
                coro=self.listener.refetch_job_listener(),
                severity="critical",
                issue = "langgraph_loop_crash",
                source="brain2"
            )
        ]
        if settings.BRAIN3_LOOP_ENABLED:
            tasks.append(
                    self.safe_runner.create_task(
                    name="brain3_reflection_loop",
                    coro=self.brain3_reflection_loop(),
                    severity="critical",
                    issue="brain3_reflection_loop_crash",
                    source="brain3"
                )
            )

        # Conditional loops for cheap production safety
        else:
            logger.warning("Brain3 loop Disabled")
        
        if settings.BRAIN4_OUTCOME_LOOP_ENABLED:
            tasks.append(
                self.safe_runner.create_task(
                    name="brain4_outcome_loop",
                    coro=self.outcome_loop.run_loop(internal_seconds=60),
                    severity="critical",
                    issue="brain4_outcome_loop_crash",
                    source="brain4"
                )
            )
        else:
            logger.warning("Brain4 loop Disabled")
        
        if settings.EVENT_MONITOR_LOOP_ENABLED:
            tasks.append(
                self.safe_runner.create_task(
                    name="event_monitor_loop",
                    coro=self.event_monitor.monitor_loop(self.event_queue),
                    severity="critical",
                    issue="event_monitor_loop_crash",
                    source="brain2"
                )
            )
        else:
            logger.warning("Event monitor loop Disabled")

        logger.info("All systems operational")
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            await self.stop()

    async def stop(self):
        """Stop autonomous orchestrator"""
        logger.info("Stopping autonomous system")
        self.is_running = False
        self.maintenance_loop = False

        if hasattr(self, 'outcome_loop'):
            await self.agent_app.shutdown()
            
        await asyncio.sleep(2)
        logger.info(f"Final stats: Events processed: {self.stats['events_processed']}, Agents activated: {self.stats['agents_activated']}")

    async def notify_new_jobs(self, job_count: int, source:str = "scraper", target_resume_id: str = None):
        """Notifying System about new Jobs"""

        try:
            await self.shared_context.write(
                key="new_jobs",
                value={
                    "count": job_count,
                    "source": source,
                    "target_resume_id": target_resume_id,
                    "timestamp": datetime.now().isoformat() 
                },
                agent_name="System"
            )
            logger.info(f" Notifies jobs {job_count} from {source}")
            if target_resume_id:
                logger.info(f" Target Resume {target_resume_id}")
            
            ## Triggering event with target info
            await self.event_queue.put({
                "type": "new_jobs",
                "data": {
                    "job_count": job_count,
                    "source": source,
                    "target_resume_id": target_resume_id,
                },
                "timestamp": datetime.now().isoformat()
            })
        
        except Exception as e:
            logger.info(f"Failed to notify jobs {e}")

    async def notify_matches_created(self, match_count: int, resume_id: str):
        await self.shared_context.update_metrics("matches_created_today", match_count)
        if match_count >= 5:
            await self.event_queue.put({"type": "report_ready", "data": {"resume_id": resume_id, "match_count": match_count}})

    
    
   







                


                      
                      
                      