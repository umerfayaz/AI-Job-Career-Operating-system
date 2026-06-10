from collections import defaultdict
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from backend.core.event_bus import get_event_bus
from opentelemetry.trace import Status, StatusCode
from backend.observability.tracer import tracer
from backend.multiagents.agents_orchestrator import SharedContext
from sklearn.metrics.pairwise import cosine_similarity
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
import structlog
import time
import numpy as np

logger = structlog.get_logger()
shared_context = SharedContext()
event_bus = get_event_bus()


class ControlSignal(BaseModel):
    apply_to: str = Field(
        description="brain1 | brain2 | system"
    )
    action: str = Field(
        description="pause | resume | boost | reduce | retry | escalate"
    )
    target: Optional[str] = Field(
        description="agent or component name"
    )
    value: Optional[float] = Field(
        description="Optional numeric adjustment"
    )


class CognitiveDecision(BaseModel):
    intent: str
    control_signals: List[ControlSignal] = Field(default_factory=list)
    policy_updates: Dict[str, float] = Field(default_factory=dict)
    has_evidence: bool =  False

    confidence: float = Field(
        default=0.5,
        ge=0.0, 
        le=1.0
    )
    reasoning: Optional[str] = None
    reflection: Optional[str] = None
    error_detected: bool = False
    human_required: bool = False
    severity: str = "info"

