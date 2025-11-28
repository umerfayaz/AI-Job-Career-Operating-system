"""
 Running BOTH Brains Together

- Starts both Brain 1 (LangGraph) and Brain 2 (Multi-agents) together
- They share data through the unified application
- API endpoints work with both systems
- No code duplication or conflicts

"""

import os
import fitz
import docx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel
from typing import Dict, Optional
import uvicorn
import structlog
from backend.multiagents.guardrails import JobReportGuardrails
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import asyncio

from backend.application import AgentApplication
from backend.core.email_sender import EmailSender
from backend.tools.pdf_generator import PDFGenerator

logger = structlog.get_logger()

# Global unified application
agent_app = AgentApplication(agentic_mode=True, autonomous_24_7=True)
email_sender = EmailSender()
guardrails = JobReportGuardrails()
pdf_generator = PDFGenerator()


# LIFESPAN - Start BOTH Brains Together


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    - Brain 1: LangGraph (for API workflows)
    - Brain 2: Multi-agents (for 24/7 monitoring)
    """
    logger.info("=" * 60)
    logger.info(" STARTING UNIFIED SYSTEM")
    logger.info("=" * 60)
    
    # Initializing the unified application (both brains)
    await agent_app.initialize()
    
    # Starting Brain 2 (multi-agent system) in background
    logger.info(" Starting Brain 2 (24/7 Multi-Agents) in background...")
    orchestrator_task = asyncio.create_task(agent_app.start_autonomous_system())
    
    logger.info("=" * 60)
    logger.info(" UNIFIED SYSTEM READY")
    logger.info("   Brain 1 (LangGraph): Ready for API requests")
    logger.info("   Brain 2 (Multi-Agents):  Running 24/7")
    logger.info("   Integration:  Connected")
    logger.info("=" * 60)
    
    try:
        yield  # API runs here
    finally:
        logger.info(" Shutting down unified system...")
        await agent_app.shutdown()
        logger.info(" Shutdown complete")


app = FastAPI(
    title="Unified Agent API", 
    version="2.0.0",
    description="Dual-brain system: LangGraph + Multi-Agents",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


# API ENDPOINTS - Basic


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


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "system_status": agent_app.get_system_status()
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


# JOB MATCHING ENDPOINTS - Uses BOTH Brains

@app.post("/resume/upload")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_email: Optional[str] = Form(None),
    keywords: Optional[str] = Form(""),
    location: Optional[str] = Form("Remote"),
    experience_level: Optional[str] = Form("mid")
):
    """
    Upload resume and trigger job matching
    
    """
    try:

        job_keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        can_proceed, reason = await guardrails.check_can_proceed(
            "fetched_jobs",
            {"keywords_count": len(job_keywords)}
        )

        if not can_proceed:
           raise  HTTPException(
            statue_code = 429,
            detail=f"Rate Limit: {reason}"
           )

        task_id = f"resume_{int(datetime.now().timestamp())}"
        resume_id = f"resume_{task_id}"

        logger.info(f"📄 Received resume: {file.filename}")

        # Save file
        os.makedirs("temp", exist_ok=True)
        file_path = f"temp/{resume_id}_{file.filename}"

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Extract text
        resume_text = extract_text_from_file(file_path, file.filename)
        logger.info(f"   Extracted {len(resume_text)} characters")

        # Prepare state for Brain 1 (LangGraph workflow)
        initial_state = {
            "task": "Find and match job opportunities for uploaded resume",
            "task_type": "job_matching",
            "task_id": task_id,
            "priority": 5,
            "resume_text": resume_text,
            "resume_id": resume_id,
            "job_keywords": job_keywords,
            "job_location": location,
            "experience_level": experience_level,
            "user_email": user_email,
            "user_id": f"_{task_id}",
            
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
            
            # Job-specific fields
            "jobs_data": [],
            "matched_jobs": [],
            "quality_check": {},
            "email_status": {},
            "report_data": {},
            "final_report": None,
            "pdf_path": None
        }

        config = {"configurable": {"thread_id": task_id}}

        logger.info(f"🎯 Starting unified workflow: {task_id}")

        # Run in background using unified application
        background_tasks.add_task(
            execute_unified_job_matching,
            task_id=task_id,
            initial_state=initial_state,
            config=config
        )

        # Clean up temp file
        try:
            os.remove(file_path)
        except:
            pass

        await guardrails.record_action("fetched_jobs")

        return {
            "success": True,
            "task_id": task_id,
            "message": "Resume uploaded. Dual-brain system processing...",
            "status_endpoint": f"/task/{task_id}",
            "brains_active": {
                "langgraph": True,
                "multi_agents": True
            }
        }

    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



# BACKGROUND TASK - Unified Workflow

async def execute_unified_job_matching(task_id: str, initial_state: dict, config: dict):
    """
    Execute job matching using the unified application
    
    """
    try:
        logger.info(f" Starting unified job matching: {task_id}")
        
        # Run through unified application (handles both brains)
        result = await agent_app.run_langgraph_workflow(initial_state, config)
        
        logger.info(f" Unified workflow completed: {task_id}")
        logger.info(f"   Jobs found: {len(result.get('jobs_data', []))}")
        logger.info(f"   Matches: {len(result.get('matched_jobs', []))}")
        logger.info(f"   Confidence: {result.get('confidence_score', 0):.2%}")
        
        # Generate and send report
        report_content = result.get('final_report') or result.get('final_output', '')

        if report_content and result.get('user_email'):
            logger.info(f"📧 Sending report to: {result.get('user_email')}")

            # Generate PDF
            pdf_path = pdf_generator.markdown_to_pdf(
                markdown_content=report_content,
                filename=f"job_matches_{task_id}" 
            )

            # Create email
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
                    <p>Powered by Dual-Brain AI System</p>
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
                <p>📎 Full report attached as PDF.</p>
                <p><small>🧠 Processed by LangGraph + Multi-Agent System</small></p>
            </body>
            </html>
            """

            email_sender.send_report(
                subject=f"{len(result.get('matched_jobs', []))} Job Matches Found",
                body=email_body,
                pdf_path=pdf_path
            )

            logger.info(f" Email sent successfully")

        return result
    
    except Exception as e:
        logger.error(f"Unified workflow failed: {task_id} - {e}", exc_info=True)



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




