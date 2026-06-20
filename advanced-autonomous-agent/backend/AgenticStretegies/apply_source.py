import os
import json
import time
from datetime import datetime
from groq import AsyncGroq
from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
from backend.LLMGateway.fallbackmodels import Models
from opentelemetry.trace import Status, StatusCode
from backend.core.skills_extractor import SkillsExtractor
import structlog
from dotenv import load_dotenv


load_dotenv()
logger = structlog.get_logger()

class SourceAgent:
    def __init__(self, shared_context):
        self.shared_context = shared_context
        self.skills_extractor = SkillsExtractor()
        self.llm_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.models = Models(self.llm_client)

    async def run(self, user_id, run_id):

        try:
            logger.info(f"Starting Source Agent for {user_id}")

            # Tracing Obervability

            with tracer.start_as_current_span("SourceAgent.run") as parent_span:
                agent_start = time.time()
                parent_span.set_attribute("agent", "source")
                parent_span.set_attribute("user_id", user_id)

                plan = await self.shared_context.read(f"stretegic_agent_plan_{run_id}")
                if not plan:
                    logger.warning(f"No stretegic agent plan found for source agent:{run_id}")
                    return
                
                logger.warning(f"Stretegic Plan that Source agent recieved:{plan}")
                
                tasks = plan.get("act", {}).get("recommended_sub_agents", [])
                source_tasks = [t for t in tasks if t.get("agent") == "SourceAgent"]

                if not source_tasks:
                    logger.warning(f"No Source task Assigned to Source agent: {run_id}")
                    return


                from backend.brain_outcomeLoop.profile_resolver import (
                    get_active_search_profile,
                )

                profile_data = await get_active_search_profile(
                    self.shared_context, user_id, run_id
                )

                if not profile_data:
                    logger.warning(
                        f"No profile data found for run_id={run_id} user_id={user_id}"
                    )
                    return

                initial_state = profile_data.get("initial_state", {})
                if not initial_state:
                    logger.warning(f"No Initial state found in source agent {user_id}")
                    return
                

                base_roles = initial_state.get("job_keywords", [])
                if not base_roles:
                    logger.info(f"No base roles found in Source agent generating from Skill extractor {user_id}")

                    resume_text = initial_state.get("resume_text") or profile_data.get("resume_text") or ""
                    skills = initial_state.get("skills") or profile_data.get("skills") or []

                    base_roles = await self.skills_extractor.generate_base_roles_llm(resume_text, skills)
                    initial_state["job_keywords"] = base_roles

                base_locations = initial_state.get("job_location", "remote")
                initial_state["job_location"] = base_locations

            
                with tracer.start_as_current_span("GenerateKeywords") as keyword_span:
                    keyword_start = time.time()
                    new_keywords = await self.generate_keywords_with_llm(
                        base_roles,
                        base_locations,
                        source_tasks,
                        stretegic_plan=plan
                    )

                    logger.warning(f"New keywords Generated in Source Agent", keywords=new_keywords)

                    if not new_keywords:
                        new_keywords = base_roles
                        logger.warning("No new Keywords using the existing initial state keywords")
                    
                    keyword_span.set_attribute("keywords.count", len(new_keywords))
                    keyword_span.set_attribute("keyword.latency_seconds", time.time() - keyword_start)

                    config = {
                        "run_id": run_id,
                        "keywords": new_keywords,
                        "location": base_locations,
                        "fresh_only": True,
                        "source": "agent",
                        "preferred_source": "Remotive",
                        "mode": "autonomous",
                        "created_at": datetime.now().isoformat()
                    }

                    await self.shared_context.write(
                        f"job_source_config_{run_id}",
                        config,
                        "SourceAgent"
                    )
                    await self.shared_context.write(
                        f"current_run_id_{user_id}",
                        run_id,
                        "SourceAgent",
                    )

                    logger.error(f"""
                    SOURCE AGENT WRITING CONFIG
                    RUN_ID: {run_id}
                    KEY: job_source_config_{run_id}
                    CONFIG: {config}
                    """)

                    logger.info(f"SourceAgent Updated config for",
                    user_id=user_id,
                    keywords_count= len(new_keywords),
                    )
                
            
        except Exception as e:
            if "parent_span" in locals():
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                logger.error(f"Error in Source Agent {e}")
        finally:
            parent_span.set_attribute("llm.latency_seconds", time.time() - agent_start)
            

   
    async def generate_keywords_with_llm(self, roles, location, source_tasks, stretegic_plan):
            with tracer.start_as_current_span("LLM.keywords_generation") as gen_span:
                agent_start = time.time()

                prompt = f"""
                You are SourceAgent, a specialized job sourcing execution agent.

                Identity:
                - You do NOT decide the user's career strategy.
                - The StrategicAgent has already made the strategic decision.
                - Your job is to convert the StrategicAgent plan into high-quality job search keywords.
                - You optimize sourcing, targeting, and search coverage.
                - You must preserve the user's strongest positioning while improving job-market alignment.

                StrategicAgent assigned task:
                {json.dumps(source_tasks, default=str)}

                Strategic diagnosis:
                {json.dumps(stretegic_plan.get("diagnosis", {}), default=str)}

                Strategic plan:
                {json.dumps(stretegic_plan.get("plan", {}), default=str)}

                Strategic action policy:
                {json.dumps(stretegic_plan.get("actions", {}), default=str)}

                User/context signals:
                {json.dumps(stretegic_plan.get("observe", {}), default=str)}

                Current base roles/keywords:
                {json.dumps(roles, default=str)}

                Preferred location:
                {location}

                Your reasoning task:
                1. Understand the StrategicAgent's goal.
                2. Identify the user's actual direction from resume + clicked jobs.
                3. Preserve strong skills such as Agentic AI, LangGraph, RAG, LLM, Python, FastAPI.
                4. Generate keywords that improve targeting.
                5. Avoid generic or low-value keywords.
                6. Avoid frontend-only, web-only, or unrelated roles unless the StrategicAgent explicitly asks.
                7. Prefer hybrid keywords that combine AI + backend + Python infrastructure.

                Return JSON ONLY.

                Schema:
                {{
                "source_reasoning": "short explanation of how you interpreted the StrategicAgent plan",
                "target_direction": "string",
                "keywords": [
                    "keyword 1",
                    "keyword 2",
                    "keyword 3"
                ],
                "avoid_keywords": [
                    "keyword/category to avoid"
                ],
                "confidence": 0.0
                }}

                Rules:
                - No markdown.
                - No explanations outside JSON.
                - No duplicate keywords.
                - Keywords must be job-search friendly.
                - Keywords should be specific enough for job boards.
                - Keep 8 to 15 keywords
                """
                try:
                    with tracer.start_as_current_span("LLM.call") as llm_span:
                        start_llm = time.time()
                        MODEL_NAME =  "openai/gpt-oss-120b"
                        llm_span.set_attribute("llm.model", MODEL_NAME)

                        response = await self.models.json_completion(
                            task_type="cheap_json",
                            messages=[
                                {"role": "system", "content": "You are SourceAgent. Output valid JSON object only"},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.3
                        )

                        llm_span.set_attribute("llm.latency_seconds", time.time() - start_llm)

                        usage = getattr(response, "usage", None)

                        if usage:
                            llm_span.set_attribute("llm.prompt", prompt[:500])
                            llm_span.set_attribute("llm.prompt_tokens", getattr(usage, "prompt_tokens", 0))
                            llm_span.set_attribute("llm.completion_tokens", getattr(usage, "completion_tokens", 0))
                            llm_span.set_attribute("llm.total_tokens", getattr(usage, "total_tokens", 0))

                            total_tokens = getattr(usage, "total_tokens", 0)
                            MODELS_COST =  {
                                "llama-3.3-70b-versatile": 0.0001
                            }
                            cost = (total_tokens / 1000) * MODELS_COST.get( MODEL_NAME, 0)

                            llm_span.set_attribute("llm.estimated_cost_usd", cost)
                        

                    content = response.choices[0].message.content.strip()

                
                    parsed = json.loads(content)

                    if isinstance(parsed, dict):
                        keywords = parsed.get("keywords", [])
                        if isinstance(keywords, list) and keywords:
                            logger.warning(
                                "SourceAgent reasoning completed",
                                reasoning=parsed.get("source_reasoning"),
                                target_direction=parsed.get("target_direction"),
                                confidence=parsed.get("confidence"),
                                keywords=keywords,
                            )
                            return keywords
                
                except Exception as e:
                    if "llm_span" in locals():
                        logger.warning("LLM Keywords Generation error", error=str(e))
                        llm_span.record_exception(e)
                        llm_span.set_status(Status(StatusCode.ERROR, str(e)))
                finally:
                    gen_span.set_attribute("agent.latency_seconds", time.time() - agent_start )

       
    
