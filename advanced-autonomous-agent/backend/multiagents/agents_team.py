### Multi Agents With Episodic Memory
import os
import json
import time
import aiohttp
import asyncio
import structlog
import numpy as np 
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dateutil import parser
from backend.core.event_bus import get_event_bus
from backend.LLMClient.lmc_client import LMCClient
from backend.tools.pdf_generator import PDFGenerator
from .event_monitor import EventMonitor
from backend.multiagents.guardrails import JobReportGuardrails
from sentence_transformers import SentenceTransformer
from ..core.memory_system import MemoryRAGSystem
from ..core.email_sender import EmailSender
from backend.narration.emitter import AgentEmitter

def get_agent_app():
    from backend.application import AgentApplication
    return AgentApplication()

def multi_agent():
    from .agents_orchestrator import AutonomousOrchestrator
    multi_agents_orchestrator  = AutonomousOrchestrator()
    return multi_agents_orchestrator


logger = structlog.get_logger()
event_bus = get_event_bus()

class EpisodicMemory:
    def __init__(self, memory_system: MemoryRAGSystem):
        self.memory=memory_system
        self.experiences = []
        self.max_experiences =  1000


    def record_experiences(self, agent_name:str, action:str, result: Dict, context:Dict):
        """Record Agent Experience"""

        experience = {
            "agent": agent_name,
            "action": action,
            "result": result,
            "context": context,
            "timestamp": datetime.now().isoformat(),
            "success": result.get("status") == "success" if result else None
        }

        self.experiences.append(experience)
    

        if len(self.experiences) > self.max_experiences:
            self.experiences = self.experiences[-self.max_experiences:]
        
        logger.info(f"{agent_name} recorded experiences:{action}")
    

    def get_recent_summary(self, limit: int = 50) -> List[Dict]:
        """
        Return the most recent N experiences (for system-level reflection).
        Used by CognitiveOrchestrator.system_reflection_loop().
        """
        return self.experiences[-limit:]


    def get_similar_experiences(self, agent_name:str, action:str, limit: int =5) ->List[Dict]:
        """Retrieve similar Past Experiences"""
        relevant =[
            exp for exp in self.experiences
            if exp["agent"] == agent_name and exp["action"] == action
        ]
        return relevant[-limit:]

    def get_success_rate(self, agent_name:str, action:str) ->float:
        """Calculate Success rate for an agent's action"""
        relevant = self.get_similar_experiences(agent_name, action, limit=20)
        if not relevant:
            return 0.5
        
        success = sum(1 for exp in relevant if exp["success"])
        return success / len(relevant)

    def learn_from_failures(self, agent_name:str) ->Dict:
        """Analyze failures and extract learnings"""
        failures =[
            exp for exp in self.experiences
            if exp["agent"] == agent_name and not exp["success"]
        ]

        if not failures:
            return {"learning": "No failures recorded"}
    
        
        common_errors = {}

        for failure in failures[-10:]:
            error = failure["result"].get("error", "unknown")
            common_errors[error] = common_errors.get(error, 0) + 1

        return {
            "total_failures": len(failures),
            "recent_failures": len(failures[-10:]),
            "common_errors": common_errors,
            "recommendations": self._generate_recommendations(common_errors)
        } 


    def _generate_recommendations(self, errors: Dict, ) ->List[str]:
        """Generate Reccomendations Based ont error Patterns"""

        recommendations = []

        for error, count in errors.items():
            if "timeout" in error.lower():
                recommendations.append("Consider increasing error limits")
            
            elif "not found" in error.lower():
                recommendations.append("Vlidate data experiences before processing")
            
            elif "empty" in error.lower():
                recommendations.append("Add data validation checks")
        
        return recommendations
    
class SharedContext:
    """Shared memory space for inter-agent Communications - Redis backed"""

    def __init__(self, memory_system: Optional[MemoryRAGSystem] = None, redis_client=None):
        self.redis = redis_client
        self.prefix = "shared_context:"
        self.lock = asyncio.Lock()
        self.memory_system = memory_system
        
        # Keep only non-serializable / frequently-mutated local state
        self._local = {
            "global_metrics": {
                "jobs_scraped_today": 0,
                "matches_created_today": 0,
                "reports_generated_today": 0
            },
            "last_reset": datetime.now()
        }

    def _k(self, key: str) -> str:
        return f"{self.prefix}{key}"

    async def write(self, key: str, value: Any, agent_name: str = "", TTL = None):
        if self.redis:
            if value is None:
                await self.redis.delete(self._k(key))
            else:
                if TTL:
                    await self.redis.set(self._k(key), json.dumps(value, default=str), ex=TTL)
                else:
                    await self.redis.set(self._k(key), json.dumps(value, default=str))
        logger.info(f"{agent_name} wrote {key}")
    

    def user_keys(self, user_id:str, keys:str):
        return f"user:{user_id}:{keys}"

    async def read(self, key: str) -> Any:
        if self.redis:
            val = await self.redis.get(self._k(key))
            return json.loads(val) if val else None
        return None

    async def pop(self, key: str, default=None):
        async with self.lock:
            if self.redis:
                val = await self.redis.getdel(self._k(key))
                return json.loads(val) if val else default
            return default

    async def delete(self, key: str):
        async with self.lock:
            if self.redis:
                await self.redis.delete(self._k(key))

    async def update_metrics(self, metric: str, increment: int = 1):
        async with self.lock:
            if metric in self._local["global_metrics"]:
                self._local["global_metrics"][metric] += increment

    async def get_all_metrics(self) -> Dict:
        async with self.lock:
            return self._local["global_metrics"].copy()

    async def set_agent_state(self, agent_name: str, state_dict: Dict) -> Dict:
        await self.write(f"agent_state_{agent_name}", state_dict, agent_name)
        return state_dict

    async def add_task(self, task_id: str, task: Dict, agent_name: str):
        task_data = {
            **task,
            "created_by": agent_name,
            "created_at": datetime.now().isoformat(),
            "status": "pending"
        }
        await self.write(f"task_{task_id}", task_data, agent_name)

    async def complete_task(self, task_id: str):
        task = await self.read(f"task_{task_id}")
        if task:
            task["completed_at"] = datetime.now().isoformat()
            task["status"] = "completed"
            await self.write(f"completed_task_{task_id}", task, "system")
            await self.delete(f"task_{task_id}")

    async def get_active_users(self) -> set:
        if not self.redis:
            return set()
        
        user_ids = set()
        prefixes = [
            "active_search_profile_", "policy_proposal_", "outcome_metrics_",
            "new_resume_upload_", "last_fingerprint_policy_",
            "last_outcome_metrics_", "policy_approved_"
        ]
        
        keys = await self.redis.keys(f"{self.prefix}*")
        for key in keys:
            key_str = key.decode() if isinstance(key, bytes) else key
            stripped = key_str.replace(self.prefix, "")
            for p in prefixes:
                if stripped.startswith(p):
                    user_ids.add(stripped[len(p):])
                    break
        
        logger.info(f"Active users {user_ids}")
        return user_ids

    async def reset(self):
        now = datetime.now()
        last_reset = self._local["last_reset"]
        if isinstance(last_reset, str):
            last_reset = parser.parse(last_reset)
        
        if now.date() > last_reset.date():
            self._local["global_metrics"] = {
                "jobs_scraped_today": 0,
                "matches_created_today": 0,
                "reports_generated_today": 0
            }
            self._local["last_reset"] = now
            logger.info("Daily metrics reset")
    

class BaseAutonomousAgent:
    """Enhanced base class with episodic memory and shared context"""

    def __init__(self, name: str, agent_app, memory: MemoryRAGSystem, 
                 episodic_memory: EpisodicMemory, shared_context: SharedContext, guardrails: JobReportGuardrails):
        self.name = name
        self.agent_app = agent_app
        self.memory = memory
        self.guardrails = guardrails
        self.episodic_memory = episodic_memory
        self.shared_context = shared_context
        self.is_active = True
        self.current_task = None

        self.metrics = {
            "task_completed": 0,
            "task_failed": 0,
            "last_run": None,
        }

    async def perceive(self) -> Optional[Dict]:

        task=self.current_task or {}
        task_desc = task.get("task_desc", "").lower()

        keywords = getattr(self, "accepted_keywords", [])
        if not keywords:
            return {"has_work": False}

        if not any(k in task_desc for k in keywords):
            return {"has_work": False}
        
        return {"has_work": True}


    async def decide(self, perception: Dict) -> Dict:
        raise NotImplementedError

    async def act(self, decision: Dict) -> Dict:
        raise NotImplementedError

    async def learn(self, result: Dict):
        """Learn from results using episodic memory"""
        
        similar_exp = self.episodic_memory.get_similar_experiences(
            self.name, 
            result.get("action", "unknown"),
            limit=5
        )
        

        if similar_exp:
            avg_past_success = sum(1 for e in similar_exp if e["success"]) / len(similar_exp)
            current_success = result.get("status") == "success"
            
            if current_success and avg_past_success < 0.5:
                logger.info(f"🎓 {self.name} is improving! Success rate increasing.")
            elif not current_success and avg_past_success > 0.8:
                logger.warning(f" {self.name} performance degrading. Analyzing...")
                learnings = self.episodic_memory.learn_from_failures(self.name)
                logger.info(f" Learnings: {learnings.get('recommendations', [])}")

    async def run_cycle(self, payload=None):
        """Complete perception → decision → action → learning"""

        self.current_task = payload

        try:
            logger.info(f"{self.name}: Starting cycle")
            
        
            await self.shared_context.set_agent_state(self.name, {
                "status": "running",
                "phase": "perceive"
            })

            # 1. PERCEIVE (with context)
            perception = await self.perceive()

            if self.shared_context:
                command = await self.shared_context.read("maintenance_command")
                if command and command.get("run") is True:
                    perception = {"has_work": True, "reason": "brain2_command"}    

            if not perception or not perception.get("has_work"):

                logger.info(f"{self.name}: No work detected")
                await self.shared_context.set_agent_state(self.name, {
                    "status": "idle"
                })
                return {"status": "idle"}

            await self.shared_context.set_agent_state(self.name, {
                "status": "running",
                "phase": "decide"
            })
            decision = await self.decide(perception)
            
            if decision.get("action") == "skip":
                logger.info(f"{self.name} decided to skip")
                return {"status": "skipped"}

        
            await self.shared_context.set_agent_state(self.name, {
                "status": "running",
                "phase": "act"
            })
            result = await self.act(decision)

            if result is None:
                result = {
                    "status": "error",
                    "message": "Action returned none",
                    "action": decision.get("action", "unknown")
                }
            
            self.episodic_memory.record_experiences(
                agent_name=self.name,
                action=decision.get("action", "unknown"),
                result=result,
                context=perception
            )

            await self.learn(result)

            self.metrics["task_completed"] += 1
            self.metrics["last_run"] = datetime.now().isoformat()
            
            await self.shared_context.set_agent_state(self.name, {
                "status": "completed",
                "last_result": result
            })

            logger.info(f"{self.name}: Task completed successfully")
            return result

        except Exception as e:
            logger.error(f"{self.name}: Cycle failed — {e}", exc_info=True)
            self.metrics["task_failed"] += 1
            
            
            self.episodic_memory.record_experiences(
                agent_name=self.name,
                action="unknown",
                result={"status": "error", "error": str(e)},
                context={}
            )
            
            return {"status": "skipped", "payload": payload}
    
    async def sub_tasks(self, task_type: str, context: Dict):
        """Agents can create new tasks"""
        subtask ={
            "type": task_type,
            "created_by": self.name,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }

        await self.shared_context.add_task(
            f"_subtask{datetime.now().isoformat()}",
            subtask,
            self.name
        )
        logger.info(f" {self.name} created subtask: {task_type}")

