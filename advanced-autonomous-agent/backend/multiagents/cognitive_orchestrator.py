
import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from backend.config.settings import Settings



try:
    import structlog

    logger = structlog.get_logger()
except Exception:
    logger = logging.getLogger("cognitive_orchestrator")
    logging.basicConfig(level=logging.INFO)

settings = Settings() 

import re

def parse_json_loose(text: str) -> Union[Dict, List, Any]:
    """Try to extract JSON from text robustly and parse it."""
    if not text:
        return {}
    
    try:
        return json.loads(text)
    except Exception:
        pass
    
    m = re.search(r"```json\s*([\s\S]*?)```", text, flags=re.I)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # first 
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
  
    return {}


@dataclass
class OrchestrationTask:
    id: str
    description: str
    agent: str
    tool: Optional[str] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    retries: int = 0
    status: str = "pending"  
    result: Optional[Dict[str, Any]] = None
    category: str = "general"


@dataclass
class Plan:
    id: str
    goal: str
    tasks: List[OrchestrationTask] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    context: Dict[str, Any] = field(default_factory=dict)


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
        llm: Optional[Any] = None,
        planner_model: str = "llama-3.3-70b-versatile",
        planner_temp: float = 0.0,
        default_timeout: int = 60,
    ):

        self.agents = agents or {}
        self.decision_engine = decision_engine
        self.episodic_memory = episodic_memory
        self.settings = settings
        self.shared_context = shared_context
        self.guardrails = guardrails
        self.memory = memory

        from groq import Groq
        self.groq_client = Groq(api_key= settings.GROQ_API_KEY)
        self.llm = True
        self.planner_model = planner_model
        self.planner_temp = planner_temp


        self.plan_store: Dict[str, Plan] = {}
        self.plan_lock = asyncio.Lock()

        # basic message bus: channel -> list of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

        # runtime tracking
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.default_timeout = default_timeout

   
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

    
    # Planner prompt & LLM wrapper
  
    def _planner_prompt(self, goal: str, system_state: Dict[str, Any], context: Dict[str, Any]) -> str:

        safe_system_state = {k: str(v) for k, v in system_state.items()}
        context_keys = list(context.keys())

        return (
            f"You are the Master Planner for an autonomous multi-agent system.\n"
            f"Available agents: {list(self.agents.keys())}\n\n"
            f"Convert this HIGH-LEVEL GOAL into 3-8 actionable tasks. For each task provide:\n"
            f"- id (unique)\n- description\n- agent (choose one of available agents)\n- tool (optional)\n- inputs (keys expected from plan context)\n- depends_on (list of task ids this task depends on)\n\n"
            f"Respond ONLY as valid JSON with keys: goal, plan_id, tasks (array).\n"
            f"SYSTEM_STATE: {json.dumps(safe_system_state)}\n"
            f"CONTEXT: {json.dumps((context_keys))}\n\n"
            f"High-level goal: {goal}\n"
        )

    async def _call_llm(self, prompt: str) -> str:
        try:
            response = self.groq_client.chat.completions.create(
                model=self.planner_model,
                temperature=self.planner_temp,
                messages=[
                    {"role": "system", "content": "You are a planning and verification engine."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.exception("Groq LLM call failed", error=str(e))
            return ""
    
    async def _determine_agents(self, event_type: str, event_data: Dict) -> List[str]:
        """
        FIXED: Determine which agents should run based on event
        """
        # Check event type
        if event_type == "new_resume":
            logger.info("📄 New resume - Running full pipeline")
            return [
                "JobScraperAgent",
                "ResumeMatcherAgent",
                "ReportGeneratorAgent",
                "NotificationAgent"
            ]
        
        elif event_type == "new_jobs":
            logger.info("💼 New jobs - Running matcher + report + notification")
            return [
                "ResumeMatcherAgent",
                "ReportGeneratorAgent",
                "NotificationAgent"
            ]
        
        elif event_type == "report_ready":
            logger.info("📧 Report ready - Running notification")
            return ["NotificationAgent"]
        
        elif event_type == "periodic_check":
            agent_name = event_data.get("agent", "")
            
            if agent_name == "JobScraperAgent":
                resumes = self.memory.resume_collection.get()
                jobs = self.memory.job_collection.get()
                job_count = len(jobs.get("ids", []) if jobs else 0)

                if resumes and resumes.get("ids") and job_count < 10:
                    logger.info(" Periodic Job scraping needed")
                    return ["JobScraperAgent", "ResumeMatcherAgent", "ReportGeneratorAgent", "NotificationAgent"]

            
            elif agent_name == "ResumeMatcherAgent":
                jobs = self.memory.job_collection.get()
                job_count = len(jobs.get("ids", []) if jobs else 0)
                if job_count > 0:
                    matches = self.memory.match_collection.get()
                    match_count = len(matches.get("ids", [])) if matches else 0
                    if match_count < job_count:
                        logger.info("🔍 Periodic: Matching needed")
                        return ["ResumeMatcherAgent", "ReportGeneratorAgent", "NotificationAgent"]
            
            elif agent_name == "ReportGeneratorAgent":
                prefs = self.memory.preferences_collection.get()
                if prefs and prefs.get("ids"):
                    logger.info("🔍 Periodic: Checking for reports")
                    return ["ReportGeneratorAgent", "NotificationAgent"]
            
        logger.info("✅ No agents needed")
        return []


    async def _plan_goal(self, goal: str, system_state: Dict[str, Any], context: Dict[str, Any]) -> Plan:
        """Create a Plan for a given goal using LLM if available, otherwise fallback to heuristic."""
        prompt = self._planner_prompt(goal, system_state, context)
        raw = await self._call_llm(prompt)
        plan_json = parse_json_loose(raw) if raw else {}

        if plan_json and isinstance(plan_json, dict) and "tasks" in plan_json:
            # build Plan
            pid = plan_json.get("plan_id") or f"plan-{int(datetime.now().timestamp())}"
            tasks_raw = plan_json.get("tasks", [])
            tasks = []
            for t in tasks_raw:
                category =  "memory" if t.get("agent") == "MemoryMaintenanceAgent" else t.get("category", "general")
                tasks.append(
                    OrchestrationTask(
                        id=str(t.get("id") or f"task-{len(tasks)+1}"),
                        description=str(t.get("description", "")),
                        agent=str(t.get("agent", "")),
                        tool=t.get("tool"),
                        inputs=t.get("inputs", {}) or {},
                        depends_on=t.get("depends_on", []) or [],
                        category=category
                    )
                )
            plan = Plan(id=pid, goal=goal, tasks=tasks, context=context)
        else:
            # fallback heuristic
            pid = f"plan-fallback-{int(datetime.now().timestamp())}"
            tasks = []
            # best-effort mapping for common goals
            if not goal:
                perform = "Perform routine system check"

            if "scrape" in goal.lower() or "job" in goal.lower():
                if "JobScraperAgent" in self.agents:
                    tasks.append(
                        OrchestrationTask(
                            id="task_scrape",
                            description="Scrape jobs (fallback)",
                            agent="JobScraperAgent",
                            inputs=context or {},
                        )
                    )
                if "ResumeMatcherAgent" in self.agents:
                    tasks.append(
                        OrchestrationTask(
                            id="task_match",
                            description="Match resumes to jobs (fallback)",
                            agent="ResumeMatcherAgent",
                            inputs=context or {},
                            depends_on=["task_scrape"] if any(t.id == "task_scrape" for t in tasks) else [],
                        )
                    )
                if "ReportGeneratorAgent" in self.agents:
                    tasks.append(
                        OrchestrationTask(
                            id="task_report",
                            description="Generate report (fallback)",
                            agent="ReportGeneratorAgent",
                            inputs=context or {},
                            depends_on=[t.id for t in tasks if t.agent in ("JobScraperAgent", "ResumeMatcherAgent")],
                        )
                    )
            else:
                # generic: run first available agent
                first_agent = next(iter(self.agents.keys()), None)
                if first_agent:

                    category = "memory" if first_agent == "MemoryMaintenanceAgent" else "general"
                    tasks.append(
                        OrchestrationTask(
                            id="task_1",
                            description=f"Fallback single task for goal: {goal}",
                            agent=first_agent,
                            inputs=context or {},
                            category=category
                        )
                    )
            plan = Plan(id=pid, goal=goal, tasks=tasks, context=context)

        async with self.plan_lock:
            self.plan_store[plan.id] = plan
        logger.info("Planner created plan", plan_id=plan.id, task_count=len(plan.tasks))
        return plan


    # getting goal from event
    def derive_goal_from_event(self, event):
        event_type = event.get('type')
        agent = event.get('agent', '')

        if event_type == "periodic_check":
            if agent == "JobScraperAgent":
                return "Check if new job scraping is needed based on system state"

            elif agent == "ResumeMatcherAgent":
                return "Check if resume matching is needed for recent jobs"

            elif agent == "ReportGeneratorAgent":
                return "Check if any reports need to be generated"

            else:
                return "Perform routine maintenance and system health check"

        if event_type in ("new_resume", "new_uploads"):
            resume_id = event.get('data', {}).get('resume_id')
            return f"Process new resumes {resume_id}: extract skills, match jobs, notify user"
        
        if event_type in ("new_jobs", "scrape_jobs"):
            return "Match resumes against new jobs and generate reports"

        if event_type == "autonomous_goal":
            goal = event.get('data', {}).get('Goal') or event.get('data', {}).get('goal')
            if goal:
                return str(goal)
        
        return "Perform routine memory maintenance"
   
    # Plan execution
 
    async def execute_plan(self, plan: Plan) -> Dict[str, Any]:
        """Execute tasks in plan obeying dependencies, retries, and verification."""
        logger.info("Executing plan", plan_id=plan.id, goal=plan.goal)
        tasks = plan.tasks
        task_index = {t.id: t for t in tasks}

        async def can_run(task: OrchestrationTask) -> bool:
            for dep in task.depends_on:
                dep_task = task_index.get(dep)
                if not dep_task or dep_task.status != "success":
                    return False
            return True

        stalled = False
        while True:
            made_progress = False

            for t in tasks:
                if t.status != "pending":
                    continue
                if not await can_run(t):
                    continue

                agent_name = t.agent
                agent = self.agents.get(agent_name)
                if not agent:
                    logger.warning("Assigned agent not found; marking skipped", agent=agent_name, task_id=t.id)
                    t.status = "skipped"
                    made_progress = True
                    continue

                payload = {
                    "plan_id": plan.id,
                    "task_id": t.id,
                    "goal": plan.goal,
                    "task_desc": t.description,
                    "inputs": t.inputs,
                    "plan_context": plan.context,
                }

                logger.info("Dispatching task", plan_id=plan.id, task_id=t.id, agent=agent_name)
                t.status = "running"
                made_progress = True

                # run agent with timeout and robust call strategy
                try:
                    response = None
                    
                    if hasattr(agent, "run") and callable(getattr(agent, "run")):
                        coro = agent.run(payload)
                        response = await asyncio.wait_for(coro, timeout=self.default_timeout)
                  
                    elif hasattr(agent, "run_with_payload") and callable(getattr(agent, "run_with_payload")):
                        coro = agent.run_with_payload(payload)
                        response = await asyncio.wait_for(coro, timeout=self.default_timeout)
                   
                    elif hasattr(agent, "run_agentic_cycle") and callable(getattr(agent, "run_agentic_cycle")):
                        coro = agent.run_agentic_cycle()
                        response = await asyncio.wait_for(coro, timeout=self.default_timeout)
                    
                    elif hasattr(agent, "run_cycle") and callable(getattr(agent, "run_cycle")):
                        coro = agent.run_cycle(payload)
                        response = await asyncio.wait_for(coro, timeout=self.default_timeout)
                    else:
                        raise RuntimeError("Agent has no runnable entrypoint")
                except asyncio.TimeoutError:
                    logger.warning("Task timeout", task_id=t.id, agent=agent_name)
                    t.status = "failure"
                    t.retries += 1
                    if t.retries <= 2:
                        t.status = "pending"  
                    continue
                except Exception as e:
                    logger.exception("Agent execution error", task_id=t.id, agent=agent_name, error=str(e))
                    t.status = "failure"
                    t.retries += 1
                    if t.retries <= 2:
                        t.status = "pending"
                    t.result = {"status": "error", "error": str(e)}
                    
                    try:
                        self.episodic_memory.record_experiences(
                            agent_name=agent_name,
                            action="task_execution",
                            result=t.result,
                            context={"plan_id": plan.id, "task_id": t.id},
                        )
                    except Exception:
                        logger.exception("episodic_memory.record_experiences failed")
                    continue

               
                verified = await self._verify_task_result(t, response)
                if verified:
                    t.status = "success"
                    t.result = response if isinstance(response, dict) else {"result": response}
                    logger.info("Task completed", task_id=t.id, agent=agent_name)
                    
                    await self.publish(f"plan:{plan.id}:task:{t.id}:done", {"task": asdict(t), "result": t.result})
                    # record success
                    try:
                        self.episodic_memory.record_experiences(
                            agent_name=agent_name,
                            action="task_execution",
                            result=t.result,
                            context={"plan_id": plan.id, "task_id": t.id},
                        )
                    except Exception:
                        logger.exception("episodic_memory.record_experiences failed")
                else:
                    t.status = "failure"
                    t.result = response if isinstance(response, dict) else {"result": response}
                    logger.warning("No Task op", task_id=t.id)
                    # record failure
                    try:
                        self.episodic_memory.record_experiences(
                            agent_name=agent_name,
                            action="task_execution",
                            result=t.result,
                            context={"plan_id": plan.id, "task_id": t.id},
                        )
                    except Exception:
                        logger.exception("episodic_memory.record_experiences failed")

                    remediation_tasks = await self._suggest_remediation(plan, t, t.result)
                    if remediation_tasks:
                        for rt in remediation_tasks:
                            # normalize and append
                            category = "memory" if rt.get("agent") == "MemoryMaintenanceAgent" else rt.get("category", "general")
                            new_task = OrchestrationTask(
                                id=rt.get("id", f"remed-{len(tasks)+1}"),
                                description=rt.get("description", ""),
                                agent=rt.get("agent", ""),
                                tool=rt.get("tool"),
                                inputs=rt.get("inputs", {}),
                                depends_on=rt.get("depends_on", []),
                                category=category
                            )

                            tasks.append(new_task)
                            task_index[new_task.id] = new_task
                        logger.info("Appended remediation tasks", count=len(remediation_tasks))

            if not made_progress:
                if stalled:
                    logger.error("Plan execution stalled - no progress possible", plan_id=plan.id)
                    break
                stalled = True
            else:
                stalled = False

            
            all_done = all(t.status in ("success", "skipped", "failure") for t in tasks)
            if all_done:
                break

        logger.info("Plan execution finished", plan_id=plan.id)
        
        return {"plan_id": plan.id, "tasks": [asdict(t) for t in tasks]}
 
    # Verification & remediation
   
    async def _verify_task_result(self, task: OrchestrationTask, result: Any) -> bool:

            try:
                if isinstance(result, dict) and result.get("status") == "success":
                    return True
                
                if isinstance(result, dict):
                    message = str(result.get("message", "")).lower()
                    if "no work" in message or "nothing to do" in message or "up to date" in message:
                        logger.info(f"Task verified as 'no work' (acceptable)", task_id=task.id)
                        return True
                
                if self.llm:
                    prompt = (
                            f"You are a verifier. Task: {task.id} by agent {task.agent}\n"
                        f"Task description: {task.description}\n"
                        f"Result: {json.dumps(result, default=str)[:2000]}\n\n"
                        f"IMPORTANT: If the agent reports 'no work needed', this is ACCEPTABLE.\n"
                        f"Question: Is the result acceptable? Respond JSON: {{\"ok\": true/false, \"reason\": \"brief\"}}"
                        
                    )

                    raw = await self._call_llm(prompt)
                    parsed = parse_json_loose(raw)
                    if isinstance(parsed, dict):
                        return bool(parsed.get("ok", False))
                
                if result is None:
                    return True
                
                return False
            
            except Exception as e:
                logger.error(f"Verification Failed: Defaulting to False", exc=True)
                return False
                   

    async def _suggest_remediation(self, plan: Plan, task: OrchestrationTask, result: Any) -> Optional[List[Dict[str, Any]]]:
        """Ask LLM to suggest remediation tasks (up to 3). If no LLM, return None."""
        
        if not self.llm:
            return []

        # If the agent said "no work", no remediation needed
        if isinstance(result, dict):
            message = str(result.get("message", "")).lower()
            if "no work" in message or "nothing to do" in message or "up to date" in message:
                logger.info("Remediation skipped: 'no work' message")
                return None
        
        try:
            prompt = (
                f"Task {task.id} failed or produced an unacceptable result.\n"
                f"Task description: {task.description}\n"
                f"Result: {json.dumps(result, default=str)[:1800]}\n\n"
                f"Suggest up to 3 remedial tasks as a JSON array.\n"
                f"Each item MUST include: id, description, agent, inputs, depends_on.\n"
                f"If no remediation needed, respond with an empty JSON array []."
            )

            raw = await self._call_llm(prompt)
            parsed = parse_json_loose(raw)

            # LLM might return {} or something messy
            if not parsed:
                return None

            if isinstance(parsed, list):
                cleaned = []
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    
                    # Normalize fields (LLM often misses fields)
                    cleaned.append({
                        "id": item.get("id", f"remed-{int(datetime.now().timestamp())}"),
                        "description": item.get("description", "Auto-generated remediation task"),
                        "agent": item.get("agent", task.agent),  # default to same agent
                        "tool": item.get("tool"),
                        "inputs": item.get("inputs", {}),
                        "depends_on": item.get("depends_on", [task.id]),
                        "category": item.get("category", "general")
                    })

                return cleaned if cleaned else None

            # If LLM returns a dict instead of list, we ignore it
            return None

        except Exception as e:
            logger.exception("Remediation suggestion failed", error=str(e))
            return None

   
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

    async def _run_agent_legacy(self, agent: Any, payload: Dict[str, Any]):
        """Compatibility wrapper for legacy agents expecting run(payload)."""
        try:
            if hasattr(agent, "run"):
                await agent.run(payload or {})
            elif hasattr(agent, "run_with_payload"):
                await agent.run_with_payload(payload or {})
            elif hasattr(agent, "run_agentic_cycle"):
                await agent.run_agentic_cycle()
            elif hasattr(agent, "run_cycle"):
                await agent.run_cycle(payload or {})
            else:
                raise RuntimeError("Agent has no runnable entrypoint")
        except Exception:
            logger.exception("legacy agent run failed", agent=str(agent))

  
    # System reflection loop
   
    async def system_reflection_loop(self, interval_seconds: int = 300):
        """
        Periodically summarize recent experiences and ask LLM for system-level recommendations.
        Results are stored in shared_context as 'system_recommendations'.
        """
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                
                if hasattr(self.episodic_memory, "get_recent_summary"):
                    summary = self.episodic_memory.get_recent_summary(limit=50)
                else:
                    
                    summary = getattr(self.episodic_memory, "experiences", [])[-50:]
                
                if self.llm:
                    prompt = (
                        "You are the System Analyst for an autonomous agent platform.\n"
                        f"Recent episodic summary (truncated): {json.dumps(summary, default=str)[:4000]}\n\n"
                        "Provide 3 prioritized recommendations to improve system reliability. Respond as JSON: "
                        '{"recommendations": [...], "priorities": [...]}'
                    )
                    raw = await self._call_llm(prompt)
                    parsed = parse_json_loose(raw)
                    if isinstance(parsed, dict) and "recommendations" in parsed:
                        try:
                            await self.shared_context.write("system_recommendations", parsed, "cognitive_orchestrator")
                            logger.info("System recommendations saved")
                        except Exception:
                            logger.exception("shared_context.write failed storing recommendations")
            except Exception:
                logger.exception("system_reflection_loop error")
    
   
