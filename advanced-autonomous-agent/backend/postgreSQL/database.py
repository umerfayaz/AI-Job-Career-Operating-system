from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, update, desc, distinct
from datetime import timedelta, datetime, UTC
from backend.postgreSQL.engine import AsyncSessionLocal
from backend.postgreSQL.models import AgentState
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
from backend.postgreSQL.models import User
from backend.postgreSQL.models import Job
from backend.postgreSQL.models import ReportHistory
from backend.postgreSQL.models import EmailHistory
from backend.postgreSQL.models import ResumeHistory
from bs4 import BeautifulSoup
from email.header import decode_header
from langchain_groq import ChatGroq
from typing import Dict, List
import structlog
import email
import imaplib
import asyncio
import json
import re


logger = structlog.get_logger()

class PostgresDatabase:

    def __init__(self, email_config: Dict= None, llm=None):
        self.llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
        self.email_config = email_config

    
    async def update_job(self, job: Dict):

        try:
            async with AsyncSessionLocal() as session:
                stmt = insert(Job).values(**job)

                stmt = stmt.on_conflict_do_update(
                    index_elements=["job_id", "user_id"],
                    set_={
                        "job": stmt.excluded.job,
                        "user_id": stmt.excluded.user_id,
                        "company": stmt.excluded.company,
                        "status": stmt.excluded.status,
                        "applied_at": stmt.excluded.applied_at,
                        "outcome_at": stmt.excluded.outcome_at,
                        "source": stmt.excluded.source,
                        "resume_version": stmt.excluded.resume_version,
                        "last_email_check": stmt.excluded.last_email_check,
                        "message_id": stmt.excluded.message_id,
                        "clicked_at": stmt.excluded.clicked_at,
                        "no_response_notified": stmt.excluded.no_response_notified,
                        "dead_application_notified": stmt.excluded.dead_application_notified,
                        "rejected_notified": stmt.excluded.rejected_notified,
                        "interview_notified": stmt.excluded.interview_notified,
                        "last_followup_at": stmt.excluded.last_followup_at,
                        "followup_count": stmt.excluded.followup_count,
                    }
                )

                await session.execute(stmt)
                await session.commit()
        
        except Exception as e:
            logger.error(
                "Failed to update jon inside update job",
                error= str(e),
                exc_info=True
            )


    async def track_application(self, job_id:str, user_id:str, job_metadata: Dict | None):

        try:
            async with AsyncSessionLocal() as session:
                existing = await session.execute(
                    select(Job).where(
                        Job.job_id == job_id,
                        Job.user_id == user_id
                    )
                )

                existing_job = existing.scalar_one_or_none()

                if existing_job:
                    logger.info(
                        f"Application already tracked: {job_id}"
                    )
                    return False

                if job_metadata:
                    job_record = {
                        "job_id": job_id,
                        "user_id": user_id,
                        "job": job_metadata.get("job_title", "Unknown"),
                        "company": job_metadata.get("company", "Unknown"),
                        "status": "applied",
                        "applied_at": datetime.now(UTC),
                        "outcome_at": None,
                        "source": "workflow_report",
                        "resume_version": job_metadata.get("resume_id", "v1"),
                        "last_email_check": None,
                        "message_id": None,
                        "clicked_at": datetime.now(UTC),
                        "no_response_notified": False,
                        "dead_application_notified": False,
                        "rejected_notified": False,
                        "interview_notified": False,
                        "last_followup_at": datetime.now(UTC),
                        "followup_count": 0,
                    }

                else:
                    job_record = {
                        "job_id": job_id,
                        "user_id": user_id,
                        "job": "Unknown",
                        "company": "Unknown",
                        "status": "applied",
                        "applied_at": datetime.now(UTC),
                        "outcome_at": datetime.now(UTC),
                        "source": "workflow_report",
                        "resume_version": "v1",
                        "last_email_check": datetime.now(UTC),
                        "message_id": None,
                        "clicked_at": datetime.now(UTC),
                        "no_response_notified": False,
                        "dead_application_notified": False,
                        "rejected_notified": False,
                        "interview_notified": False,
                        "last_followup_at": datetime.now(UTC),
                        "followup_count": 0,
                    }

        
                stmt = insert(Job).values(**job_record)

                stmt = stmt.on_conflict_do_update(
                    index_elements=["job_id", "user_id"],
                    set_={
                        "job": stmt.excluded.job,
                        "company": stmt.excluded.company,
                        "status": stmt.excluded.status,
                        "applied_at": stmt.excluded.applied_at,
                        "outcome_at": stmt.excluded.outcome_at,
                        "source": stmt.excluded.source,
                        "resume_version": stmt.excluded.resume_version,
                        "last_email_check": stmt.excluded.last_email_check,
                        "message_id": stmt.excluded.message_id,
                        "clicked_at": stmt.excluded.clicked_at,
                        "no_response_notified": stmt.excluded.no_response_notified,
                        "dead_application_notified": stmt.excluded.dead_application_notified,
                        "rejected_notified": stmt.excluded.rejected_notified,
                        "interview_notified": stmt.excluded.interview_notified,
                        "last_followup_at": stmt.excluded.last_followup_at,
                        "followup_count": stmt.excluded.followup_count,
                    },
                )
     
                await session.execute(stmt)
                await session.commit()

            logger.info(f"Application tracked successfully: {job_id}")
            return True

        except Exception as e:
            logger.error("track_application failed", error=str(e), exc_info=True) 
    
    async def get_applied_jobs(self, user_id: str| None = None, limit: int = 50, offset: int = 0):
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Job)
                if user_id:
                    stmt = stmt.where(Job.user_id == user_id)
                stmt = stmt.limit(limit).offset(offset)

                result = await session.execute(stmt)
                rows = result.scalars().all()

                jobs = []
                for r in rows:
                    jobs.append({
                        "job_id": r.job_id,
                        "job": r.job or "Unknown",
                        "user_id": r.user_id or "Unknown",
                        "company": r.company or "Unknown",
                        "status": r.status,
                        "applied_at": r.applied_at,
                        "outcome_at": r.outcome_at,
                        "source": r.source,
                        "resume_version": r.resume_version or "v1",
                        "last_email_check": r.last_email_check,
                        "message_id": r.message_id,
                        "clicked_at": r.clicked_at,
                        "no_response_notified": r.no_response_notified,
                        "dead_application_notified": r.dead_application_notified,
                        "last_followup_at": r.last_followup_at,
                        "followup_count": r.followup_count,
                    })
                return jobs
        except Exception as e:
            logger.error("get_applied_jobs failed", error=str(e), exc_info=True)
            return []
    
    async def get_agent_state(self, user_id: str):
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(AgentState).where(AgentState.user_id == user_id)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()

                if not row:
                    return None

                return {
                    "last_metrics": row.last_metrics,
                    "last_refetch_at": row.last_refetch_at,
                    "cooldown_until": row.cooldown_until,
                    "last_run_id": row.last_run_id,
                }
        except Exception as e:
            logger.error(
                "Failed to fetch agent state",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            return None
    
    async def update_agent_state(self, user_id: str, data: dict):
        try:
            record_state = {
                "user_id": user_id,
                "last_metrics": data.get("last_metrics"),
                "last_refetch_at": data.get("last_refetch_at"),
                "cooldown_until": data.get("cooldown_until"),
                "last_run_id": data.get("last_run_id"),
                "updated_at": datetime.now(UTC),
            }

            stmt = insert(AgentState).values(**record_state)
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "last_metrics": stmt.excluded.last_metrics,
                    "last_refetch_at": stmt.excluded.last_refetch_at,
                    "cooldown_until": stmt.excluded.cooldown_until,
                    "last_run_id": stmt.excluded.last_run_id,
                    "updated_at": stmt.excluded.updated_at,
                },
            )

            async with AsyncSessionLocal() as session:
                await session.execute(stmt)
                await session.commit()

            logger.info("AgentState updated", user_id=user_id)
        except Exception as e:
            logger.error(
                "Session failed to update inside update agent",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
    
    async def get_user_by_email(self, email: str):

        try:
            async with AsyncSessionLocal() as session:
                stmt = select(User).where(
                    User.email == email
                )

                result = await session.execute(stmt)

                user = result.scalar_one_or_none()

                if not user:
                    return None
                
                return user
        
        except Exception as e:
            logger.error(
                "Failed to get user email inside post db",
                error= str(e),
                exc_info=True
            )

            return None


    async def fetch_new_jobs_from_email(self):
        """Fetch ONLY NEW job-related emails from Gmail and update DB."""
        logger.info("Fetching new job applications from Gmail...")
        try:
            imap = imaplib.IMAP4_SSL(self.email_config["imap_server"])
            imap.login(self.email_config["email"], self.email_config["password"])
            imap.select(self.email_config.get("folder", "INBOX"))

            status, msgs = imap.search(None, "UNSEEN")

            if status != "OK" or not msgs[0]:
                logger.info("No new emails found")
                imap.logout()
                return

            all_message_nums = msgs[0].split()
            logger.info(f"Found {len(all_message_nums)} unseen emails to process")

            processed_count = 0

            for num in all_message_nums:
                try:
                    _, data = imap.fetch(num, "(RFC822)")
                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    sender = msg.get("From", "").lower()

                    SKIP_SENDERS = [
                        "noreply@", "no-reply@", "marketing@", "newsletter@",
                        "facebook", "twitter", "linkedin notifications",
                        "instagram", "youtube", "github",
                    ]
                    if any(skip in sender for skip in SKIP_SENDERS):
                        logger.debug(f"Skipping non-job email from: {sender}")
                        continue

                    decoded = decode_header(msg.get("subject", ""))
                    subject_parts = []
                    for part in decoded:
                        if isinstance(part, tuple):
                            text_part, enc = part[0], part[1] if len(part) > 1 else None
                        else:
                            text_part, enc = part, None
                        if isinstance(text_part, bytes):
                            subject_parts.append(text_part.decode(enc or "utf-8", errors="ignore"))
                        else:
                            subject_parts.append(str(text_part))
                    subject = "".join(subject_parts)

                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if (
                                part.get_content_type() == "text/plain"
                                and "attachment" not in str(part.get("Content-Disposition"))
                            ):
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body = payload.decode("utf-8", errors="ignore")
                                break
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="ignore")

                    body = BeautifulSoup(body, "html.parser").get_text()
                    text = f"{subject} {body}".lower()

                    JOB_KEYWORDS = [
                        "interview", "application", "shortlisted", "assessment",
                        "thank you for applying", "regret", "not moving forward",
                        "next step", "position", "role", "job", "career",
                        "recruiter", "hiring", "offer", "unfortunately",
                    ]
                    if not any(k in text for k in JOB_KEYWORDS):
                        logger.debug(f"Skipping: No job intent in '{subject[:50]}'")
                        continue

                    if not any(w in text for w in ["job", "position", "role", "career", "opportunity"]):
                        logger.debug(f"Skipping: No job-related terms in '{subject[:50]}'")
                        continue

                    msg_id = msg.get("Message-ID")
                    if msg_id:
                        async with AsyncSessionLocal() as session:
                            result = await session.execute(
                                select(Job).where(Job.message_id == msg_id)
                            )
                            if result.scalar_one_or_none():
                                logger.debug("Skipping already processed email")
                                continue

                    body = body[:3000]
                    subject = subject[:500]

                    job_match = re.search(
                        r"(?i)(?:role|position|job title)\s*[:\-]?\s*(?P<job>[\w\s]+)", body
                    )
                    company_match = re.search(
                        r"(?i)(?:company|organization|at)\s*[:\-]?\s*(?P<company>[\w\s]+)", body
                    )

                    job_info = {
                        "company": company_match.group("company").strip() if company_match else None,
                        "job": job_match.group("job").strip() if job_match else None,
                        "location": "N/A",
                    }

                    if not job_info.get("company") or not job_info.get("job"):
                        prompt = f"""
Extract job application details from this email.
Return ONLY valid JSON, no explanations.

Subject: {subject}
Body: {body}

Format:
{{
"company": "company name or Unknown",
"job": "job title or Unknown",
"location": "location or N/A"
}}
"""
                        response = await self.llm.ainvoke(prompt)
                        try:
                            raw = response.content.strip()
                            if "```json" in raw:
                                raw = raw.split("```json")[1].split("```")[0]
                            elif "```" in raw:
                                raw = raw.split("```")[1].split("```")[0]
                            llm_info = json.loads(raw)
                            if isinstance(llm_info, list):
                                llm_info = llm_info[0] if llm_info else {}
                            for k in ["company", "job", "location"]:
                                if not job_info.get(k):
                                    job_info[k] = llm_info.get(k, "Unknown")
                        except Exception as e:
                            logger.error(f"Failed to parse LLM job info: {e}")
                            job_info["company"] = "Unknown"
                            job_info["job"] = "Unknown"

                    REJECTION_KEYWORDS = [
                        "regret", "unfortunately", "not moving forward",
                        "rejected", "not selected", "decided to proceed with other candidates",
                    ]
                    INTERVIEW_KEYWORDS = [
                        "interview", "next step", "schedule", "assessment",
                        "shortlisted", "moving forward", "next round",
                    ]

                    new_status = "applied"
                    if any(k in text for k in REJECTION_KEYWORDS):
                        new_status = "rejected"
                    elif any(k in text for k in INTERVIEW_KEYWORDS):
                        new_status = "interview"

                    async with AsyncSessionLocal() as session:
                        result = await session.execute(
                            select(Job).where(
                                Job.company.ilike(job_info["company"]),
                                Job.job.ilike(f"%{job_info['job']}%"),
                            )
                        )
                        existing = result.scalar_one_or_none()

                    if not existing:
                        logger.info(f"No job found for {job_info['company']}, skipping")
                        continue

                    FINAL_STATES = {"rejected", "interview"}

                    if new_status != existing.status and existing.status not in FINAL_STATES:
                        async with AsyncSessionLocal() as session:
                            await session.execute(
                                update(Job)
                                .where(Job.job_id == existing.job_id)
                                .values(
                                    status=new_status,
                                    outcome_at=datetime.now(UTC),
                                    last_email_check=datetime.now(UTC),
                                    message_id=msg_id,
                                )
                            )
                            await session.commit()

                        logger.info(f"Updated {existing.job_id} to {new_status}")
                        processed_count += 1
                        imap.store(num, "+FLAGS", "\\Seen")

                except Exception as e:
                    logger.error(f"Error processing email: {e}")
                    continue

            imap.logout()
            logger.info(
                f"Finished processing {processed_count} job-related emails "
                f"out of {len(all_message_nums)} unseen"
            )

        except Exception as e:
            logger.error(f"Failed to fetch emails: {e}")
 
   
    def fetch_relevant_email_sync(self, job: Dict) -> List:
        """Synchronous IMAP fetch — called via asyncio.to_thread."""
        logger.info("Checking email reply from applied jobs")
 
        imap = imaplib.IMAP4_SSL(self.email_config["imap_server"])
        imap.login(self.email_config["email"], self.email_config["password"])
        imap.select(self.email_config.get("folder", "INBOX"))
 
        since_date = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
 
        company_name = job.get("company", "").replace("Unknown", "")
        job_title = job.get("job", "").replace("Unknown", "")
 
        if not company_name or not job_title:
            logger.debug(f"Skipping email for {job['job_id']}: missing info")
            imap.logout()
            return []
 
        status, messages = imap.search(None, f"(SINCE {since_date})")
        emails = []
 
        for num in messages[0].split():
            _, data = imap.fetch(num, "(RFC822)")
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)
 
            subject, encoding = decode_header(msg["subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding or "utf-8", errors="ignore")
 
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if (
                        part.get_content_type() == "text/plain"
                        and "attachment" not in str(part.get("Content-Disposition"))
                    ):
                        payload = part.get_payload(decode=True)
                        if payload:
                            decoded = payload.decode("utf-8", errors="ignore")
                            if len(decoded) > 50:
                                body = decoded
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")
 
            text = f"{subject} {body}".lower()
            if company_name.lower() in text or job_title.lower() in text:
                emails.append({
                    "subject": subject,
                    "body": body,
                    "from": msg.get("From"),
                    "date": msg.get("Date"),
                })
 
        imap.logout()
        return emails
 
  
    async def check_email_reply(self, job: Dict):
        logger.info("Checking email replies")
 
        try:
            emails = await asyncio.to_thread(self.fetch_relevant_email_sync, job)
 
            company = job.get("company", "")
            role = job.get("job", "")
 
            if not company or not role:
                logger.warning(f"Job missing company/role: {job['job_id']}")
 
            for email_obj in emails:
                prompt = ChatPromptTemplate.from_messages([
                    HumanMessage(
                        content=f"""
You are an AI assistant managing job applications.
 
Given:
Job:
- Company: {company}
- Role: {role}
- Location: {job.get('location')}
 
Email:
Subject: {email_obj['subject']}
Body: {email_obj['body']}
 
Tasks:
1. Does this email relate to this job? (yes/no)
2. If yes, classify the outcome as:
   - interview
   - rejected
   - pending
 
Respond in JSON:
{{
  "related": true/false,
  "status": "interview|rejected|pending"
}}
"""
                    )
                ])
 
                response = await self.llm.ainvoke(prompt.format_messages())
                raw = response.content.strip()
 
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
 
                try:
                    result = json.loads(raw)
                except Exception:
                    logger.error("Invalid JSON from LLM")
                    continue
 
                if not result.get("related"):
                    continue
 
                label = result.get("status", "pending").lower()
                if label not in ["interview", "rejected", "pending"]:
                    label = "pending"
 
                if label != job.get("status"):
                    job["status"] = label
                    job["outcome_at"] = datetime.now(UTC)
                    logger.info(f"{job['job']} updated via email: {label}")
 
            job["last_email_check"] = datetime.now(UTC)
            await self.update_job(job)
            return job["status"]
 
        except Exception as e:
            logger.error(f"Failed to check email for job {job['job_id']}: {e}")
            return None
    
    async def update_last_active(self, email: str):

        try:
            async with AsyncSessionLocal() as session:

                stmt = (update(User).where(
                        User.email == email
                    ).values(
                        last_active=datetime.now(UTC)
                    )
                )

                await session.execute(stmt)

                await session.commit()

                logger.info("Updated last active", email=email)
        
        except Exception as e:
            logger.error(
                "Failed to update last active user",
                error= str(e),
                exc_info=True
            )
    
    async def create_user(self, user_id: str, email: str, name: str, password_hash: str, created_at=None, last_active=None):
        try:
            user_record  = {
                "user_id": user_id,
                "email": email,
                "name": name,
                "password_hash": password_hash,
                "created_at": created_at or datetime.now(UTC),
                "last_active": last_active or datetime.now(UTC)
            }

            stmt = insert(User).values(**user_record)

            stmt = stmt.on_conflict_do_nothing(
                index_elements=["email"]
            )

            async with AsyncSessionLocal() as session:
                await session.execute(stmt)
                await session.commit()

                logger.info("User created successfully", email=email)
        
        except Exception as e:
            logger.error(
                "Failed to create user",
                error=str(e),
                exc_info=True
            )

    
    async def get_jobs_by_user(self, user_id: str, limit: int = 1000) -> List[dict]:

        try:
            async with AsyncSessionLocal() as session:

                stmt = select(Job).where(Job.user_id == user_id).order_by(desc(Job.applied_at)).limit(limit)
                result = await session.execute(stmt)
                rows = result.scalars().all()

                jobs = []

                for row in rows:
                    jobs.append({
                        "job_id": row.job_id,
                        "job": row.job,
                        "user_id": row.user_id,
                        "company": row.company,
                        "status": row.status,
                        "applied_at": row.applied_at,
                        "outcome_at": row.outcome_at,
                        "source": row.source,
                        "resume_version": row.resume_version,
                        "last_email_check": row.last_email_check,
                        "message_id": row.message_id,
                        "clicked_at": row.clicked_at,
                        "no_response_notified": row.no_response_notified,
                        "dead_application_notified": row.dead_application_notified,
                        "rejected_notified": row.rejected_notified,
                        "interview_notified": row.interview_notified,
                        "last_followup_at": row.last_followup_at,
                        "followup_count": row.followup_count,
                    })

                logger.info(
                    "Fetched jobs for user",
                    total_jobs=len(jobs) 
                )

                return jobs
            
        except Exception as e:
            logger.error(
                "Failed to get jobs",
                error= str(e),
                exc_info=True
            )

    async def update_followup_agent_fields(self,job_id: str, user_id: str, last_followup_at: str, followup_count: int ):
        try:

            async with AsyncSessionLocal() as session:
                 stmt = update(Job).where(Job.job_id == job_id, Job.user_id == user_id).values(last_followup_at=last_followup_at, followup_count=followup_count)

                 await session.execute(stmt)
                 await session.commit()

            logger.info("Followup agent fields updated")
        
        except Exception as e:
            logger.error(
                "Failed to update followup agent fields",
                error = str(e),
                exc_info=True
            )

    
    async def marked_job_notified(self, job_id: str, user_id: str, status: str):

        try:
            allowed_status = (
                "no_response",
                "dead_application",
                "rejected",
                "interview"
            )

            if status not in allowed_status:
                return ValueError(f"Invalid status:{status}")
            
            flag_key = f"{status}_notified"

            async with AsyncSessionLocal() as session:
                stmt = (
                    update(Job).where(Job.job_id == job_id, Job.user_id == user_id).values(**{flag_key: True})
                )

                await session.execute(stmt)
                await session.commit()

            logger.info(f"Marked: {job_id} as notified for {status}")
        
        except Exception as e:
            logger.error(
                "Failed to marked notified user ",
                error = str(e),
                exc_info=True
            )
    
    async def get_active_user_ids(self) -> List[str]:

        try:
            async with AsyncSessionLocal() as session:

                stmt =  select(distinct(Job.user_id)).where(Job.user_id.is_not(None)).order_by(Job.user_id)
                result = await session.execute(stmt)
                user_ids = result.scalars().all()

                logger.info(
                    "Fetched user ids",
                    total_users=len(user_ids)
                )
                
                return user_ids
        
        except Exception as e:
            logger.error(
                "Failed to get user by ids",
                error= str(e),
                exc_info=True
            )

            return []
    
    async def get_job_by_id(self, job_id: str, user_id: str):

        try:
            async with AsyncSessionLocal() as session:

                stmt = select(Job).where(
                    Job.job_id == job_id,
                    Job.user_id == user_id
                )

                result = await session.execute(stmt)
                row = result.scalar_one_or_none()

                if not row:
                    return None

                return {
                    "job_id": row.job_id,
                    "job": row.job,
                    "user_id": row.user_id,
                    "company": row.company,
                    "status": row.status,
                    "applied_at": row.applied_at,
                    "outcome_at": row.outcome_at,
                    "source": row.source,
                    "resume_version": row.resume_version,
                    "last_email_check": row.last_email_check,
                    "message_id": row.message_id,
                    "clicked_at": row.clicked_at,
                    "no_response_notified": row.no_response_notified,
                    "dead_application_notified": row.dead_application_notified,
                    "rejected_notified": row.rejected_notified,
                    "interview_notified": row.interview_notified,
                    "last_followup_at": row.last_followup_at,
                    "followup_count": row.followup_count,
                }

        except Exception as e:
            logger.error(
                "Failed to get job by id",
                error=str(e),
                exc_info=True
            )

            return None

    async def get_active_user_id(self, user_id: str):

        try:
            async with AsyncSessionLocal() as session:

                stmt = select(User).where(
                    User.user_id == user_id
                )

                result = await session.execute(stmt)

                user = result.scalar_one_or_none()

                return user
        
        except Exception as e:
            logger.error(
                "Failed to get user",
                error= str(e),
                exc_info=True
            )

            return None


    # Report History for agent reasoning
    async def save_report_history(self, report: dict):
        try:
            record = {
                "user_id": report["user_id"],
                "run_id": report.get("run_id"),
                "report_type": report.get("report_type", "job_match_report"),
                "summary": report["summary"],
                "top_jobs_count": report.get("top_jobs_count", 0),
                "highest_match_score": report.get("highest_match_score"),
                "recommended_actions": report.get("recommended_actions"),
                "email_subject": report.get("email_subject"),
                "sent_to_email": report.get("sent_to_email"),
                "created_at": datetime.now(UTC)
            }

            async with AsyncSessionLocal() as session:
                stmt = insert(ReportHistory).values(**record)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["user_id", "run_id"],
                    set_={
                        "report_type": stmt.excluded.report_type,
                        "summary": stmt.excluded.summary,
                        "top_jobs_count": stmt.excluded.top_jobs_count,
                        "highest_match_score": stmt.excluded.highest_match_score,
                        "recommended_actions": stmt.excluded.recommended_actions,
                        "email_subject": stmt.excluded.email_subject,
                        "sent_to_email": stmt.excluded.sent_to_email,
                        "created_at": stmt.excluded.created_at,
                    },
                )
                await session.execute(stmt)
                await session.commit()
            
            logger.info("Report history saved", user_id=report["user_id"], run_id=report.get("run_id"))
            return {
                "user_id": record["user_id"],
                "run_id": record["run_id"],
                "report_type": record["report_type"]
            }
        
        except Exception as e:
            logger.error("Failed to save report history", error=str(e), exc_info=True)
            return None
    
    async def get_report_history_by_user(self, user_id:str, limit: int =20):
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(ReportHistory).where(ReportHistory.user_id == user_id).order_by(
                    desc(ReportHistory.created_at)).limit(limit)

                result = await session.execute(stmt)
                rows = result.scalars().all()
            
            return [
                {
                    "user_id": row.user_id,
                    "run_id": row.run_id,
                    "report_type": row.report_type,
                    "summary": row.summary,
                    "top_jobs_count": row.top_jobs_count,
                    "highest_match_score": row.highest_match_score,
                    "recommended_actions": row.recommended_actions,
                    "email_subject": row.email_subject,
                    "sent_to_email": row.sent_to_email,
                    "created_at": row.created_at
                }
                for row in rows
            ]

        except Exception as e:
            logger.error("Failed to fetch report history", error=str(e), exc_info=True)
            return []

    
    # Email History for agent reasoning
    async def save_email_history(self, email_record: dict):
        try:
            record = {
                "user_id": email_record["user_id"],
                "run_id": email_record.get("run_id"),
                "email_type": email_record["email_type"],
                "recipient": email_record["recipient"],
                "subject": email_record.get("subject"),
                "status": email_record.get("status", "queued"),
                "provider_message_id": email_record.get("provider_message_id"),
                "error_message": email_record.get("error_message"),
                "metadata_json": email_record.get("metadata_json"),
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC)
            }

            async with AsyncSessionLocal() as session:
                stmt = insert(EmailHistory).values(**record)

                stmt = stmt.on_conflict_do_update(
                    index_elements=["user_id", "run_id", "email_type"],
                    set_={
                        "recipient": stmt.excluded.recipient,
                        "subject": stmt.excluded.subject,
                        "status": stmt.excluded.status,
                        "provider_message_id": stmt.excluded.provider_message_id,
                        "error_message": stmt.excluded.error_message,
                        "metadata_json": stmt.excluded.metadata_json,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )

                await session.execute(stmt)
                await session.commit()

            logger.info(
                "Email history saved",
                user_id=email_record["user_id"],
                run_id=email_record.get("run_id"),
                email_type=email_record["email_type"],
                status=email_record.get("status", "queued"),
            )

            return True
        
        except Exception as e:
            logger.error("Failed to save email history", error=str(e), exc_info=True)
            return False
    
    
    async def get_email_history_by_user(self, user_id: str, limit: int =20):
        try:
            async with AsyncSessionLocal() as session:
                stmt = (
                    select(EmailHistory).where(EmailHistory.user_id == user_id).order_by(
                        desc(EmailHistory.created_at)).limit(limit)
                    )

                result = await session.execute(stmt)
                rows = result.scalars().all()

                return [
                    {
                        "user_id": row.user_id,
                        "run_id": row.run_id,
                        "email_type": row.email_type,
                        "recipient": row.recipient,
                        "subject": row.subject,
                        "status": row.status,
                        "provider_message_id": row.provider_message_id,
                        "error_message": row.error_message,
                        "metadata_json": row.metadata_json,
                        "created_at": row.created_at,
                        "updated_at": row.updated_at
                    }

                    for row in rows
                ]
        
        except Exception as e:
            logger.error("Failed to get user email hisotry", error=str(e), exc_info=True)
            return []
    
    # Resume history for better agent reasoning
    async def save_resume_history(self, resume: dict):
        try:
            record = {
                "user_id": resume["user_id"],
                "run_id": resume["run_id"],
                "resume_version": resume.get("resume_version", "v1"),
                "summary": resume.get("summary"),
                "skills": resume.get("skills"),
                "experience_years": resume.get("experience_years"),
                "source": resume.get("source", "resume_upload"),
                "created_at": datetime.now(UTC),
            }

            async with AsyncSessionLocal() as session:
                stmt = insert(ResumeHistory).values(**record)

                stmt = stmt.on_conflict_do_update(
                    index_elements=["user_id", "run_id"],
                    set_={
                        "resume_version": stmt.excluded.resume_version,
                        "summary": stmt.excluded.summary,
                        "skills": stmt.excluded.skills,
                        "experience_years": stmt.excluded.experience_years,
                        "source": stmt.excluded.source,
                        "created_at": stmt.excluded.created_at,
                    },
                )

                await session.execute(stmt)
                await session.commit()

            logger.info("Resume history saved", user_id=resume["user_id"], run_id=resume["run_id"])
            return True

        except Exception as e:
            logger.error("Failed to save resume history", error=str(e), exc_info=True)
            return False

    async def get_resume_history_by_user(self, user_id: str, limit: int = 10):
        try:
            async with AsyncSessionLocal() as session:
                stmt = (
                    select(ResumeHistory).where(ResumeHistory.user_id == user_id).order_by(
                        desc(ResumeHistory.created_at)
                    ).limit(limit)
                )

                result = await session.execute(stmt)
                rows = result.scalars().all()

            return [
                {
                    "user_id": row.user_id,
                    "run_id": row.run_id,
                    "resume_version": row.resume_version,
                    "summary": row.summary,
                    "skills": row.skills,
                    "experience_years": row.experience_years,
                    "source": row.source,
                    "created_at": row.created_at,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error("Failed to fetch resume history", error=str(e), exc_info=True)
            return []






    
    

            








    