class ResumeMatcherAgent(BaseAutonomousAgent):
    """Matches incoming jobs with stored resumes - ENHANCED"""
    accepted_keywords = ["resume", "match"]

    def __init__(self, agent_app, memory, episodic_memory, shared_context, guardrails, multi_agents_orchestrator=None):
        super().__init__("ResumeMatcherAgent", agent_app, memory, episodic_memory, shared_context, guardrails)
        self.match_threshold = 0.48
        self.memory = agent_app.memory
        self.multi_agents_orchestrator = multi_agents_orchestrator
        self.model = SentenceTransformer("BAAI/bge-large-en-v1.5")
        self.emitter = AgentEmitter("ResumeMatcherAgent", event_bus)

    async def perceive(self):
        try:
            target_resume_id = await self.shared_context.read(f"{self.name}_target_resume")
            
            # no target set at all - nothing to do
            if not target_resume_id:
                logger.info(f"{self.name} No target resume provided: Skipping")
                return {"has_work": False}

            logger.info(f"{self.name}: Targeting resume {target_resume_id}")

            resume_result = self.memory.resume_collection.get()
            
            if not resume_result or not resume_result.get("ids"):
                await self.shared_context.write(f"{self.name}_target_resume", None, self.name)
                return {"has_work": False}

            resume_ids = resume_result["ids"]
            
            if target_resume_id not in resume_ids:
                # ← autonomous path: resume not stored (no resume_text), but matches may exist
                logger.warning(f"Target resume {target_resume_id} not in collection - checking autonomous path")
                
                run_id = await self.shared_context.read(f"current_run_id_{target_resume_id}")
                if run_id:
                    try:
                        existing = self.memory.match_collection.get(
                            where={"run_id": run_id},
                            limit=1
                        )
                        if existing and existing.get("ids"):
                            logger.info(f"Found existing matches for autonomous run {run_id}")
                            return {
                                "has_work": True,
                                "resumes": None,
                                "jobs": None,
                                "resume_count": 0,
                                "job_count": 0,
                                "target_user_id": target_resume_id,
                                "existing_matches_only": True,
                                "run_id": run_id,
                            }

                    except Exception as e:
                        logger.error(f"Failed to check existing matches: {e}")
                
                await self.shared_context.write(f"{self.name}_target_resume", None, self.name)
                return {"has_work": False}

            # ← frontend path: resume exists in collection, proceed normally
            idx = resume_ids.index(target_resume_id)
            resume_result = {
                "ids": [resume_result["ids"][idx]],
                "documents": [resume_result["documents"][idx]] if resume_result.get("documents") else [],
                "metadatas": [resume_result["metadatas"][idx]] if resume_result.get("metadatas") else []
            }
            logger.info(f"Filtered to single resume: {target_resume_id}")

            job_result = self.memory.job_collection.get()
            if not job_result or not job_result.get("ids"):
                await self.shared_context.write(f"{self.name}_target_resume", None, self.name)
                return {"has_work": False}

            return {
                "has_work": True,
                "resumes": resume_result,
                "jobs": job_result,
                "resume_count": len(resume_result["ids"]),
                "job_count": len(job_result["ids"]),
                "target_user_id": target_resume_id
            }

        except Exception as e:
            logger.error(f"Perception error: {e}", exc_info=True)
            return {"has_work": False}
         

    async def decide(self, perception):
        if perception.get("existing_matches_only"):
            return {
                "action": "signal_existing",
                "target_user_id": perception.get("target_user_id"),
                "run_id": perception.get("run_id"),
            }

        job_count = perception.get("job_count", 0)
        resume_count = perception.get("resume_count", 0)

        if job_count == 0 or resume_count == 0:
            return {
                "action": "skip", 
                "reason": "missing jobs or resume", 
                "job_count": job_count, 
                "resume_count": resume_count
            }

        success_rate = self.episodic_memory.get_success_rate(self.name, "match")        

        adjusted_threshold = self.match_threshold
        if success_rate > 0.8:
            adjusted_threshold = min(0.5, self.match_threshold + 0.05)  
        elif success_rate < 0.3:
            adjusted_threshold = max(0.15, self.match_threshold - 0.05)
        
        return {
            "action": "match",
            "job_count": job_count,
            "resume_count": resume_count,
            "threshold": adjusted_threshold,
            "jobs": perception.get("jobs"),
            "resumes": perception.get("resumes"),
            "target_user_id": perception.get("target_user_id")
        }

    async def act(self, decision):
        """Fixed version - ONLY uses fresh jobs from current run"""

        try:
            if decision.get("action") == "signal_existing":
                target_resume_id = decision.get("target_user_id")
                run_id = decision.get("run_id")

                existing = self.memory.match_collection.get(
                    where={"run_id": run_id,
                    }
                )

                existing_count = len(existing.get("ids", [])) if existing else 0

                await self.shared_context.write("ResumeMatcherAgent_target_resume", None, self.name)
                await self.shared_context.write(
                    "new_matches_available",            
                {
                    "count": existing_count,
                    "timestamp": datetime.now().isoformat(),
                    "target_user_id": target_resume_id,
                    "run_id": run_id,
                    "is_fetch": True
                }, self.name)

                logger.info(f"Autonomous gate signlaed {existing_count}, existing matches for {target_resume_id}")
                return {"status": "success", "matches_created": existing_count, "action": "signal_existing"}

            target_resume_id = decision.get("target_user_id")


            resumes = decision.get("resumes")
            if not resumes or not resumes.get("ids"):
                logger.warning(f"No resumes in decision")
                return {"status": "error", "reason": "no resume", "action": "match"}

            
            run_id = await self.shared_context.read(f"current_run_id_{target_resume_id}")
            if not run_id:
                run_id = await self.shared_context.read(f"current_run_id")

            await self.emitter.start(
                run_id,
                "Matching resume with relevant job openings"
            )

            await asyncio.sleep(3.0)

            logger.info(f"Querying FRESH jobs with run_id: {run_id}")
            
            try:
                jobs = self.memory.job_collection.get(
                    where={
                        "$and": [
                            {"run_id": run_id},
                            {"is_fresh": True}
                        ]
                    },
                    limit=100,
                    include=["metadatas", "documents"]
                )
                job_ids = jobs["ids"]
                
                if not jobs or not jobs.get("ids") or len(jobs["ids"]) == 0:
                    self.multi_agents_orchestrator.system_metrics["stuck_tasks"] += 1
                    self.multi_agents_orchestrator.system_metrics["no_progess_minutes"] += 10

                    await self.shared_context.write(
                        "brain3_signal",
                        {
                            "source": "ResumeMatcherAgent",
                            "severity": "high",
                            "reason": "no_fresh_jobs",
                            "run_id": run_id
                        },
                        self.name
                    )

                    logger.warning(f"No FRESH jobs found for run_id: {run_id}")
                    return {"status": "error", "reason": "no_fresh_jobs", "action": "match"}
                
                logger.info(f"Found {len(jobs['ids'])} FRESH jobs from run {run_id}")

                try:
                    existing_matches_result = self.memory.match_collection.get(
                        where={"run_id": run_id,
                        },
                        limit=100
                    )

                    if existing_matches_result and existing_matches_result.get("ids"):
                        existing_ids = existing_matches_result["ids"]

                        for match_id in existing_ids:
                            try:
                                self.memory.match_collection.update(
                                    ids=[match_id],
                                    metadatas=[{"is_fresh": True}]
                                )
                            except Exception as e:
                                logger.warning(f"Could not make re-match {match_id} as fresh {e}")
                        
                        logger.info(f"Re-marked {len(existing_ids)} matches as fresh for report generation")

                        all_existing = self.memory.match_collection.get(
                            where={"run_id": run_id,
                            }
                        )
                        existing_count = len(all_existing.get("ids", []))

                        logger.info(f"LangGraph already created {existing_count} matches for run {run_id} — skipping re-match, signaling report directly")


                        approved_policy = await self.shared_context.read(f"policy_approved_{target_resume_id}")
                        is_refetch = approved_policy is not None and approved_policy.get("approved") is True

                        await self.shared_context.write("ResumeMatcherAgent_target_resume", None, self.name)
                        await self.shared_context.write("new_matches_available", {
                            "count": existing_count,
                            "timestamp": datetime.now().isoformat(),
                            "target_user_id": target_resume_id,
                            "run_id": run_id,
                            "is_refetch": is_refetch
                        }, self.name)

                        await self.emitter.done(
                            run_id,
                            f"Resume Matching found {existing_count} existing strong matches"
                        )

                        await asyncio.sleep(3.0)

                        return {"status": "success", "matches_created": existing_count, "action": "match"}
                except Exception as e:
                    logger.info(f"could no check existing matches {e} Processing with new matches")
                    return {"status": "success", "matches_created": existing_count, "action": "match" }
            
            except Exception as e:
                logger.error(f"Error querying fresh jobs: {e}")
                return {"status": "error", "reason": "query_failed", "action": "match"}

            # Continue with matching logic
            logger.info(f"Processing {len(resumes['ids'])} resume(s) against {len(jobs['ids'])} FRESH jobs")
            if target_resume_id:
                logger.info(f"Target mode: ONLY matching {target_resume_id}")

            await self.emitter.progress(
                run_id,
                "Analyzing job matches with accuracy"
            )
            
            # Prepare job texts
            job_texts = []
            job_documents = jobs.get("documents", [])
            
            for idx, job_id in enumerate(jobs["ids"]):
                if job_documents and idx < len(job_documents) and job_documents[idx]:
                    text = job_documents[idx].strip()
                else:
                    meta = jobs["metadatas"][idx] if idx < len(jobs["metadatas"]) else {}
                    title = meta.get('title') or meta.get('job_title', '')
                    skills = meta.get('skills', [])
                    experience = meta.get('experience', "")

                    text = f"""
                    Title: {title}
                    Skill:{skills}
                    experience: {experience}
                    """
                
                if not text:
                    text = "No description available"
                
                job_texts.append(text)
            
            if not job_texts:
                logger.error("No job texts extracted!")
                return {"status": "error", "reason": "no_job_texts", "action": "match"}
            
            logger.info(f"Prepared {len(job_texts)} job texts for embedding")
            
            # Encode jobs
            try:
                job_emb = self.model.encode(job_texts)
                logger.info(f"Job embeddings shape: {job_emb.shape}")
            except Exception as e:
                logger.error(f"Failed to encode jobs: {e}")
                return {"status": "error", "reason": "encoding_failed", "action": "match"}
            
            if job_emb.size == 0:
                logger.error("Job embeddings are empty!")
                return {"status": "error", "reason": "empty_embeddings", "action": "match"}
            
            matches_created = 0
            threshold = decision.get("threshold", self.match_threshold)
            target_user_id = None
            sim = None  # ensure defined for post-loop use
            
            logger.info(f"Using threshold: {threshold}")
            
            # Match each resume
            for idx, resume_id in enumerate(resumes["ids"]):
                try:
                    resume_text = resumes["documents"][idx]
                    if not resume_text or not resume_text.strip():
                        logger.warning(f"Empty resume text for {resume_id}")
                        continue
                    
                    logger.info(f"Matching resume {idx+1}/{len(resumes['ids'])}: {resume_id}")

                    resume_keywords = EventMonitor.extract_keywords_from_text(resume_text)
                    resume_match_text = " ".join(resume_keywords)
                    
                    resume_emb = self.model.encode([resume_match_text])[0]
                    
                    if len(job_emb.shape) == 1:
                        job_emb_2d = job_emb.reshape(1, -1)
                    else:
                        job_emb_2d = job_emb
                    
                    # Calculate similarity
                    job_norms = np.linalg.norm(job_emb_2d, axis=1)
                    resume_norm = np.linalg.norm(resume_emb)
                    
                    if resume_norm == 0:
                        logger.warning(f"Zero norm for resume {resume_id}")
                        continue
                    
                    if np.any(job_norms == 0):
                        logger.warning(f"Some jobs have zero norm")
                        valid_idx = job_norms > 0
                        job_emb_2d = job_emb_2d[valid_idx]
                        job_norms = job_norms[valid_idx]
                        
                        if len(job_norms) == 0:
                            logger.error("All jobs have zero norm!")
                            continue
                    
                    sim = np.dot(job_emb_2d, resume_emb) / (job_norms * resume_norm)
                    
                    logger.info(f"Similarity scores: max={sim.max():.2f}, min={sim.min():.2f}, mean={sim.mean():.2f}")
                    
                    # Get top matches
                    top_idx = np.argsort(sim)[-10:][::-1]
                    
                    user_id = resumes['metadatas'][idx].get("user_id", "")
                    if not target_user_id:
                        target_user_id = user_id
                    
                    # Extract resume keywords
                    resume_keywords = EventMonitor.extract_keywords_from_text(resume_text)
                    
                    for j in top_idx:
                        score = float(sim[j])
                        if score < threshold:
                            continue

                        job_id = jobs['ids'][j]
                        job_metadata = jobs["metadatas"][j]
                        job_title = (job_metadata.get("job_title") or job_metadata.get("title", "")).lower()
                        job_document = job_documents[j] if job_documents and j < len(job_documents) else ""

                        relevance_boost = sum(
                            0.05 for keyword in resume_keywords
                            if keyword.lower() in job_title
                        )
                        adjusted_score = min(1.0, score + relevance_boost)

                        if adjusted_score < threshold:
                            continue

                        try:
                            already_matched = self.memory.match_collection.get(
                                where={
                                    "$and": [
                                        {"resume_id": resume_id},
                                        {"job_id": job_id}
                                    ]
                                },
                                limit=1
                            )
                            if already_matched and already_matched.get("ids"):
                                logger.info(f"Skipping duplicate match {job_id} for {resume_id}")
                                continue
                        except Exception as e:
                            logger.warning(f"Duplicate check failed: {e}")
                            continue

                        logger.info(f"MATCH FOUND: Job {job_id} (base: {score:.2f}, adjusted: {adjusted_score:.2f})")
                        
                        complete_job = {
                            "id": job_id,
                            "title": job_metadata.get("job_title", ""),
                            "company": job_metadata.get("company", ""),
                            "location": job_metadata.get("location", ""),
                            "salary": job_metadata.get("salary_range", ""),
                            "description": job_metadata.get("description", ""),
                            "url": job_metadata.get("url", ""),
                            "employment_type": job_metadata.get("employment_type", ""),
                            "source": job_metadata.get("source", ""),
                            "full_description": job_document
                        }
                        
                        await self.memory.store_successful_match(
                            user_id=user_id,
                            run_id=run_id,
                            resume_id=resume_id,
                            job=complete_job,
                            match_score=adjusted_score,
                            user_action="auto_created"
                        )
                        matches_created += 1

                    await self.emitter.progress(
                        run_id,
                        f"Analyzing {len(jobs['ids'])} new jobs against resume"
                    )

                    await asyncio.sleep(3.0)
                            
                except Exception as e:
                    logger.error(f"Error matching resume {resume_id}: {e}", exc_info=True)
                    continue

   
            logger.info(f"Created {matches_created} matches total from FRESH jobs")

            await self.shared_context.update_metrics("matches_created_today", matches_created)

            matched_job_ids = []

            if sim is not None:
                matched_job_ids = [
                    job_ids[i]
                    for i, score in enumerate(sim)
                    if score >= threshold
                ]

            if matched_job_ids:
                self.agent_app.memory.job_collection.update(
                    ids=matched_job_ids,
                    metadatas=[
                        {
                            "is_fresh": True,
                            "processed_by": "ResumeMatcherAgent",
                            "processed_at": datetime.now().isoformat(),
                            "run_id": run_id
                        }
                        for _ in range(len(matched_job_ids))
                    ]
                )

            await self.shared_context.write("new_jobs_available", None, self.name)

            # Signal new matches
            if matches_created >= 1:
                await self.shared_context.write("new_matches_available", {
                    "count": matches_created,
                    "timestamp": datetime.now().isoformat(),
                    "target_user_id": target_resume_id,
                    "run_id": run_id
                }, self.name)
                logger.info(f"Signaled new_matches for target user: {target_resume_id}")

            await self.emitter.done(
                run_id,
                f"Resume Matching created {matches_created} strong matches found"
            )

            await asyncio.sleep(3.0)

            return {
                "status": "success",
                "matches_created": matches_created,
                "action": "match"
            }

        except Exception as e:
            logger.error(f"ResumeMatcher act error: {e}", exc_info=True)
            target_user_id = decision.get("target_resume_id")
            if target_user_id:
                await self.shared_context.write(f"{self.name}_target_resume", None, self.name)
            return {"status": "error", "error": str(e), "action": "match"}

