import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import markdown
import structlog
from ..agent.graph import AgentGraph
from ..agent.state import AgentState

logger = structlog.get_logger()


class AutonomousOrchestration:
    """`
    Main orchestration 24/7 autonomous operations
    Manages task scheduling, execution and Monitoring
    """
     
    def __init__(self, agent_graph: AgentGraph, scheduler_config: Dict, email_sender =None, pdf_generator=None):
        self.graph = agent_graph
        self.scheduler_config = scheduler_config
        self.is_running = False
        self.task_queue = asyncio.Queue()
        self.start_time = datetime.now()
        self.email_sender = email_sender,
        self.pdf_generator = pdf_generator
        
        # Add tracking attributes
        self.active_tasks = {}
        self.completed_tasks = []
        self.failed_tasks = []
        self.task_durations = []
        self.task_confidence_scores = []

    
    async def start(self):
        """Start the autonomous operations"""
        self.is_running = True
        logger.info("Starting the autonomous agent orchestration")
    
        # Start the background Tasks
        await asyncio.gather(
            self._task_scheduler(),
            self._task_executer(),
            self._health_monitor(),
            self._matrics_collector()
        )
    
    async def stop(self):
        """Gracefully Stop the orchestrator"""
        logger.info("Stopping orchestration")
        self.is_running = False

        # Wait for active task to complete
        while self.active_tasks:
            await asyncio.sleep(1)
    
    async def _task_scheduler(self):
        """Schedule recurring tasks"""
        while self.is_running:
            try:
                for task_config in self.scheduler_config.get('recurring_tasks', []):
                    if self._should_run_task(task_config):
                        await self.task_queue.put({
                            'type': task_config['type'],
                            'config': task_config,
                            'scheduled_at': datetime.now().isoformat()
                        })
                        logger.info(f"Schedule Task: {task_config['name']}")
    
                # Check for manual tasks from UI/API
                await asyncio.sleep(60) 

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)

    async def _task_executer(self):
        """Execute Task from queue"""
        
        while self.is_running:
            task_id = None  # Initialize task_id
            try:
                task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )               
                
                task_id = f"{task['type']}_{datetime.now().timestamp()}"
                self.active_tasks[task_id] = task
                
                logger.info(f"Executing task: {task_id}")
                
                task_start_time = datetime.now()
                
                # Create Initial State
                create_state = AgentState(
                    task=task['config'].get('description', ''),
                    task_type=task['type'],
                    task_id=task_id,
                    priority=task['config'].get('priority', 5),
                    plan=[],
                    current_step=0,
                    reasoning_history=[],
                    search_queries=[],
                    search_results=[],
                    scraped_content=[],
                    extracted_insights=[],
                    analysis_results={},
                    relevant_memories=[],
                    entity_context={},
                    conversation_history=[],
                    confidence_score=0.0,
                    validation_results={},
                    errors=[],
                    retry_count=0,
                    final_output=None,
                    artifacts=[],
                    iteration=0,
                    max_iteration=10,
                    started_at=datetime.now(),
                    status='planning'
                )

                config = {"configurable": {"thread_id": task_id}}
                
                final_confidence = 0.0
                
                async for event in self.graph.graph.astream(create_state, config):
                    logger.debug(f"Graph event: {event}")
                    
                    # Update Task Event
                    if 'reasoner' in event:
                        final_confidence = event['reasoner'].get('confidence_score', 0)
                        self.active_tasks[task_id]['confidence'] = final_confidence

                # Task Completed - Track metrics
                task_duration = (datetime.now() - task_start_time).total_seconds()
                self.task_durations.append(task_duration)
                self.task_confidence_scores.append(final_confidence)
                self.completed_tasks.append({
                    'task_id': task_id,
                    'type': task['type'],
                    'duration': task_duration,
                    'confidence': final_confidence,
                    'completed_at': datetime.now()
                })
                
                logger.info(f"Task Completed: {task_id}")

                if self.email_sender and self.pdf_generator:
                    logger.info(f"Sending email for task: {task_id}")
                    try:
                        await self._send_report_email(
                            task_id =task_id,
                            task_config =task['config'],
                            final_state=create_state,
                            confidence=final_confidence,
                            duration=task_duration
                        )
                        
                        logger.info(f"Email sent for task: {task_id}")
                    except Exception as e:
                        logger.error(f"Failed to sent emails:{e}", exc_error=True)

                else:
                    logger.warning("Email/PDF not Configured")        

                del self.active_tasks[task_id]

            except asyncio.TimeoutError:
                continue

            except Exception as e:
                logger.error(f"Execution error: {e}", task_id=task_id if task_id else 'unknown')
                
                # Track failed task
                if task_id and task_id in self.active_tasks:
                    self.failed_tasks.append({
                        'task_id': task_id,
                        'error': str(e),
                        'failed_at': datetime.now()
                    })
                    del self.active_tasks[task_id]
    
    async def _health_monitor(self):
        """Monitor System Health and agent Performance"""

        while self.is_running:
            try:
                health_metrics = {
                    'queue_size': self.task_queue.qsize(),
                    'active_tasks': len(self.active_tasks),
                    'uptime': (datetime.now() - self.start_time).total_seconds(),
                    'memory_usage': self._get_memory_usage(),
                    'timestamp': datetime.now().isoformat()
                }

                logger.info("Health_check", **health_metrics)

                # Health Warning
                if health_metrics['queue_size'] > 100:
                    logger.warning("Task queue size is growing large")

                await asyncio.sleep(300)  # Sleep for 5 min

            except Exception as e:
                logger.error(f"Health Monitor error: {e}")
                await asyncio.sleep(300)

    async def _matrics_collector(self):
        """Collecting Metrics for report"""

        while self.is_running:
            try:
                metrics = {
                    'tasks_completed_total': self._count_completed_tasks(),
                    'tasks_failed_total': self._count_failed_tasks(),
                    'avg_task_duration': self._calculate_avg_duration(),
                    'avg_confidence_score': self._calculate_avg_confidence()
                }

                logger.info("Metrics", **metrics)
                await asyncio.sleep(60)
            
            except Exception as e:
                logger.error(f"Metrics Collector error: {e}")
                await asyncio.sleep(60)

    
    def _should_run_task(self, task_config: Dict) -> bool:
        """Check if a scheduled task should run"""

        schedule = task_config.get('schedule', {})
        schedule_type = schedule.get('type', 'interval')

        if schedule_type == 'interval':
            # Check if scheduled time has passed
            interval_minutes = schedule.get('interval_minutes', 60)
            last_run = task_config.get('last_run')

            if not last_run:
                task_config['last_run'] = datetime.now()
                return True
            
            if datetime.now() - last_run > timedelta(minutes=interval_minutes):
                task_config['last_run'] = datetime.now()
                return True
        
        elif schedule_type == 'cron':
            pass

        return False

    def _get_memory_usage(self) -> float:
        """Get Current Memory Usage in MB"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            return 0.0

    # Metrics tracking methods
    def _count_completed_tasks(self) -> int:
        """Count total completed tasks"""
        return len(self.completed_tasks)
    
    def _count_failed_tasks(self) -> int:
        """Count total failed tasks"""
        return len(self.failed_tasks)
    
    def _calculate_avg_duration(self) -> float:
        """Calculate average task duration in seconds"""
        if not self.task_durations:
            return 0.0
        return sum(self.task_durations) / len(self.task_durations)
    
    def _calculate_avg_confidence(self) -> float:
        """Calculate average confidence score"""
        if not self.task_confidence_scores:
            return 0.0
        return sum(self.task_confidence_scores) / len(self.task_confidence_scores)

    async def _send_report_email(self, task_id: str, task_config: Dict, final_state: AgentState, confidence: float, duration: float):
        """
        Generate PDF and Send Email after task Completion
        """
        if not self.email_sender or not self.pdf_generator:
            logger.warning(f"Email/PDF not configured - Skipping Delivery")
            return

        try:
            task_name = task_config.get('name', 'unknown')
            task_type = task_config.get('type', 'unknown')

            ## Final Report Cotent
            report_content = final_state.get('final_output', 'No output generated')

            # If no output create a summary from insights
            if not report_content or not report_content == 'No output generated':
                insights = final_state.get('extracted_insights', [])
                if insights:
                    report_content= self._create_report_summary(
                        task_name, insights, confidence, duration
                    )

                    ## PDF Generator

                    pdf_path = self.pdf_generator.markdown_to_pdf(
                        markdown_content = report_content,
                        filname = f"{task_type} {task_id}"
                    )


                    ## Create Email Body
                    email_body = f"""
                     <html>
                    <body style="font-family: Arial, sans-serif;">
                      <h2 style="color: #2563eb;">🤖 Autonomous Agent Report</h2>
                
                        <div style="background: #f3f4f6; padding: 15px; border-radius: 5px; margin: 20px 0;">
                           <p><strong>Task:</strong> {task_name}</p>
                           <p><strong>Type:</strong> {task_type}</p>
                           <p><strong>Completed:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                           <p><strong>Duration:</strong> {duration:.1f} seconds</p>
                           <p><strong>Confidence:</strong> {confidence:.1%}</p>
                        </div>
                
                        <h3>Preview:</h3>
                        <p>{report_content[:500]}...</p>
                
                        <p style="margin-top: 30px;">
                           <strong>📎 Full report attached as PDF</strong>
                        </p>
                
                        <hr style="margin-top: 40px;">
                         <p style="color: #666; font-size: 12px;">
                            Generated by Autonomous AI Agent • Running 24/7
                        </p>
                    </body>
                    </html>
                    """
                    ## Send Email
                    self.email_sender.send_report(
                        subject=f"Autonomous Report: {task_name}",
                        body=email_body,
                        attachment=pdf_path
                    )

                    logger.info(f"Report Emailed name:{task_name}")

        except Exception as e:
            logger.error(f"Failed to send report{e}")
    
    def create_summary_report(self, task_name: str, insights: List, confidence: float, duration: float) ->str:
        """
        Create a report Summary from insights if noo final output exists
        """

        report = f"""#{task_name}

    
    ## Execute Summary

    Task Completed in {duration:.if} seconds with {confidence:.1%} Confidence

    ## Key Findings

    """

        for i, insight in enumerate(insights):
            if isinstance(insight, Dict):
                insight_text = insight.get('content', str(insight))
            else:
                insight_text = str(insight)
            
            report +=f"{i}.{insight_text}"

        report = f"""

    ---
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
    *Agent: Autonomous AI Agent*
    """
         
        return report






            








    
