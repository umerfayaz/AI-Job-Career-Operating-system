import os
import fitz
import docx
import asyncio
import time
import uvicorn
import structlog
from groq import AsyncGroq
from pathlib import Path
from fastapi.responses import RedirectResponse
from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from backend.narration.emitter import AgentEmitter
from threading import Lock
from backend.core.email_verification import( verification_codes, 
    store_unverified_email, 
    send_verification_code, 
    generate_verification_code,
    verify_email_code
)
from backend.config.settings import Settings
from backend.LLMGateway.fallbackmodels import Models
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, Optional
from backend.multiagents.guardrails import JobReportGuardrails
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from backend.application import get_agent_app
from backend.observability.opentelemetry import setup_observability
from backend.core.stage_event import EmitStage
from backend.core.event_bus import get_event_bus 
from backend.postgreSQL.init_db import init_db                  
from backend.core.email_sender import EmailSender
from backend.tools.pdf_generator import PDFGenerator
from backend.redis.redis_memory import redis_client
from backend.auth.auth_routes import get_current_user, decode_token, router as auth_router
from backend.brain_outcomeLoop.profile_resolver import active_search_profile_key
from backend.observability.workflow_metrics import WorkflowMetrics
from  backend.observability.workflow_instance import metrics_collector
from backend.api.admin_endpoints import router as admin_router
from backend.api.user_plan import check_workflow_limit
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
logger = structlog.get_logger()

# Importing Trunstile key
TURNSTILE_SECRET= os.getenv("TURNSTILE_SECRET_KEY")
apply_serializer = URLSafeTimedSerializer(os.getenv("JWT_SECRET_KEY"))


# Global unified application
email_sender = EmailSender()
event_bus = get_event_bus()
guardrails = JobReportGuardrails()
emit_stage = EmitStage()
pdf_generator = PDFGenerator()
pending_workflows: dict = {}
settings = Settings()
workflow_lock = Lock()
router = APIRouter()
active_websocket_connections = {}
models = Models(AsyncGroq(api_key=settings.GROQ_API_KEY))

user_registry = None


# LIFESPAN - Start BOTH Brains Together
async def cleanup_old_workflows():
    while True:
        await asyncio.sleep(300)
        now = datetime.now()

        with workflow_lock:
            expired = [
                task_id for task_id, workflow in pending_workflows.items()
                if (now - workflow["initial_state"]["started_at"]) > timedelta(hours=1)
            ]

            for task_id in expired:
                pending_workflows.pop(task_id, None)
                logger.info(f" Cleaned Expired workflow:{task_id}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info(" STARTING UNIFIED SYSTEM")
    logger.info("=" * 60)

    global user_registry 

    tracer = setup_observability(app)
    app.state.tracer = tracer
    logger.info("Tracer initialized")

    await init_db()

    agent_app = await get_agent_app()
    await agent_app.start_autonomous_system()
    
    asyncio.create_task(cleanup_old_workflows())

    logger.info("=" * 60)
    logger.info(" UNIFIED SYSTEM READY")
    logger.info("   Brain 1 (LangGraph): Ready for API requests")
    logger.info("   Brain 2 (Multi-Agents):  Running 24/7")
    logger.info("   Integration:  Connected")
    logger.info("=" * 60)

    try:
        yield
    finally:
        logger.info(" Shutting down unified system...")
        await agent_app.shutdown()
        logger.info(" Shutdown complete")



app = FastAPI(
    title="Unified Agent API", 
    version="2.0.0",
    description="Dual-brain system: LangGraph + Multi-Agents",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json"
)

app.state.pending_workflows = pending_workflows
app.state.active_websocket_connections = active_websocket_connections
app.state.workflow_lock = workflow_lock
app.state.event_bus = event_bus

# Merging Auth frontend Router with Api file 
app.include_router(auth_router)
app.include_router(admin_router)

app.add_middleware(
    TrustedHostMiddleware,
    allowd_hosts=["autoagent.space", "www.autoagent.space", "localhost", "127.0.0.1"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[

        "https://autoagent.space",
        "https://www.autoagent.space",

        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MODELS
class TaskRequest(BaseModel):
    task: str
    task_id: str
    priority: int = 5
    config: Optional[Dict] = None


class TaskResponse(BaseModel):
    task_id: str
    message: str
    status: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict] = None
    error: Optional[str] = None

# HELPER FUNCTIONS

def extract_text_from_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    text = "".join([page.get_text() for page in doc])
    doc.close()
    return text


def extract_text_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])


def extract_text_from_file(file_path: str, filename: str) -> str:
    if filename.endswith('.pdf'):
        return extract_text_from_pdf(file_path)
    elif filename.endswith('.docx'):
        return extract_text_from_docx(file_path)
    elif filename.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file format: {filename}")

# API Endpoint Specially for tasks stats updates for frontend
@app.get("/api/stats")
async def get_stats(user_id: str = Depends(get_current_user)):

    tasks = await redis_client.get(f"user:{user_id}:tasks_completed")
    jobs = await redis_client.get(f"user:{user_id}:jobs_matched")
    reports = await redis_client.get(f"user:{user_id}:reports_generated") 

    return {
        "tasks_completed": int(tasks) if tasks else 0,
        "jobs_matched": int(jobs) if jobs else 0,
        "reports_generated": int(reports) if reports else 0,
    }


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Unified Agent API - Dual Brain System",
        "version": "2.0.0",
        "brains": {
            "brain_1": "LangGraph (Goal-based workflows)",
            "brain_2": "Multi-Agents (24/7 autonomous)"
        }
    }

