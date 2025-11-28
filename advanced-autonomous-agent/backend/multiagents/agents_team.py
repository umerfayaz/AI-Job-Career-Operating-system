### Multi Agents With Episodic Memory

import os
import asyncio
import structlog
import numpy as np 
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dateutil import parser
from backend.multiagents.guardrails import JobReportGuardrails
from sentence_transformers import SentenceTransformer
import json

from ..core.memory_system import MemoryRAGSystem
from ..core.email_sender import EmailSender


def get_agent_app():
    from backend.application import AgentApplication
    return AgentApplication()

logger = structlog.get_logger()


class EpisodicMemory:
    def __init__(self, memory: MemoryRAGSystem):
        self.memory=memory
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
            "success": result.get("status") == "success"
        }

        self.experiences.append(experience)


        if len(self.experiences) > self.max_experiences:
            self.experiences = self.experiences[-self.max_experiences:]
        
        logger.info(f"{agent_name} recorded experiences:{action}")
    

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
    
        ## Extract from failures
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
    """Shared memory speces for inter-agent Commounications"""

    def __init__(self):
        self.context = {
            "goals": [],
            "active_tasks": {},
            "completed_tasks": {},
            "agent_states": {},
            "global_metrics":{
                "jobs_scraped_today": 0,
                "matches_created_today": 0,
                "reports_generated_today": 0
            },
            "last_reset": datetime.now()
        }
        self.lock =asyncio.Lock()
    
    async def write(self, key: str, value: Any, agent_name:str):
        """write a shared context"""
        async with self.lock:
            self.context[key] = value
            logger.info(f"{agent_name} updated{key}")
    
    async def read(self, key:str) ->Any:
        """Read shared context"""
        async with self.lock:
            return self.context.get(key)

    async def update_metrics(self, metric:str, increment: int =1):
        """Update global metrics"""
        async with self.lock:
          if metric in self.context["global_metrics"]:
            self.context["global_metrics"][metric] += increment
    
    async def set_agent_state(self, agent_name, state_dict ) ->Dict:
        """Get Agent current state"""
        async with self.lock:
             self.context["agent_states"].get(agent_name, {})
             return state_dict
    
    async def add_task(self, task_id: str, task:Dict, agent_name:str):
        """Add a new task to the queue"""
        async with self.lock:
            self.context["active_tasks"][task_id] ={
                **task,
                "created_by": agent_name,
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }

            logger.info(f" {task_id} by {agent_name}")
    
    async def complete_task(self, task_id: str):
        """Mark as complete tasks"""
        async with self.lock:
            if task_id in self.context["active_tasks"]:
                task = self.context["active_tasks"].pop(task_id)
                task["completed_at"] = datetime.now().isoformat()
                task["status"] = "completed"
                self.context["completed_tasks"][task_id] =task
    
    async def reset(self):
        """Reset Daily metrics"""
        now = datetime.now()
        last_reset = self.context["last_reset"]

        if isinstance(last_reset, str):
            last_reset = parser.parse(last_reset)

        # Reset if its a new day
        if now.date() > last_reset.date():
            self.context["global_metrics"] = {
                "jobs_scraped_today": 0,
                "matches_created_today": 0,
                "reports_generated_today": 0
            }

            self.context["last_reset"] = now
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

        self.metrics = {
            "task_completed": 0,
            "task_failed": 0,
            "last_run": None,
        }

    async def perceive(self) -> Optional[Dict]:
        raise NotImplementedError

    async def decide(self, perception: Dict) -> Dict:
        raise NotImplementedError

    async def act(self, decision: Dict) -> Dict:
        raise NotImplementedError

    async def learn(self, result: Dict):
        """Learn from results using episodic memory"""
        # Get past experiences
        similar_exp = self.episodic_memory.get_similar_experiences(
            self.name, 
            result.get("action", "unknown"),
            limit=5
        )
        
        # Calculate improvement
        if similar_exp:
            avg_past_success = sum(1 for e in similar_exp if e["success"]) / len(similar_exp)
            current_success = result.get("status") == "success"
            
            if current_success and avg_past_success < 0.5:
                logger.info(f"🎓 {self.name} is improving! Success rate increasing.")
            elif not current_success and avg_past_success > 0.8:
                logger.warning(f" {self.name} performance degrading. Analyzing...")
                learnings = self.episodic_memory.learn_from_failures(self.name)
                logger.info(f" Learnings: {learnings.get('recommendations', [])}")

    async def run_cycle(self):
        """Complete perception → decision → action → learning"""

        try:
            logger.info(f"{self.name}: Starting cycle")
            
            # Update agent state in shared context
            await self.shared_context.set_agent_state(self.name, {
                "status": "running",
                "phase": "perceive"
            })

            # 1. PERCEIVE (with context)
            perception = await self.perceive()
            if not perception or not perception.get("has_work"):
                logger.info(f"{self.name}: No work detected")
                await self.shared_context.set_agent_state(self.name, {
                    "status": "idle"
                })
                return {"status": "idle"}

            # 2. DECIDE (with episodic memory)
            await self.shared_context.set_agent_state(self.name, {
                "status": "running",
                "phase": "decide"
            })
            decision = await self.decide(perception)
            
            if decision.get("action") == "skip":
                logger.info(f"{self.name} decided to skip")
                return {"status": "skipped"}

            # 3. ACT
            await self.shared_context.set_agent_state(self.name, {
                "status": "running",
                "phase": "act"
            })
            result = await self.act(decision)
            
            # Record experience
            self.episodic_memory.record_experiences(
                agent_name=self.name,
                action=decision.get("action", "unknown"),
                result=result,
                context=perception
            )

            # 4. LEARN
            await self.learn(result)

            # 5. UPDATE METRICS
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
            
            # Record failure
            self.episodic_memory.record_experiences(
                agent_name=self.name,
                action="unknown",
                result={"status": "error", "error": str(e)},
                context={}
            )
            
            return {"status": "error", "error": str(e)}
    
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
    

