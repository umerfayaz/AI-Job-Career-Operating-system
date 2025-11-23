import os
import fitz
import docx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel
from typing import Dict, Optional
import uvicorn
from backend.multiagents.agents_orchestrator import AutonomousOrchestrator
from backend.core.memory_system import MemoryRAGSystem
from backend.core.email_sender import EmailSender
from backend.agent.scraper_engine import IntelligentJobScraper
from backend.tools.pdf_generator import PDFGenerator
import structlog
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import asyncio


# Import your autonomous agent app
from backend.application import AgentApplication

logger = structlog.get_logger()
# Initialize global AgentApplication instance
agent_app = AgentApplication()
email_sender = EmailSender()
pdf_generator = PDFGenerator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""

    print("starting Apllication")

    # Initiallize Agent App
    await agent_app.initialize()
    print("application Ready")

    logger.info("Staring Autonomous Agent")
    agent_app.Autonomous_24_7 = True
    agent_app.multi_agent_orchestrator = AutonomousOrchestrator(
        memory = agent_app.memory_system
    )

    # Start Orchestration in the background
    agent_task = asyncio.create_task(agent_app.multi_agent_orchestrator.start())
    logger.info("Multi-agent is running in the backgound")

    try:
        yield
    finally:
            print(" Shutting down application...")
            if agent_app.multi_agent_orchestrator and agent_app.multi_agent_orchestrator.is_running:
                await agent_app.multi_agent_orchestrator.stop()
            await agent_app.shutdown()
            print(" Shutdown complete")


app = FastAPI(title="Autonomous Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: ["http://localhost:3000", "http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------ API MODELS ------------------
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


# ------------------ Helper Functions ------------------
def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF"""
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX"""
    doc = docx.Document(file_path)
    text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
    return text


def extract_text_from_file(file_path: str, filename: str) -> str:
    """Extract text from file"""
    if filename.endswith('.pdf'):
        return extract_text_from_pdf(file_path)
    elif filename.endswith('.docx'):
        return extract_text_from_docx(file_path)
    elif filename.endswith('.txt'):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file format: {filename}")


               # API ENDPOINTS 
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "ok",
        "message": "Autonomous Agent API is running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/task", response_model=TaskResponse)
async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Create a Task for the Autonomous Agent"""
    task_id = f"{request.task_id}_{int(datetime.now().timestamp())}"
    print(f"📥 Received task: {task_id}")

    # Schedule agent task in the background
    background_tasks.add_task(
        execute_agent_task,
        task_id=task_id,
        task_data=request.dict()
    )

    return TaskResponse(
        task_id=task_id,
        status="queued",
        message="Task submitted successfully"
    )


@app.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get status of a specific task"""
    return TaskStatusResponse(
        task_id=task_id,
        status="processing",
        result=None
    )


@app.get("/ping")
async def ping():
    """Simple ping endpoint"""
    return {"message": "pong"}


@app.get("/test")
async def test_connection():
    """Test frontend connection"""
    return {
        "message": "Frontend connected successfully!",
        "timestamp": datetime.now().isoformat(),
        "agent_status": "ready"
    }