@app.get("/apply")
async def apply_jobs(token: str):
    try:
        data = apply_serializer.loads(token, max_age= 60 * 60 * 24 * 30)
        job_id = data["job_id"]
        user_id = data["user_id"]
    except SignatureExpired:
        raise HTTPException(410, "This application Link has expired")
    except BadSignature:
        logger.warning(
            "Invalid applied token recieved"
        )
        raise HTTPException(400, "Inavlid or tapmered link")

    try:
        logger.info(f"Apply endpoint called {job_id} {user_id}")
        with tracer.start_as_current_span("api.job_apply") as span:
            start_apply = time.time()

            agent_app = await get_agent_app()

            # Tracing Job and User IDs
            span.set_attribute("job.id", job_id )
            span.set_attribute("user.id", user_id)

            job = await agent_app.memory.get_job_by_id(job_id, user_id)

            if not job:
                logger.error(f"Job not found {job_id} for {user_id}")
                raise HTTPException(404, "No job found")
            
            metadata = job.get("metadata", {})

            real_job_url = metadata.get("url", "")

            if not real_job_url or real_job_url == None:
                logger.error(f"No url for job {job_id}")
                raise HTTPException(404, "No url found for this job")
            
            await agent_app.multi_agent_orchestrator.outcome_database.track_application(
                job_id=job_id,
                user_id=user_id,
                job_metadata=metadata
            )

            await event_bus.emit({
                "type": "JOB_APPLIED",
                "user_id": user_id,
                "job_id":job_id,
                "job_metadata": metadata,
                "timestamps": datetime.now().isoformat()
            })


            logger.info(f" Redirecting to: {real_job_url}")

            return RedirectResponse(url=real_job_url, status_code=303)
        
    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"apply endpoint error: {e}", exc_info=True)
        span.set_status(Status(StatusCode.ERROR, str(e)))
        raise HTTPException(500, f"Failed to process application{str(e)}")
    finally:
        span.set_attribute("llm.latency_seconds", time.time() - start_apply)