# ENHANCED AGENTS WITH INTEGRATION
class JobScraperAgent(BaseAutonomousAgent):
    """Monitors job platforms & scrapes new jobs - INTEGRATED"""

    def __init__(self, agent_app, memory, episodic_memory, shared_context, guardrails):
        super().__init__("JobScraperAgent", agent_app, memory, episodic_memory, shared_context, guardrails)
        self.scrape_interval = 300  # 30 minutes

    async def perceive(self):
        try:
            # Check both preferences AND shared context
            prefs = self.memory.preferences_collection.get()
            
            # Also check if main workflow just created new resume
            agent_states = await self.shared_context.read("agent_states")
            
            keywords_all = set()

            # Get keywords from preferences
            if prefs and prefs.get("ids"):
                for metadata in prefs.get("metadatas", []):
                    kw = metadata.get("job_keywords") or metadata.get("keywords") or ""
                    
                    if isinstance(kw, str):
                        # Handle multiple separators
                        keywords = [k.strip() for k in kw.replace(".", ",").split(",") if k.strip()]
                        keywords_all.update(keywords[:3])
                    elif isinstance(kw, list):
                        keywords_all.update(kw[:3])
            
            if not keywords_all:
                logger.warning("JobScraper: No keywords found")
                return {"has_work": False}

            logger.info(f"JobScraper: Found {len(keywords_all)} unique keywords")
            return {
                "has_work": True,
                "keywords": list(keywords_all)[:10],
            }

        except Exception as e:
            logger.error(f"JobScraper perception error: {e}", exc_info=True)
            return {"has_work": False}

    async def decide(self, perception):
        # Check episodic memory for success rate
        success_rate = self.episodic_memory.get_success_rate(self.name, "scrape")
        
        last = self.metrics.get("last_run")
        if last:
            last_t = parser.parse(last)
            time_since = (datetime.now() - last_t).total_seconds()

            if time_since < self.scrape_interval:
                return {"action": "skip", "reason": "too_soon"}

        return {
            "action": "scrape", 
            "keywords": perception["keywords"],
            "expected_success_rate": success_rate
        }

    async def act(self, decision):
        from backend.agent.scraper_engine import IntelligentJobScraper

        keywords = decision["keywords"]
        all_jobs = []

        # Guardrails: Check if we are allowed to proceed with job fetching
        can_proceed, reason = await self.guardrails.check_can_proceed(
            "fetched_jobs",
            {"keywords_count": len(decision["keywords"])}
        )

        if not can_proceed:
            logger.warning(f"Guardrails BLOCKED: {reason}")
            return {"status": "BLOCKED", "reason": reason, "action": "scrape"}

        # Acquire task slot to avoid over-concurrency
        if not await self.guardrails.acquire_task_slot():
            logger.warning("Guardrails blocked: MAX TASK CONCURRENT")
            return {"status": "BLOCKED", "reason": "MAX TASK CONCURRENT", "action": "scrape"}

        try:
            async with IntelligentJobScraper() as scraper:
                for kw in keywords[:5]:
                    try:
                        jobs = await scraper.scrape_all_sources(
                            keywords=[kw],
                            location="Remote",
                            max_results=25,
                        )
                        all_jobs.extend(jobs)
                        logger.info(f"Scraped {len(jobs)} jobs for '{kw}'")

                    except Exception as e:
                        logger.error(f"Failed scraping '{kw}': {e}")

            if all_jobs:
                stored_count = await self.memory.store_jobs(
                    jobs=all_jobs,
                    search_context={
                        "source": "autonomous_scraper",
                        "time": datetime.now().isoformat()
                    },
                )
                logger.info(f"📦 Stored {stored_count} new jobs")

                # Guardrails: Record fetch action
                await self.guardrails.record_action("fetched_jobs")

                # Update shared metrics
                await self.shared_context.update_metrics("jobs_scraped_today", stored_count)

                return {
                    "status": "success",
                    "jobs_scraped": len(all_jobs),
                    "action": "scrape"
                }

            return {
                "status": "no_jobs_found",
                "jobs_scraped": 0,
                "action": "scrape"
            }

        finally:
            # Always release guardrail task slot
            await self.guardrails.release_task()