# SYSTEM STATUS ENDPOINTS

@app.get("/api/system/status")
async def get_system_status():
    """Get complete system status (both brains)"""
    return agent_app.get_system_status()


@app.get("/api/system/brain1")
async def get_brain1_status():
    """Get Brain 1 (LangGraph) status"""
    status = agent_app.get_system_status()
    return status["brain_1_langgraph"]


@app.get("/api/system/brain2")
async def get_brain2_status():
    """Get Brain 2 (Multi-Agents) status"""
    return agent_app.get_autonomous_status()

# MULTI-AGENT ENDPOINTS (Brain 2 Control)

@app.get("/status/agents")
async def get_agent_status():
    """Get status of all multi-agents"""
    if not agent_app.multi_agent_orchestrator:
        return {"error": "Multi-agent system not initialized"}
    
    return agent_app.multi_agent_orchestrator.get_status()


@app.get("/status/agents/{agent_name}")
async def get_agent_details(agent_name: str):
    """Get detailed insights about a specific agent"""
    if not agent_app.multi_agent_orchestrator:
        return {"error": "Multi-agent system not initialized"}
    
    return await agent_app.multi_agent_orchestrator.notify_agent_insight(agent_name)


@app.post("/agents/trigger/{agent_name}")
async def trigger_agent_manually(agent_name: str):
    """Manually trigger a specific agent"""
    if not agent_app.multi_agent_orchestrator:
        return {"error": "Multi-agent system not initialized"}
    
    if agent_name not in agent_app.multi_agent_orchestrator.agents:
        return {"error": f"Agent '{agent_name}' not found"}
    
    try:
        agent = agent_app.multi_agent_orchestrator.agents[agent_name]
        result = await agent.run_cycle()
        return {
            "success": True,
            "agent": agent_name,
            "result": result
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# INTEGRATION ENDPOINTS

@app.post("/api/integration/notify/resume")
async def notify_new_resume(resume_id: str, keywords: list):
    """Manually notify Brain 2 about a new resume"""
    if not agent_app.multi_agent_orchestrator:
        return {"error": "Multi-agent system not initialized"}
    
    await agent_app.multi_agent_orchestrator.notify_new_resume(resume_id, keywords)
    return {"success": True, "message": f"Brain 2 notified about resume {resume_id}"}


@app.post("/api/integration/notify/jobs")
async def notify_new_jobs(job_count: int, source: str = "manual"):
    """Manually notify Brain 2 about new jobs"""
    if not agent_app.multi_agent_orchestrator:
        return {"error": "Multi-agent system not initialized"}
    
    await agent_app.multi_agent_orchestrator.notify_new_jobs(job_count, source)
    return {"success": True, "message": f"Brain 2 notified about {job_count} jobs"}


# TEST ENDPOINTS

@app.get("/test/connection")
async def test_connection():
    return {
        "message": "Unified system connected!",
        "timestamp": datetime.now().isoformat(),
        "system": agent_app.get_system_status()
    }


@app.post("/test/brain1")
async def test_brain1():
    """Test Brain 1 (LangGraph)"""
    if not agent_app.agent_graph:
        return {"error": "Brain 1 not initialized"}
    
    return {
        "status": "ok",
        "brain": "LangGraph",
        "components": {
            "graph": agent_app.agent_graph is not None,
            "orchestrator": agent_app.orchestrator is not None,
            "goal_manager": agent_app.goal_manager is not None
        }
    }


@app.post("/test/brain2")
async def test_brain2():
    """Test Brain 2 (Multi-Agents)"""
    if not agent_app.multi_agent_orchestrator:
        return {"error": "Brain 2 not initialized"}
    
    # Trigger a simple agent cycle
    try:
        agent = agent_app.multi_agent_orchestrator.agents["ResumeMatcherAgent"]
        result = await agent.run_cycle()
        return {
            "status": "ok",
            "brain": "Multi-Agents",
            "test_result": result
        }
    except Exception as e:
        return {"error": str(e)}

# ENTRY POINT

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )