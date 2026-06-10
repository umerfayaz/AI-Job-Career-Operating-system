import os
import json
import re
import time
from datetime import datetime
from groq import AsyncGroq
from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
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
        self.model = "openai/gpt-oss-120b"

    async def run(self, user_id, run_id):

        try:
            logger.info(f"Starting Source Agent for {user_id}")

            # Tracing Obervability

            with tracer.start_as_current_span("SourceAgent.run") as parent_span:
                agent_start = time.time()
                parent_span.set_attribute("agent", "source")
                parent_span.set_attribute("user_id", user_id)


                stretegy = await self.shared_context.read(f"apply_source_stretegy_{run_id}")
                logger.warning(f"Recieved stretegy in Source agent : {stretegy}")

                if not stretegy:
                    logger.warning(f"No Stretegy found in source agent {run_id}")
                    return

                mode = stretegy.get("mode")

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

                if mode == "same":
                    return 
                
                # Shift From stretegic Agent to generate Keywords
                elif mode == "shift":
                    with tracer.start_as_current_span("GenerateKeywords") as keyword_span:
                        keyword_start = time.time()
                        new_keywords = await self.generate_keywords_with_llm(
                            base_roles,
                            base_locations
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
                        mode=mode
                        )
                
            
        except Exception as e:
            if "parent_span" in locals():
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                logger.error(f"Error in Source Agent {e}")
        finally:
            parent_span.set_attribute("llm.latency_seconds", time.time() - agent_start)
            

   
    async def generate_keywords_with_llm(self, roles, location):
            with tracer.start_as_current_span("LLM.keywords_generation") as gen_span:
                agent_start = time.time()
                    
                prompt = f"""
            You are a job search optimization AI.

            User target roles: {roles}
            Preferred location: {location}

            STRICT RULES:
            - Output ONLY valid JSON
            - No explanations
            - No text before or after
            - No markdown
            - No numbering
            - No duplicates

            OUTPUT FORMAT:
            [
                "keyword 1",
                "keyword 2",
                "keyword 3"
            ]
            """
                try:
                    with tracer.start_as_current_span("LLM.call") as llm_span:
                        start_llm = time.time()
                        MODEL_NAME =  "openai/gpt-oss-120b"
                        llm_span.set_attribute("llm.model", MODEL_NAME)

                        response = await self.llm_client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": "You ONLY output valid JSON arrays."},
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

                
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, list):
                            return parsed
                    except:
                        pass

                    # Fallback: extract JSON array
                    match = re.search(r"\[.*?\]", content, re.DOTALL)
                    if match:
                        try:
                            parsed = json.loads(match.group())
                            if isinstance(parsed, list):
                                return parsed
                        except Exception as e:
                            logger.warning("JSON parsing failed", error=str(e))

                    logger.warning("No valid JSON found in LLM response", content=content)
                    return roles
                
                except Exception as e:
                    if "llm_span" in locals():
                        logger.warning("LLM Keywords Generation error", error=str(e))
                        llm_span.record_exception(e)
                        llm_span.set_status(Status(StatusCode.ERROR, str(e)))
                finally:
                    gen_span.set_attribute("agent.latency_seconds", time.time() - agent_start )

       
    