@app.post("/resume/upload")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_email: Optional[str] = Form(None),
    keywords: Optional[str] = Form(""),
    location: Optional[str] = Form("Remote"),
    experience_level: Optional[str] = Form("mid")
):
    try:
        task_id = f"resume_{int(datetime.now().timestamp())}"
        resume_id = f"resume_{task_id}"

        print(f"Received Resume {file.filename}")

        # Save resume file
        os.makedirs("data/resumes", exist_ok=True)
        file_path = f"data/resumes/{resume_id}_{file.filename}"

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        #  Extract text
        resume_text = extract_text_from_file(file_path, file.filename)

        print(f"Extracted {len(resume_text)} characters")

        #  Prepare metadata
        job_keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        resume_payload = {
            "resume_id": resume_id,
            "resume_text": resume_text,
            "keywords": job_keywords,
            "location": location,
            "experience_level": experience_level,
            "user_email": user_email,
            "uploaded_at": datetime.now().isoformat()
        }

        #  Store resume in RAG memory
        if agent_app.multi_agent_orchestrator is not None:
            await agent_app.multi_agent_orchestrator.shared_context.set(
                "latest_resume", resume_payload
            )

            
            try:
                await agent_app.multi_agent_orchestrator.memory.store_resume(
                    resume_id, resume_text, resume_payload
                )
            except:
                print("⚠ No store_resume() function found. Skipping RAG store.")

            #Trigger ResumeMatcherAgent cycle
            background_tasks.add_task(
                agent_app.multi_agent_orchestrator.trigger_manual_cycle,
                "ResumeMatcherAgent"
            )

        else:
            print("❌ Multi-agent orchestrator not running. Resume stored only.")

        return {
            "success": True,
            "resume_id": resume_id,
            "message": "Resume uploaded. Agents are processing it...",
        }

    except Exception as e:
        print(f"Upload error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}



@app.post("/resume/match")
async def match_reume(
    background_tasks: BackgroundTasks,
    resume_text: str = Form(...),
    user_email: Optional[str] =Form(None),
    keywords: Optional[str] = Form(""),
    location: Optional[str] = Form("Remote"),
    experience_level: Optional[str] =Form("mid")
):
  """
  EndPOINT: Submit resume as text Cruisul for Frontend
  """
  try: 
      task_id = f"resume_text{int(datetime.now().timestamp())}"


      ## Parse keywords 
      job_keywords = [k.strip() for k in keywords.split(",")if k.strip()]


      # Sample initial state as upload endpoint

      initial_state = {
           "task": f"Find and match job opportunities for provided resume",
            "task_type": "job_matching",
            "task_id": task_id,
            "priority": 5,
            "resume_text": resume_text,
            "resume_id": f"resume_{task_id}",
            "job_keywords": job_keywords,
            "job_location": location,
            "experience_level": experience_level,
            "user_email": user_email,
            "user_id": f"user_{task_id}",
            
            # Standard fields
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
            
            # Job fields
            "jobs_data": [],
            "matched_jobs": [],
            "quality_check": {},
            "email_status": {},
            "report_data": {},
            "final_report": None,
            "pdf_path": None
      }

      config = {
        "configurable": {
            "thread_id": task_id
        }
      }


      background_tasks.add_task(
        execute_job_matching_workflow,
        task_id =task_id,
        initial_state=initial_state,
        config=config
      )

      return{
        "success": True,
        "task_id": task_id,
        "message": "Resume Submitted. Job matching in progress..."
      }
  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))

  ## Backgrount task