class ResumeMatcherAgent(BaseAutonomousAgent):
    """Matches incoming jobs with stored resumes - ENHANCED"""

    def __init__(self, agent_app, memory, episodic_memory, shared_context, guardrails):
        super().__init__("ResumeMatcherAgent", agent_app, memory, episodic_memory, shared_context, guardrails)
        self.match_threshold = 0.40
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    async def perceive(self):
        try:
            jobs = self.memory.job_collection.get()
            if not jobs or not jobs.get("ids"):
                return {"has_work": False}

            resumes = self.memory.resume_collection.get()
            if not resumes or not resumes.get("ids"):
                return {"has_work": False}

            logger.info(f"ResumeMatcher: {len(jobs['ids'])} jobs, {len(resumes['ids'])} resumes")
            
            return {
                "has_work": True,
                "job_count": len(jobs["ids"]),
                "resume_count": len(resumes["ids"]),
            }

        except Exception as e:
            logger.error(f"ResumeMatcher perception error: {e}", exc_info=True)
            return {"has_work": False}

    async def decide(self, perception):
        # Learn from past matching performance
        success_rate = self.episodic_memory.get_success_rate(self.name, "match")
        
        # Adjust threshold based on performance
        adjusted_threshold = self.match_threshold
        if success_rate > 0.8:
            adjusted_threshold = min(0.5, self.match_threshold + 0.05)  
        elif success_rate < 0.3:
            adjusted_threshold = max(0.35, self.match_threshold - 0.05)  # Lower bar if struggling
        
        return {
            "action": "match",
            "job_count": perception["job_count"],
            "resume_count": perception["resume_count"],
            "threshold": adjusted_threshold
        }

    async def act(self, decision):
        try:
            jobs = self.memory.job_collection.get(limit=50)
            resumes = self.memory.resume_collection.get()

            # Validate data
            if not jobs or not jobs.get("ids") or not jobs.get("metadatas"):
                logger.warning("ResumeMatcher: No jobs available")
                return {"status": "success", "matches_created": 0, "action": "match"}

            if not resumes or not resumes.get("ids") or not resumes.get("documents"):
                logger.warning("ResumeMatcher: No resumes available")
                return {"status": "success", "matches_created": 0, "action": "match"}

            # Clean job texts
            job_texts = []
            for m in jobs["metadatas"]:
                title = m.get('title', '')
                desc = m.get('description', '')
                text = f"{title} {desc}".strip()
                if not text:
                    text = "No description available"
                job_texts.append(text)

            if not job_texts:
                return {"status": "success", "matches_created": 0, "action": "match"}

            job_emb = self.model.encode(job_texts)
            matches_created = 0
            threshold = decision.get("threshold", self.match_threshold)

            for idx, resume_id in enumerate(resumes["ids"]):
                try:
                    resume_text = resumes["documents"][idx]
                    
                    if not resume_text or not resume_text.strip():
                        continue

                    resume_emb = self.model.encode([resume_text])[0]

                    # Cosine similarity
                    job_norms = np.linalg.norm(job_emb, axis=1)
                    resume_norm = np.linalg.norm(resume_emb)
                    
                    if resume_norm == 0 or np.any(job_norms == 0):
                        continue

                    sim = np.dot(job_emb, resume_emb) / (job_norms * resume_norm)

                    # Get top matches
                    top_idx = np.argsort(sim)[-5:][::-1]

                    for j in top_idx:
                        if sim[j] >= threshold:
                            user_id_clean = resumes['metadatas'][idx].get("user_id", "")
                            await self.memory.store_successful_match(
                                user_id=user_id_clean,
                                resume_id=resume_id,
                                job={"id": jobs["ids"][j], **jobs["metadatas"][j]},
                                match_score= float(sim[j]),
                                user_action="auto_created"
                            )
                            matches_created += 1

                except Exception as e:
                    logger.error(f"ResumeMatcher: Error matching {resume_id}: {e}")
                    continue

            logger.info(f" Created {matches_created} matches")
            
            # Update shared metrics
            await self.shared_context.update_metrics("matches_created_today", matches_created)

            return {
                "status": "success", 
                "matches_created": matches_created,
                "action": "match"
            }

        except Exception as e:
            logger.error(f"ResumeMatcher act error: {e}", exc_info=True)
            return {"status": "error", "error": str(e), "action": "match"}