class ReportGeneratorAgent(BaseAutonomousAgent):
    """Generate Jobs report for user with Nodes"""
    
    def __init__(self, agent_app, memory, episodic_memory, shared_context, guardrails):
        super().__init__("ReportGeneratorAgent", agent_app, memory, episodic_memory, shared_context, guardrails)
        self.threshold = 1
        self.memory = agent_app.memory
        self.min_new_matches_report = 1
        self.last_report_match_counts = {}
        self.llm_client = LMCClient()
        self.pdf_generator = PDFGenerator()
        self.notification_agent = None
        self.emitter = AgentEmitter("ReportGenetatorAgent", event_bus)
        self.report_this_session = set()

    def link_notification_agent(self, agent):
        self.notification_agent = agent
        logger.info(f"ReportGeneratorAgent linked to NotificationAgent")

    async def perceive(self):
        try:
            
            new_match_signal = await self.shared_context.read("new_matches_available")

            if new_match_signal and isinstance(new_match_signal, dict):
                
                target_user_id = new_match_signal.get("target_user_id")
                is_refetch = new_match_signal.get("is_refetch", False)
                run_id = new_match_signal.get("run_id")

                # Deleting Current match signals
                await self.shared_context.pop("new_matches_available")


                if target_user_id:
                    logger.info(f" New matches signal for TARGET USER: {target_user_id}")

                
                    if f"{target_user_id}_{run_id}" in self.report_this_session and not is_refetch:
                        logger.info(f"Skipping {target_user_id} Already Reported")
                        return {"has_work": False}
                    
                    if is_refetch and target_user_id in self.report_this_session:
                        self.report_this_session.discard(f"{target_user_id}_{run_id}")
                        logger.info(f"Refetch run - gateway cleared for {target_user_id}")
                    
                
                    matches = self.agent_app.memory.match_collection.get(where={"user_id": target_user_id})
                    match_count = len(matches.get("ids", []) if matches else [])

                    if match_count >= self.min_new_matches_report:
                        logger.info(f" Target user {target_user_id} has  {match_count}")
                    
                        return {
                            "has_work": True,
                            "users": [{
                                "user_id": target_user_id,
                                "run_id": run_id,
                                "new_matches": match_count,
                                "total_matches": match_count,
                                "is_refetch": is_refetch
                            }]
                        }
                    else:
                        logger.info(f" Target user {target_user_id} has matches {match_count}  ( need {self.min_new_matches_report})")
                        return {"has_work": False}
                
                else:
                    logger.info("new_matches_available signal has no target_user_id - skipping batch generation")
                    return {"has_work": False}
            
            target_resume_id = None
            if self.current_task and isinstance(self.current_task, dict):
                task_data = self.current_task.get("data", {})
                if isinstance(task_data, dict):
                    target_resume_id = task_data.get("resume_id")
            
            if target_resume_id:
                logger.info(f" Target Resume id Specified {target_resume_id}")

                user_id = target_resume_id.replace("resume_resume_", "_resume_")

                if f"{user_id}_{run_id}" in self.report_this_session:
                    logger.info(f" Skipping {user_id} Already reported this session")
                    return {"has_work": False}
                
        
                matches = self.agent_app.memory.match_collection.get(where={"user_id": user_id})
                match_count = len(matches.get("ids", []) if matches else 0)

                if match_count >= self.threshold:
                    logger.info(f" User {user_id} has matches {match_count}")
                    return {
                        "has_work": True,
                        "users": [{"user_id": user_id, "new_matches": match_count}]
                    }
            return {"has_work": False}
        
        except Exception as e:
            logger.error(f"Report Gen Perceive error {e}", exc_info=True)
            return {"has_work": False}
    
    async def decide(self, perception):
        return {"action": "generate", "users": perception["users"]}
    
    def _build_matched_jobs_from_metadata(self, fresh_jobs: dict) -> list:
        """
        Build matched_jobs list with proper structure and working URLs
        This creates the same format as the working JSON file
        """
        matched_jobs = []
        
        if not fresh_jobs or not fresh_jobs.get("ids"):
            return matched_jobs
        
        logger.info(f"🔧 Building matched_jobs from {len(fresh_jobs['ids'])} ChromaDB results")
        
        for idx, job_id in enumerate(fresh_jobs['ids']):
            meta = fresh_jobs['metadatas'][idx]
            doc = fresh_jobs['documents'][idx] if fresh_jobs.get('documents') and idx < len(fresh_jobs['documents']) else ""
            
            # Extract match score
            match_score = meta.get("match_score", 0)
            if match_score == 0:
                match_score = meta.get("match_percentage", 0)
            
            try:
                match_score = float(match_score)
            except (ValueError, TypeError):
                match_score = 0.0
            
            
            url = meta.get("url", "")
            redirect_url = meta.get("redirect_url", "")

            if redirect_url and redirect_url != "None" and redirect_url.startswith("http"):
                logger.debug(f" Job {idx+1}: Using redirect url")
            else:
                logger.warning(f" Job {idx+1} No redirect url will direct url")
                redirect_url = None
            
            # Clean URL
            if url and url != "None":
                # Validate it's a real URL
                if not url.startswith("http"):
                    logger.warning(f"⚠️ Invalid URL format: {url[:50]}")
                    url = None
            else:
                url = None
            
            if url:
                logger.debug(f"  ✅ Job {idx+1}: {meta.get('job_title', 'N/A')[:30]} -> URL OK ({url[:40]}...)")
            else:
                logger.warning(f"  ⚠️ Job {idx+1}: {meta.get('job_title', 'N/A')[:30]} -> NO URL")
            
            
            job = {
                'job_id': job_id,
                'title': meta.get('job_title') or meta.get('title') or "Position Not Specified",
                'company': meta.get('company') or "Company Not Specified",
                'location': meta.get('location') or "Remote/Not Specified",
                'salary': meta.get('salary_range') or meta.get('salary') or "Competitive (not specified)",
                'description': doc[:1500] if doc else meta.get('description', '')[:1500],
                'url': url, 
                'redirect_url': redirect_url, 
                'match_percentage': match_score,
                'match_score': match_score,
                'employment_type': meta.get('employment_type') or meta.get('job_type') or "Full-time",
                'source': meta.get('source', 'N/A'),
                'job_type': meta.get('employment_type') or meta.get('job_type') or "Full-time",
                'tags': [],
                'composite_score': match_score / 100.0,  
                'ranking_reasoning': {},
                'recommendation': 'Review and Apply'
            }
            
            matched_jobs.append(job)

        
        # Sort by match score (descending)
        matched_jobs.sort(key=lambda x: x['match_score'], reverse=True)
        
        logger.info(f"📦 Built {len(matched_jobs)} matched_jobs with {sum(1 for j in matched_jobs if j['url'])} valid URLs")
        
        return matched_jobs
    
    async def act(self, decision):
        """Fixed version with proper run_id handling and fresh job filtering"""

        count = 0
        processed_run = set()

        for user_data in decision["users"]:
            user_id = user_data["user_id"]

            run_id = user_data.get("run_id")

            if (user_id, run_id) in processed_run:
                logger.info(f" Skipping user id {user_id} - already_processed")
                continue
            
            if not run_id:
                logger.warning(f"No run_id in Resume Matcher found for: {user_id}")
                continue

            processed_run.add((user_id, run_id))

            try:
                resume = self.agent_app.memory.resume_collection.get(where={"run_id": run_id})
                if not resume or not resume.get("documents"):
                    logger.warning(f"No resume found for {run_id}")
                    resume_text = ""
                else:
                    resume_text = resume["documents"][0]
  
                if run_id:
                    logger.info(f"Fetching FRESH matches for run_id: {run_id}")
                    fresh_jobs = self.agent_app.memory.match_collection.get(
                        where={
                            "$and": [
                                {"run_id": run_id},
                                {"is_fresh": True},
                            ]
                        },
                        limit=100,
                        include=["metadatas", "documents"]
                    )

                await self.emitter.start(
                    run_id,
                    "Starting Generating your personalized jobs available jobs report it may take couple of minutes stay with us"
                )

                await asyncio.sleep(3.0)
   
                logger.info(f"🔧 Converting ChromaDB results to matched_jobs format")
                matched_jobs = self._build_matched_jobs_from_metadata(fresh_jobs)
                
                if not matched_jobs:
                    logger.warning(f"No valid matched_jobs after conversion for {fresh_jobs}")
                    continue
                
                # Log URL status
                urls_present = sum(1 for job in matched_jobs if job.get('url'))
                logger.info(f"📊 Matched jobs stats: {len(matched_jobs)} total, {urls_present} with URLs")
                
           
                logger.info(f"📄 Generating report with {len(matched_jobs)} matched jobs")
                report_content = await self.llm_client.generate_job_report(
                    resume_text=resume_text,
                    matches=matched_jobs  
                )

                if not report_content:
                    logger.warning(f"Failed to generate report for {user_id}")
                    continue

                highest_match_score = max(
                    [job.get("match_percentage", 0) for job in matched_jobs],
                    default=0
                )

                report_history_payload = {
                    "user_id": user_id,
                    "run_id": run_id,
                    "report_type": "job_match_report",
                    "summary": report_content[:1500],
                    "top_jobs_count": len(matched_jobs),
                    "highest_match_score": highest_match_score,
                    "recommended_actions": {
                        "top_companies": [job.get("company") for job in matched_jobs[:5]],

                        "top_roles": [job.get("job") or job.get("title") or job.get("job_title")
                        for job in matched_jobs[:5]
                        ],

                        "top_match_score": [
                            job.get("match_percentage", 0)
                            for job in matched_jobs[:5]
                        ]
                    },
                    "email_subject": "Your AI Job match report",
                    "sent_to_email": user_data.get("email")

                }

                await self.agent_app.multi_agent_orchestrator.outcome_database.save_report_history(report_history_payload)
                
                # Verify URLs made it into the report
                url_count_in_report = report_content.count('](http')
                logger.info(f"🔗 Report contains {url_count_in_report} clickable URLs")
                
                if url_count_in_report < min(5, urls_present):
                    logger.warning(f"⚠️ Expected ~{min(5, urls_present)} URLs but only found {url_count_in_report}")
                
                pdf_path = self.pdf_generator.markdown_to_pdf(
                    markdown_content=report_content
                )

                if self.notification_agent:
                    await self.notification_agent.receive_job_report(user_id, report_data={
                        "pdf_path": pdf_path,
                        "run_id": run_id  
                    })

                    logger.info(f"Report handed to notification agent for {user_id}")
                    count += 1
                    self.report_this_session.add(f"{user_id}_{run_id}")

                await self.emitter.progress(
                    run_id,
                    f" Your professional report for {user_id} is generated"
                )

                await self.agent_app.update_stats("jobs_matched", user_id, run_id, len(matched_jobs))
                await self.agent_app.update_stats("reports_generated", user_id, run_id, 1)

                await asyncio.sleep(3.0)
                
                current_total = len(matched_jobs)
                self.last_report_match_counts[user_id] = current_total


                await self.emitter.done(
                    run_id,
                    f"Handing your Report to notification agent {user_id}"
                )

                await asyncio.sleep(3.0)

                
                await self.shared_context.update_metrics("reports_generated_today")
                await self.guardrails.record_action("generated_report")
                
                
                for match_id in fresh_jobs['ids']:
                    try:
                        existing_meta_result = self.agent_app.memory.match_collection.update(
                            ids=[match_id],
                            metadatas=["metadatas"]
                        )
                        if not existing_meta_result or not existing_meta_result.get("metadatas"):
                            continue

                        existing_meta = existing_meta_result["metadatas"][0]
                        updated_meta = {
                            **existing_meta,
                            "is_fresh": True,
                            "run_id": run_id,
                            "resused_at": datetime.now().isoformat()
                        }

                        # cleaning before writing
                        updated_meta = {k: (v if v is not None else "") for k, v in updated_meta.items()}
                        self.memory.match_collection.update(
                            ids=[match_id],
                            metadatas=[updated_meta]
                        )
                    except Exception as e:
                        logger.warning(f"Could not mark match {match_id} as not fresh: {e}")
            
            except Exception as e:
                logger.error(f"Report failed to generate for {user_id}: {e}", exc_info=True)
                continue
     
        await self.shared_context.write("new_matches_available", None, self.name)

        logger.info(f"Reports Generated {count}")
        return {
            "status": "success",
            "reports": count,
            "action": "generated"
        }

