import time
import structlog



logger = structlog.get_logger()

class RecoveryManager:
    """
    Executes Determinsitic  self-healing Actions
    """
    def __init__(self, orchestrator, multi_agent_orchestrator):
        self.orchestrator = orchestrator
        self.multi_agent_orchestrator = multi_agent_orchestrator
        self.max_attempts = 5
        self.cooldown_seconds = 240
        self.attempts = {}
        self.last_action_time = {}

    def _allowed(self, key: str) -> bool:
        now = time.time()
        last = self.last_action_time.get(key, 0)

        if now - last < self.cooldown_seconds:
            return False
        
        self.last_action_time[key] =  now
        return True

    def _register_attempts(self, key: str) -> int:
        self.attempts[key] =  self.attempts.get(key, 0) + 1
        return self.attempts[key]
    
    async def handle_recovery_action(self, event: dict):
        action = event.get("action")
        target = event.get("target")
        key =  f"{action}: {target}"

        if not self._allowed(key):
            logger.warning("Recovery action blocked by cooldown", key=key)
            return 

        attempts = self._register_attempts(key)
        if attempts > self.max_attempts:
            logger.error("Recovery action exceeded max attempts", key=key) 

            await self.multi_agent_orchestrator.cognitive_brain.check_signals_notification([
                {
                    "issue": f"Recovery failed for key{key}",
                    "severity": "critical",
                    "reasoning": "Max attempts exceed manual intervention required."
                }
            ])
            return
        
        logger.warning("Executing recovery action", target=target, action=action, attempts=attempts)

        if action == "restart_loop":
            await self.restart_loop(target)
        
        elif action == "retry_langgraph_workflow":
            await self.retry_langgraph_workflow(target)
        
    async def restart_loop(self, loop_name: str):

        # self.multi_agent_orchestrator.safe_runner._active_tasks.pop(loop_name, None)
        if loop_name == "event_monitor_loop":
            self.orchestrator.safe_runner.create_task(
                name = "event_monitor_loop",
                coro = self.multi_agent_orchestrator.event_monitor.monitor_loop(self.multi_agent_orchestrator.event_queue),
                severity ="critical",
                issue = "event_monitor_loop_crash",
                source= "brain2"
            )
        
        elif loop_name == "event_processed_loop":
            self.orchestrator.safe_runner.create_task(
                name = "event_processed_loop",
                coro = self.multi_agent_orchestrator.event_processed_loop(),
                severity = "critical",
                issue = "event_processed_loop_crash",
                source = "brain2"
            )
        
        elif loop_name == "memory_maintenance_loop":
            self.orchestrator.safe_runner.create_task(
                name = "memory_maintenance_loop",
                coro = self.multi_agent_orchestrator.memory_maintenance_loop(),
                severity = "critical",
                issue = "memory_maintenance_loop_crash",
                source = "brain2"
            )

        elif loop_name == "brain3_reflection_loop":
            self.orchestrator.safe_runner.create_task(
                name = "brain3_reflection_loop",
                coro = self.multi_agent_orchestrator.brain3_reflection_loop(),
                severity = "critical",
                issue = "brain3_reflection_loop_crash",
                source  = "brain3"
            )
        
        elif loop_name == "brain4_outcome_loop":
            self.orchestrator.safe_runner.create_task(
                name = "brain4_outcome_loop",
                coro = self.multi_agent_orchestrator.outcome_loop.run_loop(),
                severity = "critical",
                issue = "brain4_outcome_loop_crash",
                source = "brain4"
            )
        
        elif loop_name == "langgraph_refetch_loop":
            self.orchestrator.safe_runner.create_task(
                name ="langgraph_refetch_loop",
                coro = self.multi_agent_orchestrator.backend_listener.refetch_job_listener(),
                severity = "critical",
                issue = "langgraph_loop_crash",
                source = "brain2"
            )       
        
        else:
            logger.warning("No restart role found for loop", loop_name=loop_name)
    
   




        


        





