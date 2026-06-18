import json
import time
from groq import AsyncGroq
from datetime import datetime
import structlog
from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
from backend.config.settings import Settings



logger = structlog.get_logger()

class stretegic_agent:
    def __init__(self, shared_context, user_intelligence):
        self.settings = Settings()
        self.user_intelligence = user_intelligence
        self.shared_context = shared_context
        self.client = AsyncGroq(api_key=self.settings.GROQ_API_KEY)


    async def decision_context(self, user_id: str):
        user_snapshot = await self.user_intelligence.get_user_intelligence(user_id)

        return {
            "user_snapshot": user_snapshot
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
            decision_context = await self.decision_context(user_id)
            prompt = self._build_prompt(metrics, decision_context)

            logger.warning(f"Stretegic agent received decision contex", user_id=user_id, decision_context=decision_context)
            logger.warning("Stretegic Prompt size recieved", characters=len(prompt))

            try:
                with tracer.start_as_current_span("LLM.call") as llm_span:
                    start_llm = time.time()
                    MODEL_NAME = "llama-3.3-70b-versatile"
                    llm_span.set_attribute("llm.model", MODEL_NAME)

                    response =  await self.client.chat.completions.create(
                        model = "llama-3.3-70b-versatile",
                        temperature = 0.2,
                        response_format = {"type": "json_object"},
                        messages = [
                            {
                                "role": "system",
                                "content": "You are a careful stretegic agent. Output json only"
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    )

                    llm_span.set_attribute("llm.latency_seconds", time.time() - start_llm)
                    
                    # LLM Token & Cost Tracking
                    usage = getattr(response, "usage", None)

                    if usage:
                        llm_span.set_attribute("llm.prompt", prompt[:500])
                        llm_span.set_attribute("llm.prompt_tokens", getattr(usage, "prompt_tokens", 0))
                        llm_span.set_attribute("llm.completion_tokens", getattr(usage ,"completion_tokens", 0))
                        llm_span.set_attribute("llm.total_tokens", getattr(usage, "total_tokens", 0))

                        # Calculating cost per Token LLM
                        total_tokens = getattr(usage, "total_tokens", 0)
                        MODEL_COSTS = {
                            "llama-3.3-70b-versatile": 0.0001
                        }
                        cost = (total_tokens / 1000) * MODEL_COSTS.get(MODEL_NAME, 0)

                        llm_span.set_attribute("llm.estimated_cost_usd", cost)
                    
                    content =  response.choices[0].message.content
                    result=json.loads(content)
                    actions = result.get("actions", {})

                    logger.warning("Stretegic Agent Decision", result=result)

                    safe_snapshot = json.loads(
                        json.dumps(
                            decision_context,
                            default=str
                        )
                    )

                    await self.user_intelligence.decision_workflow.create_agent_decision({
                        "user_id":  user_id,
                        "run_id": metrics.get("run_id"),
                        "agent_name": "StretegicAgent",
                        "decision_type": result.get("intent", "unknown"),
                        "reason": result.get("reason", "No reason provided"),
                        "input_snapshot": safe_snapshot,
                        "planned_actions": json.dumps(actions, default=str),
                        "trigger_agent": "AutonomyLoop" if actions.get("trigger_workflow") else "",
                        "status": "planned",
                        "confidence": result.get("confidence", 0.0),
                        "result_summary": result.get("result_summary")
                    })


                    llm_span.set_attribute("decision.intent", result.get("intent"))
                    llm_span.set_attribute("decision.confidence", result.get("confidence"))
                    llm_span.set_attribute("decision.apply_volume", actions.get("apply_volume"))
                    llm_span.set_attribute("decision.follow_up_stretegy", actions.get("follow_up_stretegy", ""))
                    llm_span.set_attribute("decision.trigger_workflow", actions.get("trigger_workflow"))
                
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
    You are an autonomous career optimization strategic agent.

    Use BOTH:
    1. Outcome metrics
    2. Full user intelligence context

    User Intelligence Context:
    {json.dumps(decision_context, default=str)}

    Observed outcome metrics:
    - Reply rate: {metrics.get('reply_rate', 0)}
    - Rejection rate: {metrics.get('rejection_rate', 0)}
    - No response rate: {metrics.get('no_response_rate', 0)}
    - Dead application rate: {metrics.get('dead_application_rate', 0)}
    - Total applications evaluated: {metrics.get('total', 0)}

    Task:
    Optimize FUTURE job application strategy.

    Rules:
    - Do not modify past applications.
    - Do not repeat recent failed decisions.
    - Use recent_agent_decisions to avoid duplicate actions.
    - Treat rejection as resume/fit problem.
    - Treat no_response as targeting/visibility problem.
    - Trigger workflow only when necessary.

    Return JSON ONLY:
    {{
    "intent": "optimize_strategy",
    "confidence": 0.0,
    "reason": "string",
    "actions": {{
        "apply_volume": "low|normal|high",
        "follow_up_strategy": "none|reminder",
        "targeting_adjustment": "broad|narrow|refine",
        "source_strategy": "same|shift",
        "application_timing": "anytime|early_only",
        "resume_strategy": "keep|improve|role_specific",
        "trigger_workflow": true
    }}
    }}
    """