async def execute_job_matching_workflow(task_id: str, initial_state: dict, config: dict):
    """Execute job matching workflow (separate from general research workflow)"""

    try:
        print(f"Starting job matching for: {task_id}")

        resume_id = initial_state.get("resume_id")
        resume_text = initial_state.get("resume_text")
        job_keywords = initial_state.get("job_keywords",[])

        # Nofity multi - agents
        if agent_app.multi_agent_orchestrator:
         try:
            await agent_app.multi_agent_orchestrator.notify_new_resume(
                resume_id=resume_id,
                keywords=job_keywords
            )
            logger.info(f"Notify multi-agents new resume: {resume_id}")
         except Exception as e:
            logger.error(f"Failed to notify {e}")
        
        jobs_count = len(result.get('jobs_data', []))
        print(f"Found {jobs_count}")

        # Notify about new jobs
        if agent_app.multi_agent_orchestrator and jobs_count > 0:
            try:
                await agent_app.multi_agent_orchestrator.notify_new_jobs(
                    jobs_count=jobs_count,
                    soource = "main worklow"
                )
                logger.info(f"Notified multi agents {jobs_count}")
            except Exception as e:
                logger.error(f"Failed to count jobs {e}")
        
        # Notfify New matches created
        matches_count = len(result.get('matches_found', []))
        print(f"Found {matches_count} matching jobs")
        print(f"COnfidence {result.get('confidence_score', 0):.2f}")

        # Notify Agents about the matches
        if agent_app.multi_agent_orchestrator and matches_count > 0:
            try:
                await agent_app.multi_agent_orchestrator.notify_matches_created(
                    matches_count=matches_count,
                    resume_id=resume_id
                )
                logger.info(f" New matches {matches_count} Created")
            except Exception as e:
                logger.error(f"Failed to create matches:{e}")


        result = await agent_app.agent_graph.graph.ainvoke(initial_state, config)

        print(f"job matching{task_id} Completed")
        print(f"Found{len(result.get('matched_jobs', []))} matching jobs")
        print(f"Confidence {result.get('confidence_score',0):.2%}")



        ## Generate and send report 
        report_content = result.get('final_report') or result.get('final_output', '')

        if report_content and result.get('user_email'):
            print(f"Sending job report to:{result.get('user_email')}")

            ## Genrate PDF
            pdf_path = pdf_generator.markdown_to_pdf(
                markdown_content=report_content,
                filename = f"job_matches{task_id}" 
            )

            email_body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .header {{ background: #4CAF50; color: white; padding: 20px; }}
                    .job {{ background: #f9f9f9; padding: 10px; margin: 10px 0; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🎯 Your Job Matches Are Ready!</h1>
                </div>
                <p>We found {len(result.get('matched_jobs', []))} opportunities matching your profile.</p>
                <h3>Top Matches:</h3>
            """
            
            for i, job in enumerate(result.get('matched_jobs', [])[:5], 1):
                email_body += f"""
                <div class="job">
                    <strong>{i}. {job.get('title', 'Position')}</strong><br>
                    Company: {job.get('company', 'N/A')}<br>
                    Match: {job.get('match_percentage', 0):.0f}%<br>
                    Location: {job.get('location', 'N/A')}
                </div>
                """
            
            email_body += """
                <p>📎 Full detailed report attached as PDF.</p>
            </body>
            </html>
            """

            email_sender.send_report(
                subject =f"{len(result.get('matched_jobs', []))} Job matches found",
                body=email_body,
                pdf_path=pdf_path
            )

            print(f"Email sent Successfully")

        return result
    
    except Exception as e:
        print(f"Job matching {task_id} Failed {e}")
        import traceback
        traceback.print_exc()


# ------------------ AGENT EXECUTION ------------------
async def execute_agent_task(task_id: str, task_data: Dict):
    """Execute Agent Task via AgentApplication"""
    try:
        print(f" Executing task {task_id}")
        print(f" Task data: {task_data}")

        # Prepare initial state for LangGraph
        initial_state = {
            "task": task_data.get("task", ""),
            "task_type": task_data.get("config", {}).get("task_type", "custom"),
            "task_id": task_id,
            "priority": task_data.get("priority", 5),
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


            "resume_text": None, 
            "job_keywords": [],
            "jobs_data": [],
            "matched_jobs": [],
        }

        config = {"configurable": {"thread_id": task_id}}

        print(f"Starting graph execution for {task_id}")
        result = await agent_app.agent_graph.graph.ainvoke(initial_state, config)

        print(f"Task {task_id} completed successfully")
        print(f"Confidence Score: {result.get('confidence_score', 0)}")
        print(f"Iterations: {result.get('iteration', 0)}")
        print(f"Final Status: {result.get('status', 'unknown')}")

        # Generate Report
        print(f"Preparing email for task: {task_id}")

        try:
            report_content = result.get('final_output', '')
            if report_content:
                print(f"Report Generated: {len(report_content)} characters")
            else:
                print("No final output — creating summary from insights")
                insights = result.get('extracted_insights', [])
                report_content = f"Task Report:\n\n## Task: {task_data.get('task')}\n\n"
                if insights:
                    report_content += "## Key Findings\n\n"
                    for i, insight in enumerate(insights[:5], 1):
                        if isinstance(insight, dict):
                            findings = insight.get('key_findings', [])
                            for finding in findings[:3]:
                                report_content += f"{i}. {finding}\n"
                else:
                    print("Task completed but no detailed insight available.\n")

            task_type = task_data.get('config', {}).get('task_type', 'task')
            pdf_path = pdf_generator.markdown_to_pdf(
                markdown_content=report_content,
                filename=f"{task_type}_{task_id}"
            )
            print(f"PDF Created: {pdf_path}")

            task_name = task_data.get('task', 'Task')[:80]
            confidence = result.get('confidence_score', 0)

            email_body = f"""
            <html>
            <body>
                <h2> Autonomous AI Agent Report</h2>
                <p><strong>Task:</strong> {task_name}</p>
                <p><strong>Type:</strong> {task_type}</p>
                <p><strong>ID:</strong> {task_id}</p>
                <p><strong>Confidence:</strong> {confidence:.1%}</p>
                <p><strong>Iterations:</strong> {result.get('iteration', 0)}</p>
                <hr>
                <p><strong>Report Preview:</strong></p>
                <p>{report_content[:600].replace('\n', '<br>')}...</p>
                <p><em>Full report is attached as a PDF document.</em></p>
            </body>
            </html>
            """

            print("Sending email...")
            email_sender.send_report(
                subject=f"Task Completed: {task_name}",
                body=email_body,
                pdf_path=pdf_path
            )
            print(f"Report successfully sent to {email_sender.to_email}\n")

        except Exception as email_error:
            print(f"Failed to send email: {email_error}")
            import traceback
            traceback.print_exc()

        return result

    except Exception as e:
        print(f"Task {task_id} failed: {e}")
        import traceback
        traceback.print_exc()




multi_agent_orchestrator = None

@app.on_event("startup")
async def startup_event():
    """Initialize Apllication"""
    global multi_agent_orchestrator

    await agent_app.initialize()

    # Auto-start 24_7 System if configured 
    if os.getenv("AUTO_START_AUTONOMOUS", "false").lower() == "true":
        logger.info("Auto Starting 24_7 autonomous system")
        multi_agent_orchestrator = agent_app.multi_agent_orchestrator
        asyncio.create_task(multi_agent_orchestrator.start())

@app.post("/api/autonomous/start")
async def start_autonomous_system():
    """Start 24/7 Multi agent System"""
    global multi_agent_orchestrator

    if not agent_app.autonomous_24_7:
        # Enabling it dynamically
        agent_app.autonomous_24_7 = True
        agent_app.multi_agent_orchestrator = AutonomousOrchestrator(
            agent_app=agent_app,
            memory=agent_app.memory_system
        )

    if agent_app.multi_agent_orchestrator.is_running:
        return {"success": False, "messgae": "Already Running"}

    multi_agent_orchestrator = agent_app.multi_agent_orchestrator
    asyncio.create_task(multi_agent_orchestrator.start())

    return {
        "Success": True,
        "message": "24_7 Autonomous is Runnnig",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/autonomous/stop")
async def stop_autonomous_system():
    """Stop Autonomous System"""
    if not agent_app.multi_agent_orchestrator or not agent_app.multi_agent_orchestrator.is_running:
        return {"Success": False, "message": "Autonomous System is not Running"}
    
    await agent_app.multi_agent_orchestrator.stop()

    return {
        "success": True,
        "message": "Autonomous System Stopped"
    }

@app.post("/api/autonomous/status")
async def get_autonomous_status():
    """Get 24_7 autonomous Status"""
    if not agent_app.multi_agent_orchestrator:
        return {"enabled": False, "message": "Not Running"}
    
    status = agent_app.multi_agent_orchestrator.get_status()
    return {"success": True, **status}

@app.post("/api/autonomous/trigger/{event_type}")
async def trugger_event(event_type:str, payload: dict):
    """Manually Trigger an event"""


    if not agent_app.multi_agent_orchestrator or not agent_app.multi_agent_orchestrator.is_running:
        return {"success": False, "message": "System Not Running"}
    
    
    event = {
        'event_type': event_type,
        'source': 'manual_api',
        'payload': payload,
        'timestamp': datetime.now().isoformat()
    }

    await agent_app.multi_agent_orchestrator.event_queue.put(event)

    return {"success": True, "event": event}


@app.get("/api/system/status")
async def get_system_status():
    """Get Status of Entire System"""
    return {
        "agentic_mode": agent_app.agentic_mode,
        "autonomous_24_7": agent_app.autonomous_24_7,
        "graph_initialized": agent_app.graph_initialized is not None,
        "orchestrator_active":agent_app.orchestrator is not None,
        "multi_agent_status": agent_app.get_autonomous_status(),
        "memory_system": agent_app.memory_system is not None
    }


@app.get("/status/agents")
async def get_agent_status():
    """Check multi-agents status"""
    if not agent_app.multi_agent_orchestrator:
        return {"error": "Multi-agent system not running"}

@app.get("/status/agents/{agent_name}")
async def get_agent_details(agent_name:str):
    """Get agents details insight about specific agent"""
    if not agent_app.multi_agent_orchestrator:
        return {"error": "Multi agent system is not running"}

    return await multi_agent_orchestrator.get_agent_insights(agent_name)

@app.post("/agent/trigger/{agent_name}")
async def trigger_agent_manually(agent_name: str):
    """Manually trigger agent for texting"""
    if not agent_app.multi_agent_orchestrator:
        return {"error": "agent is not running"}
    
    if not agent_name in agent_app.multi_agent_orchestrator:
        return {"error": f" Agent nane {agent_name} not found"}
    
    try:
        agent = agent_app.multi_agent_orchestrator.agents[agent_name]
        result = await agent.run_cycle
        return {
            "success": True,
            "agent": agent_name,
            "result": result
        }
    except Exception as e:
        return {"Success": False, "error": str(e)}


# ------------------ ENTRY POINT ------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
