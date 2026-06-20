import json
import time
from groq import AsyncGroq
from datetime import datetime
import structlog
from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
from backend.config.settings import Settings
from backend.LLMGateway.fallbackmodels import Models



logger = structlog.get_logger()

class stretegic_agent:
    def __init__(self, shared_context, user_intelligence):
        self.settings = Settings()
        self.user_intelligence = user_intelligence
        self.shared_context = shared_context
        self.client = AsyncGroq(api_key=self.settings.GROQ_API_KEY)
        self.models = Models(self.client)


    async def decision_context(self, user_id: str):
        user_snapshot = await self.user_intelligence.get_user_intelligence(user_id)
        summarized_context = self.user_intelligence.build_executive_summary(user_snapshot)

        return {
            "executive_summary": summarized_context
        }

    async def decide(self, metrics: dict, job):
        # Tracing Observability
        with tracer.start_as_current_span("StretegicAgent.decide") as parent_span:
            start_agent = time.time()
            parent_span.set_attribute("agent", "stretegic")
            parent_span.set_attribute("metrics.total", metrics.get("total", 0))
            parent_span.set_attribute("metrics.reply_rate", metrics.get("reply_rate", 0))

            profile = await self.shared_context.read("active_search_profile")
            if profile:
                cooldown_until = profile.get("cooldown_until")
                if cooldown_until:
                    if datetime.now() < datetime.fromisoformat(cooldown_until):
                        logger.info("cooldown active in stretegic_agent - skipping stretegic agent Policy")
                        return {
                            "intent": "no_change",
                            "confidence": 0,
                            "reason": "insufficient_data",
                            "actions": {}
                        }

            pending = await self.shared_context.read("refetch_pending")
            if pending:
                logger.info("Refetch Pending - Skipping Stretegic agent")
                return {
                    "intent": "no_change",
                    "confidence": 0.0,
                    "reason": "insiufficient_data",
                    "actions": {}
                }
            
            user_id = job.get("user_id") if isinstance(job, dict) else None
            run_id = job.get("run_id") or metrics.get("run_id")
            decision_context = await self.decision_context(user_id)
            prompt = self._build_prompt(metrics, decision_context)

            logger.warning(f"Stretegic agent received decision contex", user_id=user_id, decision_context=decision_context)
            logger.warning("Stretegic Prompt size recieved", characters=len(prompt))

            try:
                with tracer.start_as_current_span("LLM.call") as llm_span:
                    start_llm = time.time()

                    llm_result =  await self.models.json_completion(
                        task_type="stretegic_reasoning",
                        messages=[
                            {"role": "system", "content": "You are a careful stretegic agent output JSON only" },
                            {"role": "user", "content": prompt}
                        ]
                    )

                    if not llm_result.get("ok"):
                        return {
                            "intent": "needs_more_data",
                            "confidence": 0.0,
                            "reason": f" LLM Gateway failed: {llm_result.get('error')}",
                            "actions": {"trigger_workflow": False}
                        }

                    llm_span.set_attribute("llm.latency_seconds", time.time() - start_llm)
                    
                    # LLM Token & Cost Tracking
                    usage = llm_result.get("usage")
                    MODEL_NAME = llm_result.get("model", "unknown")
                    llm_span.set_attribute("llm.model", MODEL_NAME)

                    logger.warning(f"LLM Model called inside stretegic agent:{MODEL_NAME}")

                    if usage:
                        llm_span.set_attribute("llm.prompt", prompt[:500])
                        llm_span.set_attribute("llm.prompt_tokens", getattr(usage, "prompt_tokens", 0))
                        llm_span.set_attribute("llm.completion_tokens", getattr(usage ,"completion_tokens", 0))
                        llm_span.set_attribute("llm.total_tokens", getattr(usage, "total_tokens", 0))

                        # Calculating cost per Token LLM
                        total_tokens = getattr(usage, "total_tokens", 0)
                        MODEL_COSTS = {
                            MODEL_NAME: 0.0001
                        }
                        cost = (total_tokens / 1000) * MODEL_COSTS.get(MODEL_NAME, 0)

                        llm_span.set_attribute("llm.estimated_cost_usd", cost)
                    
                    content =  llm_result["content"]
                    result=json.loads(content)
                    actions = result.get("actions", {})

                    logger.warning("Stretegic Agent Decision", result=result)

                    # Saving result summary for the history from agent
                    summary = {
                        "intent": result.get("intent"),
                        "observe": result.get("observe"),
                        "diagnosis": result.get("diagnosis"),
                        "plan": result.get("plan"),
                        "act": result.get("act"),
                        "verify": result.get("verify"),
                        "memory_update": result.get("memory_update"),
                        "actions": actions
                    }

                    # Import shared memory for subagents to read from stretegic agent
                    await self.shared_context.write(
                        key=f"stretegic_agent_plan_{run_id}",
                        value=result,
                        agent_name="StretegicAgent"
                    )

                    safe_snapshot = json.loads(
                        json.dumps(
                            decision_context,
                            default=str
                        )
                    )

                    stretegic_agent_decision = await self.user_intelligence.decision_workflow.create_agent_decision({
                        "user_id":  user_id,
                        "run_id": run_id,
                        "agent_name": "StretegicAgent",
                        "decision_type": result.get("intent", "unknown"),
                        "reason": result.get("reason", "No reason provided"),
                        "input_snapshot": safe_snapshot,
                        "planned_actions": json.dumps(actions, default=str),
                        "trigger_agent": "AutonomyLoop" if actions.get("trigger_workflow") else "",
                        "status": "planned",
                        "confidence": result.get("confidence", 0.0),
                        "result_summary": json.dumps(summary, default=str)
                    })

                    logger.warning(f"Stretegic Agent decision recorded: {stretegic_agent_decision}")


                    llm_span.set_attribute("decision.intent", result.get("intent"))
                    llm_span.set_attribute("decision.confidence", result.get("confidence"))
                    llm_span.set_attribute("decision.observe", json.dumps(result.get("observe", {}), default=str))
                    llm_span.set_attribute("decision.plan", json.dumps(result.get("plan", {}), default=str))
                    llm_span.set_attribute("decision.act", json.dumps(result.get("act", {}), default=str))
                    llm_span.set_attribute("decision.actions", json.dumps(actions, default=str))
                    llm_span.set_attribute("decision.reason", json.dumps(result.get("reason", {}), default=str))
                
                return result
                    

            except Exception as e:
                logger.exception("Stretegic Agent Failed")
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                return {
                    "intent": "no_change",
                    "confidence": 0.0,
                    "reason": "llm failed",
                    "actions": {}
                }
            finally:
                parent_span.set_attribute("llm.latency_seconds", time.time() - start_agent)
    
    def _build_prompt(self, metrics: dict, decision_context: dict) -> str:
        return f"""
    You are a senior autonomous career strategy agent.

    You act like a CEO-level planner for a user's job-search system.

    Your responsibility is to:
    1. Observe the user's current state.
    2. Diagnose what is happening.
    3. Create a strategic plan.
    4. Decide safe actions.
    5. Define what should be observed next.
    6. Record what should be remembered.

    You are NOT a metrics-only rules engine.
    You must reason from the full user intelligence context.

    INPUTS YOU MUST USE:
    - User profile and name
    - Latest resume history
    - Saved/clicked jobs
    - Job report history
    - Email delivery history
    - Previous strategic decisions
    - Outcome metrics

    USER INTELLIGENCE CONTEXT:
    {json.dumps(decision_context, default=str)}

    SECONDRY PERFORMANCE SIGNALS.
    {json.dumps(metrics, default=str)}

    Use them only as performance evidence.
    Do not base the whole strategy on metrics when user intelligence has stronger signals.
    Primary reasoning source is:
    1. latest resume_history
    2. saved/clicked jobs
    3. report_history
    4. user behavior trend
    5. previous decisions
    6. then outcome metrics

    Hard output rules:
    - Every diagnosis must mention at least one concrete job title/company from recent_saved_or_clicked_jobs.
    - Every plan must mention the latest resume direction and whether the clicked jobs align with it.

    Sub-agent routing rules:
    - SourceAgent handles keyword generation, source strategy, and targeting changes.
    - FollowupAgent handles no-response follow-up reminders/emails only.
    - Never assign keyword generation to FollowupAgent.
    - Never assign follow-up emails to SourceAgent.

    DECISION PRINCIPLES:
    - Do not overreact when data is small.
    - Do not repeat the same recent strategy without new evidence.
    - Prefer safe actions first.
    - Never modify past applications.
    - Treat saved/clicked jobs as strong user behavior signals.
    - Treat resume_history as the user's positioning.
    - Treat report_history as market/opportunity signal.
    - Treat email_history as delivery/execution signal.
    - Treat outcome metrics as performance signal.
    - If resume direction and clicked jobs conflict, identify the mismatch.
    - If reports recommend one direction but user clicks another, identify the behavior gap.
    - If email reports are sent but no jobs are clicked, identify engagement problem.
    - If jobs are clicked but no applications/outcomes exist, collect more data before aggressive action.

    AVAILABLE SAFE ACTIONS:
    - update targeting strategy
    - generate better search keywords
    - recommend follow-up timing
    - adjust application volume
    - recommend role-specific resume direction
    - shift or keep job source strategy
    - wait for more outcome data

    OUTPUT JSON ONLY.

    Return exactly this schema:

    {{
    "intent": "strategic_plan|no_change|needs_more_data",
    "confidence": 0.0,

    "observe": {{
        "user": "string",
        "latest_resume_direction": "string",
        "recent_saved_or_clicked_jobs": ["string"],
        "report_history_signal": "string",
        "email_history_signal": "string",
        "outcome_signal": "string"
    }},

    "diagnosis": {{
        "career_direction": "string",
        "current_behavior": "string",
        "alignment": "strong_match|partial_match|mismatch|insufficient_data",
        "main_problem": "string",
        "evidence": ["string"]
    }},

    "plan": {{
        "strategic_goal": "string",
        "next_best_action": "string",
        "why_this_action": "string",
        "expected_impact": "string",
        "risk_if_wrong": "string"
    }},

    "act": {{
        "should_execute": true,
        "execution_level": "observe_only|plan_only|safe_execute",
        "recommended_sub_agents": [
        {{
            "agent": "SourceAgent|FollowupAgent|None",
            "task": "string",
            "priority": "low|medium|high",
            "input": {{}}
        }}
        ]
    }},

    "verify": {{
        "signals_to_watch_next": ["string"],
        "success_criteria": ["string"],
        "when_to_review_again": "string"
    }},

    "memory_update": {{
        "decision_summary": "string",
        "what_changed": "string",
        "what_to_avoid_repeating": "string"
    }},

    "actions": {{
        "apply_volume": "low|normal|high",
        "follow_up_strategy": "none|reminder",
        "targeting_adjustment": "broad|narrow|refine",
        "source_strategy": "same|shift",
        "application_timing": "anytime|early_only",
        "resume_strategy": "keep|improve|role_specific",
        "trigger_workflow": true
    }},

    "reason": "short final reason"
    }}
    """