class ReportGeneratorAgent(BaseAutonomousAgent):
    """Generate Jobs report for user with Nodes"""
    def __init__(self, agent_app, memory, episodic_memory, shared_context, guardrails):
        super().__init__("ReportGeneratorAgent", agent_app, memory, episodic_memory, shared_context, guardrails)
        self.threshold = 1
        self._nodes_cache = None

        self.reports_dir = os.getenv("REPORTS_dir", "reports" )

    @property
    def nodes(self):
        """Lazy nodes - when first succeed"""
        if self._nodes_cache is None:
            if hasattr(self.agent_app, 'agent_graph') and self.agent_app.agent_graph:
                if hasattr(self.agent_app.agent_graph, 'nodes'):
                    self._nodes_cache = self.agent_app.agent_graph.nodes
                    logger.info("Report Generator agent Successfully loaded agent nodes")
                else:
                    logger.error("Agent graph  exists but noo nodes are loaded")
            else:
                logger.warning("agent graph not available while accessing nodes")
        return self._nodes_cache
    
    def link_nodes(self, agent_graph):
        """Explicity link to agent_graph after its initialization"""
        if hasattr(agent_graph, 'nodes'):
            self._nodes_cache = self.agent_graph.nodes
            logger.info("ReportGeneratorAgent: linked to agent_graph.nodes")
        else:
            logger.error("Provided agent_graph has no nodes")
    
    async def perceive(self):
        try:
            prefs = self.memory.preferences_collection.get()
            if not prefs or not prefs.get("ids"):
                logger.info("ReportGen: No Prefrence Found")
                return {"has_work": False}
        
            users =  []
            for uid in prefs["ids"]:
                uclean = uid.replcae("pref_", "")
                matches = self.memory.match_collection.get(
                    where={"user_id": uclean}
                )
                matches_count  = len(matches.get("ids", "") if matches else 0)
                logger.info(f"ReportGen : User {uclean} found {matches_count} matches ({self.threshold})")

                if matches_count >= self.threshold:
                    users.append(uclean)

            if not users:
                logger.info("ReportGen: No users meet threshold")
                return {"has_work": False}

            logger.info(f"ReportGen: Found users {len(users)}")
            return {"has_work": True, "users": users[:5]}
        
        except Exception as e:
            logger.error(f"' ReportGen: Perception {e}", exc_info=True)
            return {"has_work": False}
    
    async def decide(self, perception):
        return {"action": "generate", "users": perception["users"]}
    
    async def act(self, decision):
            count = 0

            for user_id in decision["users"]:
                try:
                    can_proceed, reason = await self.guardrails.check_can_proceed(
                        "report_generation",
                        {"report_size_mb": 10}
                    )

                    if not can_proceed:
                        logger.warning(f"Guardrails BLOCKED {e}")
                        continue

                    found_resume =  None

                    # Founding resume with id
                    canidate_ids = []
                    if user_id.startswith("resume") or user_id.startswith("_resume_"):
                        canidate_ids.append(user_id)

                        canidate_ids.append(user_id.replace("resume", "resume_"))
                        canidate_ids.append(user_id.replace("resume_", ""))

                    
                    # ID looking up
                    for cid in [c for c in canidate_ids if c]:
                        try:
                            r = self.memory.resume_collection.get(ids=[cid], limit=1)
                            if r and r.get("ids"):
                                found_resume = r
                                logger.info(f"ReportGen: found resume by {cid} for user {user_id}")
                                break
                        except Exception:
                            pass
                    
                    # Found resume by metadata
                    if not found_resume:
                        try:
                            r  = self.memory.resume_collection.get(where={"user_id": user_id}, limit=1)
                            if r and r.get("documents"):
                                found_resume = r
                                logger.info(f"ReportGen: Found resume by metadat user_id{user_id}")
                        except Exception:
                            pass
                    
                    ## Still not found skipped it
                    if not found_resume:
                        logger.info(f"ReportGen: No resume found for {user_id}")
                        continue

                    resume_text = found_resume["documents"][0]

                    # Fetching matched jobs

                    matches = self.memory.match_collection.get(
                        where={"user_id": user_id}, limit=15
                    )

                    if not matches or not matches.get("metadatas"):
                        logger.warning(f"ReportGen: No matches found for {user_id}")
                        continue
                    








        