@app.get("/api/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get status of a specific task"""
    return TaskStatusResponse(
        task_id=task_id,
        status="processing",
        result=None
    )

@app.get("/api/test/event-bus-status")
async def test_event_bus_status():
    eb = get_event_bus()
    return {
        "connected_clients": len(eb.connections),
        "queues": [str(q) for q in eb.connections],
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    user_email: Optional[str] = Form(None),
    keywords: Optional[str] = Form(""),
    resume_id: Optional[str] = Form(None),
    location: Optional[str] = Form("Remote"),
    experience_level: Optional[str] = Form("mid"),
):
    """
    Upload resume and trigger automatic job matching + email reports
    """
    try:
        with tracer.start_as_current_span("api.resume_upload") as parent_span:
            start_resume = time.time()

            # Starting workflow after Capctha verification
            agent_app = await get_agent_app()

            # Validate file type
            if not file.filename.endswith(('.pdf', '.docx', '.txt')):
                raise HTTPException(
                    status_code=400,
                    detail="Only PDF, DOCX, and TXT files are supported"
                )
            
             # Wrofklow Limit 
            workflow_usage = await check_workflow_limit(user_id, plan="free")
            
            job_keywords = [k.strip() for k in keywords.split(",") if k.strip()]

            # Rate limiting
            can_proceed, reason = await guardrails.check_can_proceed(
                "fetched_jobs",
                {"keywords_count": len(job_keywords)}
            )

            if not can_proceed:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate Limit: {reason}"
                )

            task_id =f"task_{int(datetime.now().timestamp())}"
            resume_id =f"resume_{task_id}"

            logger.info(f" Received resume: {file.filename}")

            # Save file
            TEMP_DIR = Path("temp")
            TEMP_DIR.mkdir(parents=True, exist_ok=True)

            safe_path = Path(file.filename).name
            file_path = TEMP_DIR / f"{resume_id}_{safe_path}"

            MAX_FILE_SIZE = 30 * 1024 * 1024
            content = await file.read()

            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(400, "File is to large")
            with open(file_path, "wb") as f:
                f.write(content)  
            
            run_id = f"run{resume_id}_{int(datetime.now().timestamp())}"     

            resume_text = extract_text_from_file(file_path, file.filename)
            logger.info(f"   Extracted {len(resume_text)} characters")

            import re

            def normalize_resume_text(text: str) -> str:
                text = text.replace("\n", " ")
                text = text.replace("\r", " ")
                text = re.sub(r"\s+", " ", text)
                return text

            def extract_email_from_resume(text: str):
                text = normalize_resume_text(text)

                pattern = re.compile(
                    r'[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}',
                    re.IGNORECASE
                )

                match = pattern.search(text)
                if not match:
                    return None

                # remove spaces introduced by PDF extraction
                email = re.sub(r"\s+", "", match.group())
                return email

            extracted_email = extract_email_from_resume(resume_text)

            if extracted_email:
                email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_regex, extracted_email):
                    logger.info(f"Invalid email extracted from {extracted_email}")
                    extracted_email =  None
            logger.info(f" Extracted email: {extracted_email if extracted_email else 'None (will use default)'} ")

            if extracted_email:
                verification_code = generate_verification_code()

                await store_unverified_email(
                    task_id = f"{task_id}",
                    email=extracted_email,
                    verification_code=verification_code
                )
                    
                await send_verification_code(extracted_email, verification_code, task_id)

                prompt = f"""
            A user uploaded a resume. 
    The extracted email is: {extracted_email if extracted_email else 'None'}.
    If it's invalid, explain in a friendly, step-by-step way what the user should do next.
    If it's valid, congratulate them and mention that a verification code will be sent.
    Return the message in natural human-like language suitable for chat display.
            """

            with tracer.start_as_current_span("llm.call") as llm_span:
                llm_start = time.time()
                llm_span.set_attribute("llm.model",  "openai/gpt-oss-120b")

                response = await models.text_completion(
                    task_type="cheap_json",
                    messages =[{"role": "user", "content": prompt}]
                )

                MODEL_NAME = response.get("model", "unknown")
                logger.warning(f"Model called inside resume upload: {MODEL_NAME}")

                llm_span.set_attribute("llm.latency_seconds", time.time() - llm_start)

                llm_usage = response.get("usage")

                if llm_usage:
                    llm_span.set_attribute("llm.prompt", prompt[:500])
                    llm_span.set_attribute("llm.prompt_tokens", getattr(llm_usage, "prompt_tokens", 0))
                    llm_span.set_attribute("llm.completion_tokens", getattr(llm_usage, "completion_tokens", 0))
                    llm_span.set_attribute("llm.total_tokens", getattr(llm_usage, "total_tokens", 0))

                    total_tokens = getattr(llm_usage, "total_tokens", 0)
                    MODEL_COSTS = {
                        MODEL_NAME: 0.0001
                    }
                    cost = (total_tokens / 1000) * MODEL_COSTS.get(MODEL_NAME)

                    llm_span.set_attribute("llm.total_estimated_cost_usd", cost)

                narration_messages = response.get("content")

                emitter = AgentEmitter(agent_name="ResumeController", event_bus=event_bus)

                await event_bus.emit(
                    event= {
                    "event_type":"ui.verification.show",
                    "email_detected": extracted_email
                    }
                )
                email_valid = extracted_email is not None

                if not email_valid:
                    await event_bus.emit(
                        event= {
                        "event_type":"ui.chat.show",
                        "message": narration_messages
                        }
                    )   

                await emitter.progress(run_id=task_id, message=narration_messages)


                logger.info(f" Verification code sent to email {extracted_email}")

            final_email = user_email or extracted_email
            
            if not final_email:
                try:
                    os.remove(file_path)
                except:
                    pass
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Email required",
                        "message": "Please provide an email or include it in your resume"
                    }
                )
            
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, final_email):
                try:
                    os.remove(file_path)
                except:
                    pass
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid email format: {final_email}"
                )

            logger.info(f" Email validated: {user_email}")

              # Observability and tracking of uploaded resume 
            parent_span.set_attribute("file.name", file.filename)
            parent_span.set_attribute("resume.user_id", user_id)
            parent_span.set_attribute("resume.run_id", run_id)
            parent_span.set_attribute("resume.job_keywords", len(job_keywords))
            parent_span.set_attribute("resume.user_email", user_email)

            if agent_app.multi_agent_orchestrator:
                await agent_app.multi_agent_orchestrator.shared_context.write(
                    f"current_run_id_{user_id}",
                    run_id,
                    "WorkFlowController"
                )
                logger.warning(f" Current run id created in resume upload endpoint {run_id}")

            # Prepare state
            initial_state = {
                "task": "Find and match job opportunities for uploaded resume",
                "task_type": "job_matching",
                "workflow_type": "frontend_workflow",
                "task_id": task_id,
                "priority": 5,
                "resume_text": resume_text,
                "resume_id": resume_id,
                "job_keywords": job_keywords,
                "job_location": location,
                "experience_level": experience_level,
                "run_id": run_id,
                "user_email": user_email or extracted_email,  
                "user_id": user_id,
                
                "plan": [],
                "current_step": 0,
                "reasoning_history": [],
                "search_queries": [],
                "search_results": [],
                "scraped_content": [],
                "extracted_insights": [],
                "analysis_results": {},
                "relevant_memories": [],
                "entity_context": {},
                "conversation_history": [],
                "confidence_score": 0.0,
                "validation_results": {},
                "errors": [],
                "retry_count": 0,
                "final_output": None,
                "artifacts": [],
                "iteration": 0,
                "max_iteration": 10,
                "started_at": datetime.now(),
                "status": "running",
                "jobs_data": [],
                "matched_jobs": [],
                "quality_check": {},
                "email_status": {},
                "report_data": {},
                "final_report": None,
                "pdf_path": None
            }

            config = {
                "configurable": {"thread_id": task_id}
            }

            with workflow_lock:
                pending_workflows[task_id] = {
                    "initial_state": initial_state,
                    "config": config,
                    "run_id": run_id
                }

            try:
                os.remove(file_path)
            except:
                pass

            await guardrails.record_action("fetched_jobs")

            return {
                "success": True,
                "task_id": task_id,
                "run_id": run_id,
                "message": "Resume uploaded successfully! You'll receive an email report when matching is complete.",
                "email": user_email,
                "email_source": "extracted" if extracted_email else "provided",
                "notification": f"Report will be sent to {user_email}",
                "status_endpoint": f"/task/{task_id}",
                "status": "verification_pending",
                "verification_required": True,
                "usage": workflow_usage,
                "brains_active": {
                    "langgraph": True,
                    "multi_agents": True
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        parent_span.set_status(Status(StatusCode.ERROR, str(e)))
        raise HTTPException(status_code=500, detail="Internal server error. Please Try again later")
    finally:
        parent_span.set_attribute("resume.latency_seconds", time.time() - start_resume)


@app.websocket("/api/ws/events")
async def websockets_events(websocket: WebSocket, token: str = None):
    if not token:
        await websocket.close()
        return
    
    try:
        user_id = await decode_token(token)
    
    except:
        await websocket.close(code=1008)
        return

    client_ip = websocket.client.host if websocket.client else "unknown"
    connection_id = id(websocket)
    
 
    existing_conn_info = active_websocket_connections.get(client_ip)
    if existing_conn_info:
        existing_id = existing_conn_info.get("id")
        existing_ws = existing_conn_info.get("ws")
        last_activity = existing_conn_info.get("timestamp", 0)
        time_since_activity = time.time() - last_activity
    
        if time_since_activity < 30 and existing_id != connection_id:
            logger.warning(f"Rejecting duplicate connection from {client_ip} (existing connection is still active)")
            await websocket.close(code=1008, reason="Another connection already exists")
            return
        else:
   
            logger.info(f"Replacing stale connection from {client_ip} (inactive for {time_since_activity:.1f}s)")
            try:
                await existing_ws.close(code=1000, reason="Replaced by new connection")
            except Exception as close_error:
                logger.debug(f"Error closing stale connection: {close_error}")
            if client_ip in active_websocket_connections:
                del active_websocket_connections[client_ip]
    
    # Accept the new connection
    await websocket.accept()
    active_websocket_connections[client_ip] = {
        "id": connection_id,
        "ws": websocket,
        "timestamp": time.time()
    }
    logger.info(f"WebSocket connected: {client_ip} -> {connection_id} (Total clients: {len(active_websocket_connections)})")
    
    queue = await event_bus.connect()

    try:
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "timestamp": datetime.now().isoformat(),
            "message": "🤖 Connected to AI Career Assistant"
        })
        
        active_websocket_connections[client_ip]["timestamp"] = time.time()

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)  
                
                await websocket.send_json(event)
                active_websocket_connections[client_ip]["timestamp"] = time.time()
                    
            except asyncio.TimeoutError:
        
                try:
                    await websocket.send_json({"type": "ping"})
                    active_websocket_connections[client_ip]["timestamp"] = time.time()
                except Exception:
                    logger.warning(f"Ping failed for {client_ip}, connection likely dead")
                    break
                continue
                
            except Exception as e:
                logger.error(f"Event processing error: {e}")
                break  

    except WebSocketDisconnect:
        logger.info(f"WebSocket Client Disconnected: {connection_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    
    finally:
        conn_info = active_websocket_connections.get(client_ip)
        if conn_info and conn_info.get("id") == connection_id:
            del active_websocket_connections[client_ip]
            logger.info(f"WebSocket cleanup: {client_ip} -> {connection_id} (Remaining clients: {len(active_websocket_connections)})")
        
        await event_bus.disconnect(queue)

@app.post('/api/resume/verify-email')
async def verify_email(task_id: str = Form(...), code: str =Form(...), user_id: str = Depends(get_current_user)):
    logger.warning(f"DEBUG task_id={task_id}, code={code}")

    agent_app = await get_agent_app()

    success, message = verify_email_code(task_id, code)

    if not success:
        return {
            "success": False,
            "error": message
        }
    
    verification_codes[task_id]["verified"] = True
    verified_email = verification_codes[task_id]["email"]

    try:
         existing_prefs = agent_app.memory.preferences_collection.get(ids=[user_id])

         if existing_prefs and existing_prefs.get("ids"):
            existing_meta = existing_prefs["metadatas"][0]
            existing_meta["email_verified"] = True
            existing_meta["verified_at"] = datetime.now().isoformat()

            agent_app.memory.preferences_collection.update(
                ids=[user_id],
                metadatas=[existing_meta]
            )

            logger.info(f"Updated Preferences verified: emails Verified: {user_id}")
         else:
            agent_app.memory.preferences_collection.add(
                ids=[user_id],
                documents=[f" User Preference for {verified_email}"],
                metadatas=[{
                    "user_id": user_id,
                    "email": verified_email,
                    "email_verified": True,
                    "verified_at": datetime.now().isoformat()
                }]
            )
            logger.info(f" Created Preferences: email verified for {user_id}")
    
    except Exception as e:
        logger.info(f"Failed to update preferences {e}", exc_info=True)
    
    workflow = pending_workflows.get(task_id)

    if not workflow:
        logger.error(f" No workflow found for task {user_id}")
        return {
            "success": False,
            "error": "workflow not found or expired"
        } 
    run_id = (
        workflow.get("run_id") or
        workflow["initial_state"].get("run_id")
    )

    if not run_id:
        logger.error(f"No run_id found for task {user_id}")
        return {
            "success": False,
            "error": "Internal run context missing"
        }
    
    logger.warning(f"Email Verified. Starting workflow for {user_id}")

    if agent_app.multi_agent_orchestrator:
         await agent_app.multi_agent_orchestrator.shared_context.write(
            key = f"new_resume_upload_{user_id}",
            value={
                "remaining_cycles": 3,
                "user_id": user_id,
                "email": verified_email,
                "workflow_type": "frontend_workflow",
                "source": "email_verification",
                "timestamp": datetime.now().isoformat()
            },
            agent_name="resume_api"
        )

    config = {
        "configurable": {"thread_id":run_id}
    }

    agent_app.safe_runner.create_task(
        name = f"retry_workflow{user_id}",
        coro = execute_unified_job_matching(
            task_id=task_id,
            initial_state=workflow["initial_state"],
            config=config
        ),
        severity= "critical"
    )


    return {
        "success": True,
        "message": "Email verified Processing Your resume now",
        "task_id": task_id
    }

async def execute_unified_job_matching(task_id: str, initial_state: dict, config: dict):
    """
    Execute job matching using the unified application
    """
    with tracer.start_as_current_span("workflow.execute_matching.execute") as span:
        execute_start = time.time()
        agent_app = None

        try:
            agent_app = await get_agent_app()

            run_id = initial_state.get("run_id")
            resume_id = initial_state.get("resume_id")

            user_id = initial_state.get("user_id")
            logger.warning("Writing active search profile in execute job matching")


            if not run_id:
                logger.warning(f"CRITICAL: No run_id found in initial_state for {task_id}")
                if agent_app.multi_agent_orchestrator:
                    run_id =  await agent_app.multi_agent_orchestrator.shared_context.read(f"current_run_id_{user_id}")

            
            logger.info(f"Starting unified matching workflow {task_id}")
            logger.info(f"Using run_id {run_id}")
                
            if agent_app.multi_agent_orchestrator:
                await agent_app.multi_agent_orchestrator.shared_context.write(
                    f"current_run_id_{user_id}",
                    run_id,
                    "WorkflowExecutor"
            )
            logger.info(f" Confirm run_id in shared_context {run_id}")

            if agent_app.multi_agent_orchestrator:
                verified = await agent_app.multi_agent_orchestrator.shared_context.read(f"current_run_id_{user_id}", )
                if verified != run_id:
                    logger.warning(f" Verification Failed Expected: {run_id} got {verified}")
                else:
                    logger.info(f"Verified run_id in shared context {verified}")         

                profile = {
                    "user_id": user_id,
                    "run_id": run_id,
                    "resume_id": initial_state.get("resume_id"),
                    "resume_text": initial_state.get("resume_text"),
                    "initial_state": initial_state,
                    "autonomous_enabled": True,
                    "config": config,
                    "task_id": task_id,
                    "last_run_id": run_id,
                    "workflow_status": "running",
                    "timestamp": datetime.now().isoformat(),
                    "cooldown_until": None,
                }

                profile_key = active_search_profile_key(run_id)
                await agent_app.multi_agent_orchestrator.shared_context.write(
                    profile_key,
                    profile,
                    "WorkflowExecutor",
                )
            
            workflow_type = initial_state.get("workflow_type", "frontend_workflow")
            if workflow_type == "autonomous_workflow":
                await agent_app.multi_agent_orchestrator.shared_context.pop(
                    f"new_resume_upload_{user_id}"
                )
                logger.warning(f"cleared new resume upload key for autonomous workflow {user_id}")
            
            result = await agent_app.run_langgraph_workflow(initial_state, config)
            
            matches_count = len(result.get('matched_jobs', []))
            if matches_count > 0 and agent_app.multi_agent_orchestrator:
                await agent_app.multi_agent_orchestrator.shared_context.write(
                    f"ResumeMatcherAgent_target_resume",
                    user_id, 
                    "WorkflowExecutor"
                )
            logger.warning(f"Resume matcher agent target_resume_created")
            
            logger.info(f" Unified workflow completed: {task_id}")
            logger.info(f"   Jobs found: {len(result.get('jobs_data', []))}")
            logger.info(f"   Matches: {len(result.get('matched_jobs', []))}")
            logger.info(f"   Confidence: {result.get('confidence_score', 0):.2%}")

            user_email = initial_state.get("user_email")
            job_keywords = initial_state.get("job_keywords", [])
            location = initial_state.get("job_location", "Remote")
            
            if user_email and user_id:
                try:
                    # Check if preferences exist
                    existing_prefs = agent_app.memory.preferences_collection.get(
                        ids=[user_id]
                    )
                    
                    if not existing_prefs or not existing_prefs.get("ids"):
                        
                        agent_app.memory.preferences_collection.add(
                            ids=[user_id],
                            documents=[f"User preferences for {user_email}"],
                            metadatas=[{
                                "user_id": user_id,
                                "email": user_email,  
                                "email_verified": True,
                                "job_keywords": ",".join(job_keywords) if job_keywords else "",
                                "location": location,
                                "resume_id": resume_id,
                                "resume_text": initial_state.get("resume_text"),
                                "run_id": run_id,
                                "created_at": datetime.now().isoformat()
                            }]
                        )
                        logger.info(f"Stored preferences with email: {user_email} (user_id: {user_id})")
                    else:
                        # Update existing preferences with email (in case it was missing)
                        existing_meta = existing_prefs["metadatas"][0]
                        existing_meta["email"] = user_email
                        existing_meta["resume_text"] = initial_state.get("resume_text")
                        existing_meta["email_verified"] = True
                        existing_meta["updated_at"] = datetime.now().isoformat()
                        existing_meta["last_run_id"] = run_id

                        agent_app.memory.preferences_collection.update(
                            ids=[user_id],
                            metadatas=[existing_meta]
                        )
                        logger.info(f" Updated preferences with email: {user_email}")
                    
                    with workflow_lock:
                        pending_workflows.pop(task_id, None)

                except Exception as e:
                    logger.error(f" Failed to store preferences: {e}", exc_info=True)
            else:
                logger.error(f" CRITICAL: Missing email or user_id (email={user_email}, user_id={user_id})")

            try:
                metrics = WorkflowMetrics(
                    workflow_type= initial_state.get("workflow_type", "frontend_workflow"),
                    task_id=task_id,
                    run_id=run_id,
                    status="success",
                    user_id= user_id,
                    latency_ms=(time.time() - execute_start) * 1000,
                    jobs_found=len(result.get("jobs_data", [])),
                    matched_jobs=len(result.get("matched_jobs", [])),
                    confidence_score=result.get("confidence_score", 0),
                    timestamp= time.time()
                )

                await metrics_collector.record_workflow(metrics)
                logger.warning("workflow type in execute metrics:{metrics}")
            
            except Exception as metric_error:
                logger.error(f"Failed to record worflow_metrics:{metric_error}")

                
            return result

        except Exception as e:
            logger.error(f" Unified workflow failed: {task_id} - {e}", exc_info=True)
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            if agent_app is not None and agent_app.cognitive_brain:
                await agent_app.cognitive_brain.autonomous_recovery([{
                    "issue": "langgraph_loop_crash",
                    "severity": "critical",
                    "task_id": task_id,
                    "error": str(e)
                }])

            if agent_app is not None and agent_app.multi_agent_orchestrator:
                profile_key = active_search_profile_key(run_id)

                profile = await agent_app.multi_agent_orchestrator.shared_context.read(profile_key)

                if isinstance(profile, dict):
                    profile["workflow_status"] = "failed"
                    profile["last_failed_at"] = datetime.now().isoformat()
                    profile["last_error"] = str(e)

                    await agent_app.multi_agent_orchestrator.shared_context.write(
                        profile_key,
                        profile,
                        "WorkflowExecutor"
            )
            #  if agent_app is not None and agent_app.multi_agent_orchestrator:
            #     await agent_app.multi_agent_orchestrator.shared_context.write(
            #         f"current_run_id_{user_id}",
            #         run_id,
            #         "WorkflowExecutor"
            #     )

            try:
                metrics =  WorkflowMetrics(
                    workflow_type=initial_state.get("workflow_type", "frontend_workflow"),
                    task_id=task_id,
                    run_id=run_id or "unknown",
                    status="failed",
                    user_id=user_id or "unknown",
                    latency_ms= (time.time() - execute_start) * 1000,
                    jobs_found=0,
                    matched_jobs=0,
                    confidence_score=0.0,
                    timestamp=time.time()
                )

                await metrics_collector.record_workflow(metrics)

                logger.warning(f"Execute unified metrics for lantency:{metrics}")
            
            except Exception as metrics_error:
                logger.error(f"Failed to calculate workflow metrics:{metrics_error}",
                exc_info=True
            )

            raise

        finally:
            try:
                if agent_app is not None and agent_app.multi_agent_orchestrator:
                        if agent_app.multi_agent_orchestrator:
                            profile_key = active_search_profile_key(run_id)
                            profile = await agent_app.multi_agent_orchestrator.shared_context.read(profile_key)
                            if isinstance(profile, dict) and profile.get("workflow_status") == "running":
                                    profile["workflow_status"] = "idle"
                                    profile["last_completed_at"] = datetime.now().isoformat()
                                    await agent_app.multi_agent_orchestrator.shared_context.write(
                                        profile_key,
                                        profile,
                                        "WorkflowExecutor"
                                )
            except Exception as cleanup_error:
                logger.error(
                    f"workflow cleanup failed: {cleanup_error}",
                    exc_info=True
                )

            span.set_attribute("execute.latency_seconds", time.time() - execute_start)

# SYSTEM workflow observability STATUS ENDPOINTS
@app.get("/api/app/system/status")
async def system_state(user_id: str = Depends(get_current_user)):

    user_id = user_id

    frontend_metrics = await metrics_collector.get_recent(
        "frontend_workflow",
        50,
        user_id=user_id
    )

    autonomous_metrics = await metrics_collector.get_recent(
        "autonomous_workflow",
        50,
        user_id=user_id
    )

    def avg_latency(metrics):
        if not metrics:
            return 0

        return sum(m["latency_ms"] for m in metrics) / len(metrics)

    def success_rate(metrics):
        if not metrics:
            return 100

        successful = len(
            [m for m in metrics if m["status"] == "success"]
        )

        return round((successful / len(metrics)) * 100, 2)
    
    def latest_latency(metrics):
        if not metrics:
            return 0
        
        return metrics[0]["latency_ms"]
    
    def fastest_latency(metrics):
        if not metrics:
            return 0
        
        return min(
            m["latency_ms"]
            for m in metrics
        )
    
    def slowest_latency(metrics):
        if not metrics:
            return 0
        
        return max(
            m["latency_ms"]
            for m in metrics
        )

    return {
        "status": "healthy",

        "frontend": {
            "user_id": user_id,
            "name": "Frontend Workflow",
            "avg_latency_ms": avg_latency(frontend_metrics),
            "latest_latency": latest_latency(frontend_metrics),
            "fastest_latency": fastest_latency(frontend_metrics),
            "slowest_latency": slowest_latency(frontend_metrics),
            "runs": len(frontend_metrics),
            "success_rate": success_rate(frontend_metrics),
            "agents": [
                "ResumeMatcherAgent",
                "ReportGeneratorAgent",
                "NotificationAgent"
            ]
        },

        "autonomous": {
            "user_id": user_id,
            "name": "Autonomous Workflow",
            "avg_latency_ms": avg_latency(autonomous_metrics),
            "latest_latency": latest_latency(autonomous_metrics),
            "fastest_latency": fastest_latency(autonomous_metrics),
            "slowest_latency": slowest_latency(autonomous_metrics), 
            "runs": len(autonomous_metrics),
            "success_rate": success_rate(autonomous_metrics),
            "agents": [
                "StrategicAgent",
                "SourceAgent",
                "FollowupAgent"
            ]
        },

        "workflows": {
            "active": len(pending_workflows),
            "total": 2
        },

        "timestamp": datetime.now().isoformat()
    } 
   

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "agentic-backend"}


@router.websocket("/ws/{run_id}")
async def ws_endpoint(ws: WebSocket, run_id: str):
    await ws.accept()

    async for event in event_bus.subscribe():
        await ws.send_json(event)


# ENTRY POINT
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )