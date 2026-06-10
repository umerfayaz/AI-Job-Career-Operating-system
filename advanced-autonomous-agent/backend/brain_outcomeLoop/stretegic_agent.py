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
    def __init__(self, shared_context):
        self.settings = Settings()

        self.shared_context = shared_context
        self.client = AsyncGroq(api_key=self.settings.GROQ_API_KEY)

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

            prompt = self._build_prompt(metrics)
            try:
                with tracer.start_as_current_span("LLM.call") as llm_span:
                    start_llm = time.time()
                    MODEL_NAME = "openai/gpt-oss-120b"
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
                            "openai/gpt-oss-120b": 0.0001
                        }
                        cost = (total_tokens / 1000) * MODEL_COSTS.get(MODEL_NAME, 0)

                        llm_span.set_attribute("llm.estimated_cost_usd", cost)
                    
                    content =  response.choices[0].message.content
                    result=json.loads(content)
                    actions = result.get("actions", {})

                    llm_span.set_attribute("decision.intent", result.get("intent"))
                    llm_span.set_attribute("decision.confidence", result.get("confidence"))
                    llm_span.set_attribute("decision.apply_volume", actions.get("apply_volume"))
                    llm_span.set_attribute("decision.follow_up_stretegy", actions.get("follow_up_stretegy"))
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
    
    def _build_prompt(self, metrics: dict) -> str:
            return f"""
        You are an autonomous career optimization stretegic agent.

        Observed outcome metrics (0.0–1.0):
        - Reply rate: {metrics['reply_rate']}
        - Rejection rate: {metrics['rejection_rate']}
        - No response rate: {metrics['no_response_rate']}
        - Dead application rate: {metrics['dead_application_rate']}
        - Total applications evaluated: {metrics['total']}

        Task:
        1. Optimize FUTURE job application stretegy.
        2. Adjust targeting, sources, timing, and positioning.
        3. Suggest follow-up behavior for no_response jobs.
        4. Trigger workflow ONLY when necessary.

        Key Principles:
        - DO NOT modify past applications.
        - Focus on improving future pipeline performance.
        - Treat no_response as a targeting/positioning problem.
        - Treat rejection as a resume/fit problem.
        - Treat dead_application as pipeline volume problem.

        Guidelines:
        - Sample size < 2 → low confidence

        - reply_rate ≥ 0.25:
            → stretegy working
            → apply_volume = high

        - rejection_rate ≥ 0.5:
            → resume mismatch
            → resume_stretegy = improve
        
        - no_response_rate ≥ 0.2:
            → follow_up_stretegy = reminder
           
        - no_response_rate ≥ 0.5:
            → weak targeting or visibility
            → targeting_adjustment = narrow
            → source_stretegy = shift
            → application_timing = early_only
            → trigger_workflow = true

        - dead_application_rate ≥ 0.5 AND total ≥ 2:
            → pipeline too small
            → apply_volume = high
            → trigger_workflow = true

        Confidence Rules:
        - total <2 -> confidence = 0.1-0.3
        - weak signal -> confidence = 0.3-0.5
        - moderate signal -> confidence = 0.5-0.7
        - strong signal -> confidence: = 0.7-1.0

        Return JSON ONLY:
        {{
        "intent": "optimize_stretegy",
        "confidence": 0.0 to 1.0,
        "reason": "string",
        "actions": {{
            "apply_volume": "low" | "normal" | "high",
            "follow_up_stretegy": "reminder",

            "targeting_adjustment": "broad" | "narrow" | "refine",
            "source_stretegy": "same" | "shift",
            "application_timing": "anytime" | "early_only",

            "resume_stretegy": "keep" | "improve" | "role_specific",

            "trigger_workflow": true | false
        }}
        }}
        """