class NotificationAgent(BaseAutonomousAgent):
    """Sends email notifications - FIXED"""
    
    def __init__(self, agent_app, memory, episodic_memory, shared_context, guardrails):
        super().__init__("NotificationAgent", agent_app, memory, episodic_memory, shared_context, guardrails)
        self.email_sender = EmailSender()  
        self.sent_reports = set()
        self.reports_dir = os.getenv("REPORTS_DIR", "reports")

    async def perceive(self):  
        try:
            if not os.path.exists(self.reports_dir):
                logger.warning(f"Notification: Reports dir {self.reports_dir} not found")
                return {"has_work": False}

            recent = []
            for f in os.listdir(self.reports_dir):
                if f.startswith("job_report") and f.endswith(".md"):
                    if f in self.sent_reports: 
                        continue

                    path = os.path.join(self.reports_dir, f)
                    
                    
                    if (datetime.now().timestamp() - os.path.getmtime(path)) < 3600:
                        recent.append(f)
            
            if not recent:
                return {"has_work": False}
            
            logger.info(f"Notification: Found {len(recent)} new reports")
            return {"has_work": True, "reports": recent}
        
        except Exception as e:
            logger.error(f"Notification perception error: {e}", exc_info=True)
            return {"has_work": False}
    
    async def decide(self, perception):
        return {"action": "notify", "reports": perception["reports"]}

    async def act(self, decision):
        sent_count = 0

        for filename in decision["reports"]:
            try:
                path = os.path.join(self.reports_dir, filename)

                if not os.path.exists(path):
                    logger.warning(f"Notification: File not found {path}")
                    continue

                
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                if not content.strip():
                    logger.warning(f"Notification: Empty report {filename}")
                    continue

                # Extract user ID
                parts = filename.replace(".md", "").split("_")
                user_id = parts[2] if len(parts) > 2 else "unknown"

                
                if self.email_sender.send_report(
                    to_email=None,  # Get from preferences
                    subject=f"New Job Matches - {datetime.now().strftime('%Y-%m-%d')}",
                    body=content
                ):
                    sent_count += 1
                    self.sent_reports.add(filename)
                    logger.info(f" Sent notification for {filename}")
            
            except Exception as e:
                logger.error(f"Notification error {filename}: {e}", exc_info=True)
        
        logger.info(f"Notification: Sent {sent_count} notifications")
        return {"status": "success", "notifications_sent": sent_count, "action": "notify"}


class MemoryMaintenanceAgent(BaseAutonomousAgent):
    """Maintains RAG memory system - FIXED"""
    
    def __init__(self, agent_app, memory, episodic_memory, shared_context, guardrails):
        super().__init__("MemoryMaintenanceAgent", agent_app, memory, episodic_memory, shared_context, guardrails)
        self.interval = 86400  # 24 hours
        self.job_retention_days = 30
        self.match_retention_days = 90

    async def perceive(self):  
        last = self.metrics.get("last_run")
        if not last:
            logger.info("MemoryMaintenance: First run")
            return {"has_work": True}
        
        last_t = parser.parse(last)
        if (datetime.now() - last_t).total_seconds() > self.interval:
            logger.info("MemoryMaintenance: Interval reached")
            return {"has_work": True}
        
        return {"has_work": False}

    async def decide(self, perception):
        return {"action": "maintain"}

    async def act(self, decision):
        tasks_completed = []

        # 1. Clean old jobs
        try:
            cutoff = datetime.now().timestamp() - (self.job_retention_days * 86400)
            
            jobs = self.memory.job_collection.get()
            if jobs and jobs.get("ids"):
                old_jobs = []
                for idx, job_id in enumerate(jobs["ids"]):
                    metadata = jobs["metadatas"][idx]
                    created = metadata.get("created_at", datetime.now().timestamp())
                    
                    if isinstance(created, str):
                        created = parser.parse(created).timestamp()
                    
                    if created < cutoff:
                        old_jobs.append(job_id)
                
                if old_jobs:
                    self.memory.job_collection.delete(ids=old_jobs)
                    logger.info(f"MemoryMaintenance: Deleted {len(old_jobs)} old jobs")
                    tasks_completed.append(f"clean_old_jobs:{len(old_jobs)}")
        except Exception as e:
            logger.error(f"MemoryMaintenance: Failed to clean jobs: {e}")
        
        # 2. Clean old matches
        try:
            cutoff = datetime.now().timestamp() - (self.match_retention_days * 86400) 
            
            matches = self.memory.match_collection.get()
            if matches and matches.get("ids"):
                old_matches = []
                for idx, match_id in enumerate(matches["ids"]):
                    metadata = matches["metadatas"][idx]
                    created = metadata.get("created_at", datetime.now().timestamp())
                    
                    if isinstance(created, str):
                        created = parser.parse(created).timestamp()
                    
                    if created < cutoff:
                        old_matches.append(match_id)
                
                if old_matches:
                    self.memory.match_collection.delete(ids=old_matches)
                    logger.info(f"MemoryMaintenance: Deleted {len(old_matches)} old matches")
                    tasks_completed.append(f"clean_old_matches:{len(old_matches)}")
        except Exception as e:
            logger.error(f"MemoryMaintenance: Failed to clean matches: {e}")

        # 3. Optimize collections
        try:
            job_count = len(self.memory.job_collection.get().get("ids", []))
            resume_count = len(self.memory.resume_collection.get().get("ids", []))
            match_count = len(self.memory.match_collection.get().get("ids", []))
            
            logger.info(f"MemoryMaintenance: Stats - Jobs:{job_count}, Resumes:{resume_count}, Matches:{match_count}")
            tasks_completed.append("collection_stats")
        except Exception as e:
            logger.error(f"MemoryMaintenance: Failed to get stats: {e}")
        
        logger.info(f"MemoryMaintenance: Completed {len(tasks_completed)} tasks")
        return {"status": "success", "tasks_completed": tasks_completed, "action": "maintain"}
    



    












        



            










        





































        






    