class NotificationAgent(BaseAutonomousAgent):
    """Sends email notifications - ENHANCED"""
    
    def __init__(self, agent_app, memory, episodic_memory, shared_context, guardrails):
        super().__init__("NotificationAgent", agent_app, memory, episodic_memory, shared_context, guardrails)
        self.email_sender = EmailSender()
        self.event_bus = get_event_bus()
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.memory = agent_app.memory
        self.emitter = AgentEmitter("NotificationAgent", event_bus)
        self.pending_reports = {}
        self.slack_cooldown_seconds = 300
        self.last_sent = {}
        self.retry_unverified = True
        logger.warning(f"NotificationAgent created:  | id={id(self)}")

        self.listener_started = False
        if not self.listener_started:
            self.listener_started = True           
            asyncio.create_task(self._listen_brain3())

    async def _listen_brain3(self):
            logger.warning("Notification agent Event listener started")

            async for event in self.event_bus.subscribe():
                if event.get("type") == "BRAIN3_ALERT":
                    await self.handle_brain3_decision(event)
                
                elif event.get("type") == "JOB_APPLIED":
                    await self.handle_applied_jobs(event)
                
                elif event.get("type") == "JOB_STATUS_CHANGED":
                    await self.handle_job_status_change(event)

                elif event.get("type") == "API_ERROR":
                    await self.handle_api_error(event)
                
                elif event.get("type") == "FOLLOWUP_JOB_REQUEST":
                    await self.reminder_job_email(event)

    async def send_slack_alert(self, message: str, severity: str = "info"):
        color = {"critical": "#ff0000", "warning": "#ffa500", "info": "#36a64f"}.get(severity, "#36a64f")

        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"Agentic Career Alert - {severity.upper()}",
                    "text": message
                }
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.slack_webhook_url, json=payload) as resp:
                    if resp.status !=200:
                        raise Exception(f"Slack webhook failed {resp.status}")

            logger.info(f"Slack alert sent")
        except Exception as e:
            logger.error(f"Slack alert failed {e}")
    
    async def handle_applied_jobs(self, event: Dict):
        user_id = event["user_id"]
        job = event["job_metadata"]


        prefs = await self.agent_app.memory.get_user_preferences(user_id)

        if not prefs:
            logger.info(f"No Preferences found for user_id {user_id}")
            return
        
        email= prefs.get("email") or prefs.get("emai")
        
        subject = "✅ Job Application Tracked Successfully"

        body = f"""
        <html>
        <body>
            <h2>OS agent has started tracking your application 🎯</h2>
            <p><strong>Role:</strong> {job.get("job_title") or job.get("title")}</p>
            <p><strong>Company:</strong> {job.get("company")}</p>
            <p><strong>Status:</strong> Applied</p>
            <p>System Employee Strategic Agent will Track Your application From Here:</p>
            <ul>
            <li>Track responses</li>
            <li>Monitor follow-ups</li>
            <li>Alert you if action is needed</li>
            </ul>
        </body>
        </html>
        """
        await asyncio.to_thread(
            self.email_sender.send_report,
            subject, 
            email,
            body
        )

        logger.info(f"Application tracking email sent to {email}")
    
    async def handle_api_error(self, event: Dict):
        payload = event.get("payload", {})

        run_id = payload.get("run_id")
        keywords = payload.get("keywords")
        location = payload.get("location")
        source = payload.get("source")
        message = payload.get("message")

        alert_message = (
            "API Error Detected\n"
            f"source: {source}\n"
            f"keywords: {keywords}\n"
            f"location: {location}\n"
            f"Run ID: {run_id}\n"
            f"Message: {message}"
        )

        logger.warning(f"API ERROR {alert_message}")

        await self.send_slack_alert(alert_message, severity="critical")

    
    async def handle_job_status_change(self, event: Dict):
        user_id = event["user_id"]
        job_id = event["job_id"]
        new_status = event["new_status"]
        job = event.get("job_metadata") or {}

        logger.warning(f"Notification job handling STATUS_CHANGES: {job_id} {new_status}")
        
        prefs = await self.agent_app.memory.get_user_preferences(user_id)
        
        if not prefs:
            logger.warning(f"No Preferences found for user {user_id}")
            return

        email = prefs.get("email") or prefs.get("emai")
        if not email:
            logger.warning(f"No email for user: {user_id}")
            return

        flag_key = f"{new_status}_notified"
        if job.get(flag_key):
            logger.info(f"Already Notified for {job_id}, {user_id}")
            return
        
        if new_status == "no_response":
            subject = "⏳ No response yet — Os Agent team is monitoring"
            body = f"""
            <html>
            <body>
                <h3>Still waiting — no action needed yet</h3>
                <p><strong>Role:</strong> {job.get("job_title") or job.get("title")}</p>
                <p><strong>Company:</strong> {job.get("company")}</p>
                <p>It's been a few days with no response.</p>
                <p>Our agent will Continue Monitoring:</p>
                <ul>
                <li>Continue monitoring</li>
                <li>Suggest follow-ups if needed</li>
                <li>Re-run job discovery if this goes cold</li>
                </ul>
            </body>
            </html>
            """
            try:
                await asyncio.to_thread(
                    self.email_sender.send_report,
                    subject,
                    email,
                    body
                )
                logger.info(f"Status changed email sent {email} {user_id}")

                job[flag_key] = True
                await self.agent_app.multi_agent_orchestrator.outcome_database.update_job(job)
            except Exception as e:
                logger.error(f" Failed to sent status changed email: {e}", exc_info=True)

        elif new_status == "dead_application":
            subject = "❌ Application marked inactive — next steps ready"
            body = f"""
            <html>
            <body>
                <h3>This application looks inactive</h3>
                <p><strong>Role:</strong> {job.get("job_title") or job.get("title")}</p>
                <p><strong>Company:</strong> {job.get("company")}</p>
                <p>Your agent recommends:</p>
                <ul>
                <li>Re-applying to similar roles</li>
                <li>Adjusting resume keywords</li>
                <li>Running a new job search</li>
                </ul>
            </body>
            </html>
            """
            try:
                await asyncio.to_thread(
                    self.email_sender.send_report,
                    subject,
                    email,
                    body
                )
                logger.info(f"Status change email sent to {email} {user_id}")

                job[flag_key] = True
                await self.agent_app.multi_agent_orchestrator.outcome_database.update_job(job)
            
            except Exception as e:
                logger.error(f"Failed to send status change email:{e}", exc_info=True)

    async def handle_brain3_decision(self, event: Dict):
        level = event.get("level") or event.get("severity") or "info"
        payload = event.get("payload", {})
        confidence = payload.get("confidence", 1.0)
        human_required = payload.get("human_required", False)
        intent = event.get("message", "unknown")

        dedulpe_key = f"{event.get('type')}::{intent}::{level}"

        now = time.time()

        last = self.last_sent.get(intent)
        if last and (now - last) < self.slack_cooldown_seconds:
            return
        self.last_sent[dedulpe_key] = now

        if level in ["warning", "critical"] or human_required:
            logger.warning(f"Brain3 Alerted: {intent} confidence={confidence:.0%}, human_required={human_required}")
            
            alert_message  = (
                "Brain3 Decision alert*\n"
                f"Intent: {intent} \n"
                f"*Confidence: *{confidence}"
                f"*Human required:* {human_required}"
            )

            await self.send_slack_alert(alert_message, severity=level)
    
    async def reminder_job_email(self, event:dict):
        try:
            payload = event.get("payload", {})
            user_id = payload.get("user_id")
            run_id = payload.get("run_id")
            job_id = payload.get("job_id")

            if not user_id or not job_id:
                logger.info("Missing job_id and user_id in job reminder email")
                return
            
            prefs = await self.agent_app.memory.get_user_preferences(user_id)
            if not prefs:
                logger.info(f"No Prefs found for {user_id} in Reminder job email from agent")
                return
            
            to_email = prefs.get('email') or prefs.get('emai')
            if not to_email:
                logger.info("Already notified from reminder email agent")
                return
            

            job_result = await self.agent_app.multi_agent_orchestrator.outcome_database.get_job_by_id(job_id, user_id)
            if not job_result:
                logger.warning(f"Job no found {user_id}")
                return
            
            job = job_result

            subject = f"Follow up {job.get('job_title') or job.get('title')}"

            last_followup = job.get("last_followup_at")
            if last_followup:
                last_followup = datetime.fromisoformat(last_followup)
                if(datetime.now() - last_followup).days <2:
                    logger.info(f"skipping followup (cooldown active) for job {job_id}")
                    return
            
            email_content = await self.generate_email(job)

            await asyncio.to_thread(
                    self.email_sender.send_report,
                    subject,
                    to_email,
                    email_content
            )

            job["last_followup_at"] = datetime.now().isoformat()
            job["followup_count"] = job.get("followup_count", 0) + 1
            

            await self.agent_app.multi_agent_orchestrator.outcome_database.update_followup_agent_fields(
                job_id=job.get("job_id"),
                user_id=user_id,
                last_followup_at=job["last_followup_at"],
                followup_count=job["followup_count"]
            ) 
        
        except Exception as e:
            logger.info(f"Error in job reminder function {e}")
    
    async def generate_email(self, job):
        followup_message = f"""
    Hi {job.get("company", "Hiring Team")},

    I hope this message finds you well.

    I wanted to follow up regarding my application for the **{job.get("job_title", "position")}** role. I remain very interested in this opportunity and would appreciate any updates you may be able to share about the current status of my application.

    Please let me know if there is any additional information I can provide.

    Thank you for your time and consideration.

    Kind regards,  
    {job.get("candidate_name", "Candidate")}
    """

        return f"""
    <html>
    <body>

    <h2>📩 Follow-up Suggested by Your AI Career Assistant</h2>

    <p>Hi,</p>

    <p>Your application for the following role has not received a response yet:</p>

    <ul>
    <li><strong>Role:</strong> {job.get("job_title") or job.get("title")}</li>
    <li><strong>Company:</strong> {job.get("company")}</li>
    </ul>

    <p>Based on this, your AI system recommends sending a follow-up email to increase your chances of getting a response.</p>

    <hr>

    <h3>✉️ Suggested Follow-up Message:</h3>

    <pre>{followup_message}</pre>

    <hr>

    <p><strong>What you can do next:</strong></p>
    <ul>
    <li>Review and personalize the message if needed</li>
    <li>Send it to the recruiter or hiring manager</li>
    </ul>

    <p>Your AI assistant will continue monitoring your application and notify you of any updates.</p>

    <br>

    <p>Best regards,<br>
    Your AI Career Assistant</p>

    </body>
    </html>
"""

    async def receive_job_report(self, user_id: str, report_data: Dict):
        """Receive a report from ReportGeneratorAgent"""
        self.pending_reports[user_id] = report_data
        logger.info(f"📬 NotificationAgent received report for {user_id}")
    
    async def perceive(self):
        """Check if there are pending reports to send"""
        if self.pending_reports:
            logger.info(f"📧 {len(self.pending_reports)} pending notifications detected")
            return {"has_work": True, "pending_count": len(self.pending_reports)}
        
        # Also check if ReportGenerator signaled us
        new_matches = await self.shared_context.read("new_matches_available")
        if new_matches:
            logger.info(f"📬 New matches signal (will wait for reports)")
        
        return {"has_work": False}

    async def decide(self, perception):
        return {"action": "send_notifications"}
    

    async def act(self, decision):
        """Send all pending notifications"""

        sent_count = 0
        failed_count = 0

        for user_id, report_data in list(self.pending_reports.items()):
            try:
                run_id = await self.shared_context.read(f"current_run_id_{user_id}")
                if not run_id:
                    logger.warning(f"No run_id for {user_id} - skipping notification")
                    continue


                await self.emitter.start(
                    run_id,
                    f"Nofitication agent got your matching career report"
                )

                await asyncio.sleep(3.0)
                
                # Clean user ID variations
                clean_id = user_id.replace("_", "").replace("resume", "")

                search_ids = [
                    f"Prefs_{clean_id}",
                    f"Prefs_{user_id}",
                    clean_id,
                    user_id
                ]

                prefs = None

                # Try finding preferences by ID
                for sid in search_ids:
                    try:
                        result = self.memory.preferences_collection.get(ids=[sid])
                        if result and result.get("ids"):
                            prefs = result
                            logger.info(f" Found preferences with ID: {sid}")
                            break
                    except Exception as e:
                        continue
                
                # Try finding by metadata
                if not prefs:
                    try:
                        result = self.memory.preferences_collection.get(
                            where={"user_id": user_id}
                        )
                        if result and result.get("metadatas"):
                            prefs = result
                            logger.info(f" Found preferences via metadata")
                    except Exception as e:
                        logger.error(f"Metadata search failed: {e}")
                
                if not prefs:
                    logger.warning(f"⚠️ No preferences found for user {user_id}")
                    logger.warning(f"   Tried IDs: {search_ids}")
                    del self.pending_reports[user_id]
                    failed_count += 1
                    continue

                # Extract email
                metadata = prefs["metadatas"][0]
                user_email = metadata.get("email") or metadata.get("emai")

                email_verified = metadata.get("email_verified", False)

                if not email_verified:
                    logger.info(f"Email is not verified : {user_id} (email_verified={email_verified}), Skipping Notification")
                    del self.pending_reports[user_id]
                    failed_count +=1
                    continue

                logger.info(f" Email verified for {user_id}, processing with notification")


                if not user_email or not user_email.strip():
                    logger.info(f"No email Preferences found in the resume {user_id} EMailSender will use default")
                    user_email = None 

                pdf_path = report_data.get("pdf_path")        
                
                # Create HTML email
                html_body = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                        .header {{ background: #4CAF50; color: white; padding: 20px; }}
                        .content {{ padding: 20px; }}
                        pre {{ white-space: pre-wrap; font-family: Arial; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>🎯 Your Job Matches Are Ready!</h1>
                        <p>Generated by AI Agent System</p>
                    </div>
                    <div class="content">
                        <pre>{pdf_path}</pre>
                    </div>
                </body>
                </html>
                """

                if not pdf_path:
                    logger.info(f"Missing pdf path for {user_id}, skipping email")
                    continue
                
                email_subject = f"🎯 New Job Matches - {datetime.now().strftime('%Y-%m-%d')}"
                # Send email
                logger.info(f"📤 Sending email to {user_email}")
                sent = self.email_sender.send_report(
                    to_email=user_email,
                    subject=email_subject,
                    body=html_body,
                    pdf_path =pdf_path
                )
                
                if sent:
                    await self.agent_app.multi_agent_orchestrator.outcome_database.save_email_history({
                        "user_id": user_id,
                        "run_id": run_id,
                        "email_type": "job_report",
                        "recipient": user_email,
                        "subject": email_subject,
                        "status": "sent",
                        "metadata_json": {
                            "source": "NotificationAgent",
                            "pdf_path": pdf_path
                        },
                    })

                    logger.info(f" Email sent successfully to {user_email}")
                    del self.pending_reports[user_id]
                    sent_count += 1

                else:
                    await self.agent_app.multi_agent_orchestrator.outcome_database.save_email_history({
                        "user_id": user_id,
                        "run_id": run_id,
                        "email_type": "job_report",
                        "recipient": user_email,
                        "subject": email_subject,
                        "status": "failed",
                        "error_message": "email_sender.send_report returned False",
                        "metadata_json": {
                            "source": "NotificationAgent",
                            "pdf_path": pdf_path
                        },
                    })

                    logger.error(f" Failed to send email to {user_email}")
                    failed_count += 1


                    self.agent_app.multi_agent_orchestrator.system_metrics["error_count_last_hour"] +=1

                    await self.shared_context.write(
                        "brain3_signal",
                        {
                            "source": "NotificationAgent",
                            "severity": "low",
                            "reason": "email_failed",
                            "user_id": user_id,
                            "timestamp": datetime.now().isoformat()
                        },
                        self.name
                    )

                await self.emitter.done(
                    run_id,
                    f"Notification count {sent_count}, Failed: {failed_count}",
                    {
                        "sent": sent_count,
                        "failed": failed_count
                    }
                )

                await asyncio.sleep(3.0)

                await self.agent_app.update_stats("tasks_completed", user_id, run_id, 1)
    
            except Exception as e:
                logger.error(f" Notification error for {user_id}: {e}", exc_info=True)
                failed_count += 1
    
        
        logger.info(f"📊 Notifications: {sent_count} sent, {failed_count} failed")
        return {
            "status": "success",
            "emails_sent": sent_count,
            "emails_failed": failed_count,
            "action": "send_notifications"
        }

class MemoryMaintenanceAgent(BaseAutonomousAgent):
    """Maintains RAG memory system - FIXED"""
    accepted_keywords = ["memory", "maintenance", "clean_up"]
    
    def __init__(self, agent_app, memory, episodic_memory, shared_context, guardrails):
        super().__init__("MemoryMaintenanceAgent", agent_app, memory, episodic_memory, shared_context, guardrails)
        self.interval = 300  
        self.job_retention_days = 2
        self.resume_retention_days =7
        self.match_retention_days = 90
        self.memory = agent_app.memory
        self.last_maintenance = None

        self.max_jobs  = 15
        self.max_resume = 10
        self.max_matches = 20

    def _parse_created(self, created):
        if isinstance(created, datetime):
            return created

        if isinstance(created, (int, float)):
            return datetime.fromtimestamp(created)

        if isinstance(created, str):
            
            try:
                return datetime.fromisoformat(created)
            except ValueError:
                pass

            try:
                return datetime.fromtimestamp(float(created))
            except ValueError:
                pass

        raise ValueError(f"Unsupported created type/value: {created} ({type(created)})")

    async def perceive(self):
        """Checking if maintenance is needed"""

        command = await self.shared_context.read("maintenance_command")
        if command and command.get("run"):
            logger.info("Brain3 ")
            return {"has_work": True, "reason": "brain3_triggered"}
        try:
            job_count = len(self.agent_app.memory.job_collection.get().get("ids", []))
            match_count =  len(self.agent_app.memory.match_collection.get().get("ids", []))
            resume_count = len(self.agent_app.memory.resume_collection.get().get("ids", []))

            if job_count > self.max_jobs:
                logger.warning(f" triggering memory maintenance {job_count} (max: {self.max_jobs})")
                return {
                    "has_work": True,
                    "reason": "emergency_jobs",
                    "job_count": job_count
                }
            
            if resume_count > self.max_resume:
                logger.warning(f"triggering memory maintenance {resume_count} (max {self.max_resume})")
                return {
                    "has_work": True,
                    "reason": "emergency_resumes",
                    "resume_count": resume_count
                }
            
            if match_count > self.max_matches:
                logger.warning(f" triggering memory maintenance {match_count} (max: {self.max_matches})")
                return {
                    "has_work": True,
                    "reason": "emergency_matches",
                    "match_count": match_count
                }
        except Exception as e:
            logger.error(f" error checking collection sizes {e}")
        
        if self.last_maintenance is None:
            logger.info("Initializing First run -Performing maintenance")
            return {"has_work": True, "reason": "first_run"}
        
        time_since = (datetime.now() -  self.last_maintenance).total_seconds()

        if time_since >= self.interval:
            logger.info(f"Maintencance interval reached ({time_since:.0f}s / {self.interval}s)")
            return {"has_work": True, "reason": "interval_reached"}

        seconds_left = self.interval - time_since
        logger.debug(f" Cooldown {seconds_left:.0f}s remaining")
        return {"has_work": False, "reason": "cooldown", "seconds_left": seconds_left} 

    async def decide(self, perception):

        reason =perception.get("reason")

        if reason in ["emergency_jobs", "emergency_matches", "emergency_resumes"]:
            return {
                "action": "emergency_cleanup",
                "reason": reason,
                "aggressive": True
            }
        
        return {
            "action": "maintain",
            "reason": reason,
            "aggressive": False
        }

    async def act(self, decision):
        """Performing Enhanced maintenace tasks"""
        logger.info(f" Starting maintenance (mode: {decision.get('action')})")

        tasks_completed = []
        jobs_to_delete = []

        aggressive = decision.get("aggressive", False)

        self.last_maintenance = datetime.now()

        try:
            retention_days = self.job_retention_days // 2 if aggressive else self.job_retention_days
            cutoff_time = datetime.now().timestamp() - (retention_days * 86400)

            jobs = self.agent_app.memory.job_collection.get()
            if jobs and jobs.get("ids"):

                old_jobs = []
                stale_jobs = []

                for idx, job_id in enumerate(jobs["ids"]):
                    metadata = jobs["metadatas"][idx]

                    created =  metadata.get("created_at", datetime.now())
                    created_dt = self._parse_created(created)
                    
                    age_days = (datetime.now() -  created_dt).total_seconds() / 86400

                    if created_dt.timestamp() < cutoff_time and not metadata.get("matched"):
                        stale_jobs.append(job_id)
                    
                jobs_to_delete  = list(set(old_jobs + stale_jobs))

                if jobs_to_delete:
                    self.agent_app.memory.job_collection.delete(ids=jobs_to_delete)
                    logger.info(f" Jobs to deleted {len(jobs_to_delete)} jobs( old {stale_jobs})")
                    tasks_completed.append(f"jobs_clean{jobs_to_delete}")
                else:
                    logger.info(" No jobs to clean")
                    tasks_completed.append("clean_jobs:0")
        except Exception as e:
            logger.error(f"Failed to clean jobs from memory jobs {e}", exc_info=True)
    
        try:
            retention_days = self.match_retention_days // 2 if aggressive else self.match_retention_days
            cutoff_time = datetime.now().timestamp() - (retention_days * 86400)
            resume_count  = len(self.agent_app.memory.resume_collection.get().get("ids", []))

            matches = self.agent_app.memory.match_collection.get()
            old_matches = []

            if matches and matches.get("ids"):

                for idx, match_id in  enumerate(matches["ids"]):
                    metadata = matches["metadatas"][idx]
                    created = metadata.get("created_at", datetime.now().timestamp())

                    if isinstance(created, str):
                        try:
                            created = parser.parse(created).timestamp()
                        except:
                            created = datetime.now().timestamp()

                    if created < cutoff_time:
                        old_matches.append(match_id)

                match_count = len(matches.get("ids", []))
                overflow = match_count - self.max_matches
                 
                if overflow > 0:
                    sorted_matches = sorted(
                        zip(matches["ids"], matches["metadatas"]),
                        key = lambda x: parser.parse(x[1].get("created_at", datetime.now().isoformat())).timestamp()
                    )
                    to_delete = [m[0] for m in sorted_matches[:overflow]]
                    old_matches.extend(to_delete)
            
            if old_matches:
                self.agent_app.memory.match_collection.delete(ids=old_matches)
                logger.info(f"Deleted {len(old_matches)} old matches")
                tasks_completed.append(f"clean_old_matches{len(old_matches)}")
            
            else:
                logger.info("No old_matches found")
                tasks_completed.append("clean_match:0")
        
        except Exception as e:
            logger.error(f"error in deleting old matches {e}", exc_info=True)
    
        try:
            jobs = self.agent_app.memory.job_collection.get()
            if jobs and jobs.get("ids"):
                url_map = {}
                duplicates = []
                
                for idx, job_id in enumerate(jobs["ids"]):
                    metadata = jobs["metadatas"][idx]
                    url = metadata.get("url") or metadata.get("job_apply_link", "")
                    
                    if url:
                        if url in url_map:
                            # Keep the newer one
                            duplicates.append(job_id)
                        else:
                            url_map[url] = job_id
                
                if duplicates:
                    self.agent_app.memory.job_collection.delete(ids=duplicates)
                    logger.info(f"🗑️ Deleted {len(duplicates)} duplicate jobs")
                    tasks_completed.append(f"clean_duplicates:{len(duplicates)}")
                else:
                    tasks_completed.append("clean_duplicates:0")

        except Exception as e:
            logger.error(f"❌ Failed to clean duplicates: {e}", exc_info=True)
        
        try:
            jobs = self.agent_app.memory.job_collection.get()
            if jobs and jobs.get("ids"):
                stale_fresh_jobs = []
                cutoff = datetime.now().timestamp() - (7 * 86400)  
                
                for idx, job_id in enumerate(jobs["ids"]):
                    metadata = jobs["metadatas"][idx]
                    created_dt = self._parse_created(
                        metadata.get("created_at", datetime.now())
                    )

                    if metadata.get("is_fresh") and metadata.get("created_at", 0) < cutoff:
                        stale_fresh_jobs.append(job_id)
                
                job_count = len(jobs.get("ids", []))
                overflow = job_count - self.max_jobs

                if overflow > 0:
                    sorted_jobs = sorted(
                        zip(jobs["ids"], jobs["metadatas"]),
                        key=lambda x: self._parse_created(
                            x[1].get("created_at", datetime.now())
                        )
                    )

                    oldest_jobs = [j[0] for j in sorted_jobs[:overflow]]
                    jobs_to_delete.extend(oldest_jobs)

                jobs_to_delete = list(set(jobs_to_delete))
                
                if stale_fresh_jobs:
                    for job_id in stale_fresh_jobs:
                        self.agent_app.memory.job_collection.update(
                            ids=[job_id],
                            metadatas=[{"is_fresh": False}]
                        )
                    logger.info(f"🔄 Marked {len(stale_fresh_jobs)} jobs as not fresh")
                    tasks_completed.append(f"mark_not_fresh:{len(stale_fresh_jobs)}")

        except Exception as e:
            logger.error(f"❌ Failed to mark stale jobs: {e}", exc_info=True)

        try:
            retention_days = self.resume_retention_days // 2 if aggressive else self.resume_retention_days
            cutoff = datetime.now().timestamp() - (retention_days * 86400)

        
            resumes = self.agent_app.memory.resume_collection.get()
            if resumes and resumes.get("ids"):
                old_resumes = []
                stale_resumes = []
                

                for idx, resume_id in enumerate(resumes["ids"]):
                    metadata = resumes["metadatas"][idx]
                    created = metadata.get("created_at", datetime.now())
                    created_dt = self._parse_created(created)
            
                    if created_dt.timestamp() < cutoff:
                        old_resumes.append(resume_id)
                    
                    elif aggressive:
                        age_days = (datetime.now() - created_dt).total_seconds() / 86400

                        if age_days > 3 and not metadata.get("matched"):
                            stale_resumes.append(resume_id)
                
                resumes_to_delete = list(set(stale_resumes + old_resumes))

                resume_count = len(resumes.get("ids", []))
                overflow = resume_count -  self.max_resume

                if overflow >0:

                    sorted_resumes = sorted(
                        zip(resumes["ids"], resumes["metadatas"]),
                        key=lambda x: self._parse_created(x[1].get("created_at", datetime.now()))
                    )
                
                    # Deleting old rsumes
                    to_delete = [r[0] for r in sorted_resumes[:overflow]]
                    resumes_to_delete.extend(to_delete)
                    resumes_to_delete = list(set(resumes_to_delete))
                
                if resumes_to_delete:
                    self.agent_app.memory.resume_collection.delete(ids=resumes_to_delete)
                    logger.info(f"Deleted: {len(resumes_to_delete)} resumes (old {len(old_resumes)}), stale {len(stale_resumes)}")
                    tasks_completed.append(f" clean_resumes {len(resumes_to_delete)}")
                
                else:
                    logger.info("No resumes to delete")
                    tasks_completed.append("cleaned_resumes:0")
            
            else:
                logger.info("No resumes found in collection")
                tasks_completed.append("cleaned_resumes:0")
        
        except Exception as e:
            logger.error(f"Failed to clean_resumes {e}", exc_info=True)        

        try:
            job_count = len(self.agent_app.memory.job_collection.get().get("ids", []))
            match_count = len(self.agent_app.memory.match_collection.get().get("ids", []))
            resume_count = len(self.agent_app.memory.resume_collection.get().get("ids", []))

            logger.info(f" Collection Stats:")
            logger.info(f" jobs:{job_count}  / {self.max_jobs}")
            logger.info(f" resumes: {resume_count}")
            logger.info(f" match: {match_count} / {self.max_matches}")

            # storing in shared context
            await self.shared_context.write("collection_state", {
                "jobs": job_count,
                "matches": match_count,
                "resumes": resume_count,
                "timestamp": datetime.now().isoformat()
            }, self.name)

            tasks_completed.append("collection_stats")
        except Exception as e:
            logger.error(f" Failed to collect stats {e}")
        
        # Logging maintencance Completion
        logger.info(f" Maintenance completed {len(tasks_completed)}")
        for task in tasks_completed:
            logger.info(f"  - {task}")
        
        return {
            "status": "completed",
            "task_completed": tasks_completed,
            "action": decision.get("action"),
            "next_maintenance": (datetime.now() + timedelta(seconds=self.interval)).isoformat()
        }
        







        

                    



        

    












        



            










        





































        






    