class CognitiveBrain:
    """Brain3 Stretegic Control"""
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self.event_bus = event_bus
        base_llm = ChatGroq(
        model = "openai/gpt-oss-20b",
        temperature=0.25
        )

        self.llm = base_llm.bind_tools(
        tools=[CognitiveDecision],
        tool_choice={
            "type": "function",
            "function": {"name": "CognitiveDecision"}
        }

        )

        from langchain_core.output_parsers.openai_tools import PydanticToolsParser
        self.parser = PydanticToolsParser(
            tools=[CognitiveDecision],
            first_tool_only=True
        )

        self.last_decision: Optional[CognitiveDecision] = None
        self.last_reflection_time: Optional[datetime] = None

        self.policy_state: Dict[str, float] = {
            "min_job_similarity_delta": 0.16,
            "max_same_source_ratio": 0.7
        }

        self.alert_cooldown_seconds = 300
        self.last_alert_time = {}
        self.execution_feedback: List[Dict] = []
        self.reflection_interval = timedelta(minutes=10)
    
    async def pull_system_error(self, limit=20) -> List[Dict]:

        try: 
            events = await self.event_bus.get_recent("SYSTEM_ERROR", limit=limit)

            errors = []

            for e in events:
                errors.append({
                    "issue": e.get("issue", "unknown_issue"),
                    "severity": e.get("level", "warning"),
                    "reasoning": f"[{e.get('source')}] {e.get('message')}",
                    "source": e.get("source"),
                    "payload": e.get("payload", {}),
                    "timestamp": e.get("timestamp"),
                    "event": e 
                })
            
            return errors
        
        except Exception as e:
            logger.error("brain3 Failed to pull system errors", error=str(e))
            return []           

    async def detected_errors(self, system_metrics: Dict) -> List[Dict]:
        errors = []

        if system_metrics.get("failure_rate", 0) > 0.2:
            errors.append({
                "issue":"High Failure rate detected",
                "severity": "warning",
                "reasoning": f"{system_metrics['failure_rate']} Increasing failure rate"
            })
        
        if system_metrics.get("error_count_last_hour", 0) > 1:
            errors.append({
                "issue": "High error count in last hour",
                "severity": "critical",
                "reasoning": f"{system_metrics['error_count_last_hour']} errors detected in last hour"
            })
        
        if system_metrics.get("stuck_tasks", 0) > 0:
            errors.append({
                "issue": "stuck tasks detected",
                "severity": "critical",
                "reasoning": f"{system_metrics['stuck_tasks']} task have not progressed"
            })
        
        
        system_errors = await self.pull_system_error(limit=20)

        errors.extend(system_errors)
        
        return errors
    
    async def emit_recovery_action(self, action: str, target: str, severity = "warning"):
        await self.event_bus.emit({
            "type": "RECOVERY_ACTION",
            "source": "brain3",
            "action": action, 
            "target": target,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        })

    
    async def autonomous_recovery(self, errors: List[Dict]):

            normalized = []

            for e in errors:
                if isinstance(errors, str):
                    normalized.append({"issue": e, "severity": "warning"})
                elif isinstance(errors, dict):
                        normalized.append(e)
            errors = normalized

            for error in errors:
                issue = error.get("issue", "unknown_issue")
                severity = error.get("severity", "warning")

                if issue == "event_processed_loop_crash":
                    if severity == "critical":
                        await self.emit_recovery_action(
                        action = "restart_loop",
                        target = "event_processed_loop",
                        severity = "critical",
                    ) 
                
                elif issue == "health_check_loop_crash":
                    await self.emit_recovery_action(
                        action = "restart_loop",
                        target = "health_check_loop",
                        severity = "critical",
                    )

                elif issue == "event_monitor_loop_crash":
                    await self.emit_recovery_action(
                        action = "restart_loop",
                        target = "event_monitor_loop",
                        severity = "critical",
                    )
                elif issue == "memory_maintenance_loop_crash":
                    await self.emit_recovery_action(
                        action = "restart_loop",
                        target = "memory_maintenance_loop",
                        severity = "critical",
                    )
                
                elif issue == "stats_reporter_loop_crash":
                    await self.emit_recovery_action(
                        action = "restart_loop",
                        target = "stats_reporter_loop",
                        severity = "critical",
                    )
                
                elif issue == "goal_generation_loop_crash":
                    await self.emit_recovery_action(
                        action = "restart_loop",
                        target = "autonomous_goal_generation_loop",
                        severity = "critical",
                    )
                
                elif issue == "brain3_reflection_loop_crash":
                    await self.emit_recovery_action(
                        action = "restart_loop",
                        target = "brain3_reflection_loop",
                        severity = "critical",
                    )
                
                elif issue == "brain4_outcome_loop_crash":
                    await self.emit_recovery_action(
                        action = "restart_loop",
                        target = "brain4_outcome_loop",
                        severity = "critical"
                )
                
                elif issue == "langgraph_loop_crash":
                    await self.emit_recovery_action(
                        action = "restart_loop",
                        target = "langgraph_refetch_loop",
                        severity = "critical",
                    )
    
    async def check_signals_notification(self, errors: List[Dict]):
        now = time.time()

        for error in errors:
            severity = error.get("severity")
            human_required = severity in ["critical"]
            issue = error.get("issue")

            last_time = self.last_alert_time.get(issue, 0)
            if (now - last_time) < self.alert_cooldown_seconds:
                continue

            self.last_alert_time[issue] = now

            event = {
                "type": "BRAIN3_ALERT",
                "intent": "system_health",
                "source": "brain3",
                "level": severity,
                "message": error.get("issue"),
                "payload": {
                    "confidence": 0.9,
                    "reasoning": error.get("reasoning"),
                    "human_required": human_required
                },
                "timestamp": datetime.now().isoformat()
            }

            await self.event_bus.emit(event)
            if human_required:
                logger.warning(f"Brain3 detect critical issue for human attention: {error['issue']}")


    def should_reflect(self, system_metrics: Dict) -> bool:
         # First-time reflection
        if not self.last_reflection_time:
            return True

        # Reactive reflection (problems detected)
        if system_metrics.get("failure_rate", 0) > 0.2:
            return True

        if system_metrics.get("stuck_tasks", 0) > 0:
            return True


        if system_metrics.get("memory_pressure", 0) > 0.8:
            return True
        
        # Detecting Outcome Failures

        if system_metrics.get("task_started_last_hour", 0) > 5:
            if system_metrics.get("progress_rate", 1.0) < 0.3:
                return True 

        if system_metrics.get("match_jobs_count") >0.8:
            return True

        if system_metrics.get("jobs_scraped_today")  >50:
            return True
        
        
        if system_metrics.get("task_completed_last_hour", 0) == 0:
            return True
        
        if system_metrics.get("error_count_last_hour", 0) > 1:
            return True   
        
        if system_metrics.get("no_progress_minutes", 0) > 30:
            return True
        
        if len(system_metrics.get("idle_agents", [])) > 0:
            return True
 
        if datetime.now() - self.last_reflection_time > self.reflection_interval:
            return True

        return False
    
    async def learn_from_outcomes(self, outcome_metrics: Dict):

        rejection_rate = outcome_metrics.get("rejection_rate", 0)
        no_response_rate = outcome_metrics.get("no_response_rate", 0)
        reply_rate = outcome_metrics.get("reply_rate", 0)


        if rejection_rate > 0.6:
            self.policy_state["min_job_similarity_delta"] = min(
                self.policy_state["min_job_similarity_delta"] + 0.02, 0.4
            )
        
        if no_response_rate > 0.5:
            self.policy_state["max_same_source_ratio"] = max(
                self.policy_state["max_same_source_ratio"] -0.05, 0.3
            )
        
        if reply_rate > 0.15:
            self.policy_state["resume_weight_boost"] = min(
                self.policy_state.get("resume_weight_boost", 1.0) + 0.1, 2.0
            )
    
    async def merge_external_policy(self, external_policy: Dict):
            for  k, v in external_policy.items():
                if v is None:
                    continue

                logger.info("Applying stretgic policy update", key=k, value=v)
                self.policy_state[k] = v 


    def _build_context(self, system_metrics: Dict, recent_events: List[Dict], memory_summary: str) ->str:
        """Build Comprehensive context for brain3"""

        events_str = "\n".join([
            f" -{e.get('event_type', 'uknown')}: {e.get('description', '')}"
            for e in recent_events[-5:]
        ])

        feedback_str = "\n".join([
            f" - Decision {f.get('decision')}, Signals: {f.get('signals_applied')}- Time: {f.get('timestamp')}"
            for f in self.execution_feedback[-3:]
        ])


        return f"""
    
    SYSTEM HEALTH METRICS:
    Failure Rate: {system_metrics.get('failure_rate', 0):.1%}
    Stuck Task: {system_metrics.get('stuck_tasks', 0)}
    Job Repitation Rate: {system_metrics.get('job_repitation_rate',0):.1%}
    Agent Utilization: {system_metrics.get('agent_utilization', {})}
    Error Count: {system_metrics.get('error_count_last_hour', 0)}
    Scraped Jobs: {system_metrics.get('jobs_scraped_today', 0)}
    Matched Jobs Count: {system_metrics.get('match_jobs_count', 0)}
    Memory Maintenance: {system_metrics.get('memory_pressure', 0)}
    Last Updated: {system_metrics.get('last_updated', 'N/A')}
    Task Completed {system_metrics.get('task_completed_last_hour', 0)}
    Progress Update {system_metrics.get('progress_rate', 0.0):.1%}
    Idle Agents: {system_metrics.get('idle_agents', [])}
    No Progress Minutes: {system_metrics.get('no_progress_minutes', 0)}


    === RECENT SYSTEM EVENTS ===
{events_str or "No recent events"}

=== PREVIOUS DECISIONS & FEEDBACK ===
{feedback_str or "No previous decisions"}

=== CURRENT POLICY STATE ===
{self.policy_state or "No active policies"}

=== MEMORY SUMMARY ===
{memory_summary}

=== YOUR TASK ===
Analyze the system state and decide:
1. Are there any problems that need immediate attention?
2. Should any agents be paused, resumed, or adjusted?
3. Should system resources be increased or decreased?
4. What policy updates would improve long-term performance?

Emit control signals only if action is needed.
        """
    async def think(self, system_metrics: Dict, recent_events: List[Dict], memory_summary: str) -> CognitiveDecision:
        with tracer.start_as_current_span("Brain3.think") as parent_span:
            agent_start = time.time()
            parent_span.set_attribute("metrics.failure_rate", system_metrics.get("failure_rate", 0))
            parent_span.set_attribute("metrics.stuck_tasks", system_metrics.get("stuck_tasks", 0))

            logger.info(
            "Brain3 INPUT",
            metrics=system_metrics,
            policy_state=self.policy_state,
            last_decision=self.last_decision.intent if self.last_decision else None,
            last_confidence=self.last_decision.confidence if self.last_decision else None,
            reflection_due=self.should_reflect(system_metrics),
            )

            system_prompt = SystemMessage(content="""
            You are Brain-3, the strategic control system of a multi-brain autonomous AI.

    CAPABILITIES:
    - Monitor system health and performance
    - Diagnose inefficiencies and failures
    - Emit control signals to Brain-1 (LangGraph) and Brain-2 (Multi-agents)
    - Update long-term system policies

    CONTROL SIGNALS YOU CAN EMIT:
    - pause: Stop an agent or brain temporarily
    - resume: Resume a paused agent or brain
    - reduce: Decrease resource allocation or depth
    - boost: Increase resource allocation or depth
    - retry: Retry failed tasks
    - escalate: Escalate priority of stuck tasks

    TARGET OPTIONS (apply_to field):
    - "brain1": LangGraph orchestrator
    - "brain2": Multi-agent system (specify target agent)
    - "system": System-wide controls

    IMPORTANT:
    - Only emit control signals when you detect actual problems
    - If everything is running smoothly, emit empty control_signals list
    - Be conservative with interventions
    - policy_updates must ONLY contain numeric values
    - do NOT include strings, enums, or strategy names
    - express strategies as numeric thresholds or weights
    - Think strategically, not reactively

    You are an AI architect, not an executor.
            """)

            human_prompt = HumanMessage(content= self._build_context(
                system_metrics,
                recent_events,
                memory_summary
            )
            )

            decision = None

            try:
                with tracer.start_as_current_span("LLM.brain3_decision") as llm_span:
                    llm_start = time.time()
                    MODEL_NAME = "openai/gpt-oss-120b"
                    llm_span.set_attribute("llm.model", MODEL_NAME)

                    response =  await self.llm.ainvoke([system_prompt, human_prompt])
                    if hasattr(response, 'tools') and response.tools:
                        for call in response.tools:
                            if isinstance(call, dict):
                                if '.' in call.get('name', ''):
                                    call['name'] = call['name'].split('.')[-1]
                            elif hasattr(call, 'name'):
                                if 'name' in call and ',' in call['name']:
                                    call['name'] = call['name'].split('.')[-1]

                    # Tracing LLM Latency, Cost , Tokens Observability

                    llm_span.set_attribute("llm.latency_seconds", time.time() - llm_start)

                    usage = getattr(response,"usage", None)
                    llm_span.set_attribute("llm.prompt", human_prompt.content[:500])

                    if usage:
                        llm_span.set_attribute("llm.prompt_tokens", getattr(usage, "prompt_tokens", 0))
                        llm_span.set_attribute("llm.completion_tokens", getattr(usage, "completion_tokens", 0))
                        llm_span.set_attribute("llm.total_tokens", getattr(usage ,"total_tokens", 0))

                        # Model Cost total tokens
                        total_tokens = getattr(usage, "total_tokens", 0)
                        MODEL_COSTS = {
                            "openai/gpt-oss-120b": 0.0001
                        }
                        cost = (total_tokens /1000) * MODEL_COSTS.get(MODEL_NAME, 0)
                        
                        llm_span.set_attribute("llm.estimated_cost_usd", cost) 
                    

                    decision = self.parser.invoke(response) 

                    self.last_decision = decision
                    self.last_reflection_time = datetime.now()
            
            except Exception as e:
                if "llm_span" in locals():
                    logger.exception("Brain3 Decider think Failed")
                    llm_span.record_exception(e)
                    llm_span.set_status(Status(StatusCode.ERROR, str(e)))
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
            
            finally:
                if decision:
                    logger.info(
                        "Brain3 OUTPUT",
                        intent=decision.intent,
                        confidence=decision.confidence,
                        control_signals=[cs.dict() for cs in decision.control_signals],
                        policy_updates=decision.policy_updates
                    )

                    parent_span.set_attribute("decision.intent", decision.intent)
                    parent_span.set_attribute("decision.confidence", decision.confidence)
                    parent_span.set_attribute("control_signals.count", len(decision.control_signals))
                    parent_span.set_attribute("policy_updated.count", len(decision.policy_updates))
                parent_span.set_attribute("agent.latency_seconds", time.time() - agent_start)

            return decision

    def filter_new_jobs(self, jobs):
        min_delta = self.policy_state.get("min_job_similarity_delta", 0.16)
        max_source_ratio = self.policy_state.get("max_same_source_ratio", 0.7)

        seen_embeddings =[]
        source_count = defaultdict(int)
        filtered = []

        for job in jobs:
            emb = job.get("embedding")

            if emb is None:
                filtered.append(job)
                source_count[job.get("source", "unknown")] +=1
                continue
            emb_vector = np.array(emb).reshape(1, -1)

            is_deduplication = False

            for e in seen_embeddings:
                e_vec = np.array(e).reshape(1, -1)
                sim = cosine_similarity(emb_vector, e_vec)[0][0]

                if sim > (1 - min_delta):
                    is_deduplication = True
                    break

            if is_deduplication:
                continue

            source = job.get("source", "unknown")
            if source_count[source] / max(len(filtered, 1)) > max_source_ratio:
                continue

            seen_embeddings.append(emb)
            source_count[source] += 1
            filtered.append(job)
            
        return filtered

    async def apply_decision(self, decision: CognitiveDecision):
        """Apply Stretegic outcomes"""
        with tracer.start_as_current_span("Brain3.apply_decision") as parent_span:
            parent_span.set_attribute("decision.confidence", decision.confidence)

            if decision.confidence < 0.6:
                logger.info("Policy update frozen")
                return []
            
            if not decision.has_evidence:
                logger.info("No new evidence - Policy Frozen")
            
                for k, v in decision.policy_updates.items():
                    self.policy_state[k] = v
                    logger.info(f" Policy updated {k} = {v}")

            for signal in decision.control_signals:
                
                if signal.action == "resume" and signal.target == "memory":
                    await shared_context.write("maintenance_allowed", True, "brain3")
                    await shared_context.write("maintenance_command", {"run": True}, "brain3")
                
                if signal.action == "pause" and signal.target == "memory":
                    await shared_context.write("maintenance_allowed", False, "brain3")
                    await shared_context.write("maintenance_command", {"run": False}, "brain3")

            return decision.control_signals
    
    def ingest_feedback(self, feedback: Dict):
        """Store Execution feedback for learning"""

        self.execution_feedback.append({
            **feedback,
            "timestamp": datetime.now().isoformat()
        })

        self.execution_feedback = self.execution_feedback[-50:]









    




