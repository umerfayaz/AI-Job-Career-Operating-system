"""
Main Autonomous Orchestrator
Runs 24/ Cordinates all agents based on events
"""

import asyncio
from typing import List , Dict
from datetime import datetime
import structlog
import signal
import sys


from .agents_team import (
    JobScraperAgent,
    ResumeMatcherAgent,
    ReportGeneratorAgent,
    MemoryMaintenanceAgent,
    NotificationAgent,
    EpisodicMemory,
    SharedContext
)

from .decision_engine import EventType, DecisionEngine
from .event_monitor import EventMonitor
from ..core.memory_system import MemoryRAGSystem


def get_app():
    from backend.application import AgentApplication
    return AgentApplication()

logger = structlog.get_logger()

class AutonomousOrchestrator:
    """Main Orchestraator Runs 24/7"""

    def __init__(self, memory: MemoryRAGSystem):
        self.agent_app =get_app()
        self.memory = memory


        # Initialze EpisodicMemory and SharedContext 
        self.episodic_memory = EpisodicMemory(memory)
        self.shared_context = SharedContext()

        ## Inittialize Components
        self.decision_engine = DecisionEngine()
        self.event_monitor = EventMonitor(memory)
        self.event_queue = asyncio.Queue()

        ## Inittialize Agents

        self.agents = {
            'JobScraperAgent': JobScraperAgent(self.agent_app, memory, self.episodic_memory, self.shared_context),
            'ResumeMatcherAgent': ResumeMatcherAgent(self.agent_app, memory, self.episodic_memory, self.shared_context),
            'ReportGeneratorAgent': ReportGeneratorAgent(self.agent_app, memory, self.episodic_memory, self.shared_context),
            'MemoryMaintenanceAgent': MemoryMaintenanceAgent(self.agent_app, memory, self.episodic_memory, self.shared_context),
            'NotificationAgent': NotificationAgent(self.agent_app, memory, self.episodic_memory, self.shared_context)
        }

        self.is_running =False
        self.stats = {
            'events_processed': 0,
            'agents_activated': 0,
            'start_time': 0,
            'uptime_seconds': 0
        }


        # Setup Shutdown
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

    def _shutdown_handler(self, signum, frame):
        """Handle shutdown"""
        logger.info("Shutdown Signal Received")
        self.is_running =False
        sys.exit(0)

    async def process_event(self, event: Dict):
        """Engine decides which agent to activate"""

        logger.info(f"Processing Event: {event.get('type')}")

        try:

            # Decide which agent to activate
            agents_to_activate = self.decision_engine.decide(event)

            if not agents_to_activate:
                logger.info("Now agents needed to activate")
                return

            # Activate agents in parraller
            tasks =[]
            for agent_name in agents_to_activate:
                agent = self.agents.get(agent_name)

                if agent and agents_to_activate:
                    tasks.append(agent.run_cycle())
                    self.stats['agents_activated'] +=1
            
            ## Run all agents Concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            ## 4 Log
            for agent_name, result in zip(agents_to_activate, results):
                if isinstance(result, Exception):
                    logger.error(f" {agent_name} Failed: {result}")
                
                else:
                    logger.info(f"{agent_name} {result.get('status')}")
            
            self.stats['events_processed'] +=1

        except Exception as e:
            logger.error(f" Error Processing Event {e}")

    async def event_processed_loop(self):
        """Main Event Processing Loop"""

        logger.info("Event Processing Loop Started")

        while self.is_running:

            try:
                # Wait for event
                event = await asyncio.wait_for(
                  self.event_queue.get(),
                  timeout =5.0  
                ) 

                await self.process_event(event)
            except asyncio.TimeoutError:

                continue
            
            except Exception as e:
                logger.error(f" Error in Processing loop {e}")
                await asyncio.sleep(1)
    
    async def stats_reporter_loop(self):
        """Periodically Reports Stats"""
        logger.info("Stats reporter started")

        while self.is_running:

            try:
                await asyncio.sleep(300)

                # Update uptine
                if self.stats['start_time']:
                    self.stats['uptime_seconds'] = (
                        datetime.now() - self.stats['start_time']
                    ).total_seconds()

                    # Get global metrics
                    global_metrics = await self.shared_context.read("global_metrics")


                    # Log stats

                    logger.info(f"="*60)
                    logger.info("AUTONOMOUS SYSTEM STATS")
                    logger.info(f"Events Processed: {self.stats['events_processed']}")
                    logger.info(f"Agents Activated: {self.stats['agents_activated']}")
                    logger.info(f" {self.stats['uptime_seconds'] / 3600:.1f} hours")

                    if global_metrics:
                        logger.info("Today's global metrics")
                        logger.info(f"Scraped jobs {global_metrics.get('jobs_scraped_today', 0)}")
                        logger.info(f"Mateches created {global_metrics.get("'matches_created_today", 0)}")
                        logger.info(f" Reoirts Generated {global_metrics.get('reports_generated_today', 0)}")


                    # Fo Specific agents
                    for name , agent in self.agents.items():
                       logger.info(f" {name}")
                       logger.info(f" Completed: {agent.metrics['task_completed']}")
                       logger.info(f" Failed: {agent.metrics['task_failed']}")
                       logger.info(f" Last run {agent.metrics['last_run'] or 'never'}")

                    # Get Success rate from episodic memory
                    success_rate = self.episodic_memory.get_success_rate(name, "any")
                    logger.info(f"Success rate: {success_rate:.2%}")
                    logger.info(f" Last run{agent.metrics['last_run'] or 'never'}")
                    
                    logger.info("="*60)

            except Exception as e:
                logger.error(f"Stats Reporter Error{e}")
        
    async def health_check_loop(self):
        """Monitor System Health and restart Components"""
        logger.info("Health Checker Started")

        while self.is_running:

            try:
                await asyncio.sleep(60)

                    # Check if event Monitor is alive

                for name, agent in self.agents.items():
                    failure_rate = agent.metrics['task_failed']
                    total_tasks = agent.metrics['task_completed'] + agent.metrics['task_failed']

                    if total_tasks > 10 and failure_rate / total_tasks > 0.5:
                        logger.warning(f"{name} has a high failure rate {failure_rate}/{total_tasks}")

                        ## Get Learning from episodic memory
                        learning = self.episodic_memory.learn_from_failures(name)
                        logger.info(f" Recommendations {name}: {learning.get('recommendations', [])}")

            except Exception as e:
                logger.info(f"Health check error {e}")
    
    async def start(self):
        """Start the autonomous system"""
        logger.info("="*60)
        logger.info("Autonomous System Started")
        logger.info(f"="*60)
        
        self.is_running = True
        self.stats['start_time'] =datetime.now()

        ## Launch all tasks
        tasks = [
            asyncio.create_task(self.event_monitor.monitor_loop(self.event_queue)),
            asyncio.create_task(self.event_processed_loop()),
            asyncio.create_task(self.stats_reporter_loop()),
            asyncio.create_task(self.health_check_loop())
        ]

        logger.info("ALL Systems are Operational")
        logger.info(f" Active Agents {self.agents}")
        logger.info("Event Monitor: Active")
        logger.info("Decision Engine Active")
        logger.info("Episodic Memory: Active")
        logger.info("="*60)

        ## await for all tasks
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("Keyboard Interrupted")
        
        finally:
            await self.stop()

    async def stop(self):
        "Stop the autonomous System"

        logger.info("Stopping autonomous system")

        self.is_running = False

        ## Wait for agent to finish the current task
        await asyncio.sleep(2)

        logger.info("Autonomous System Stopped")
        logger.info(f" Final Stats")
        logger.info(f"Events Processed: {self.stats['events_processed']}")
        logger.info(f"Total Runtime {self.stats['uptime_seconds'] / 3600:.1f} Hours")

    def get_status(self):
        """Get Current System Status"""
        return {
            'is_running': self.is_running,
            'stats': self.stats,
            'agents': {
                name: {
                    'is_active': agent.is_active,
                    'metrics': agent.metrics,
                    'success_rate': self.episodic_memory.get_success_rate(name, "any")
                }
                for name, agent in self.agents.items()
            },
            'event_queue_size': self.event_queue.qsize(),
            'episodic_memory_size': len(self.episodic_memory.experiences)
        }

        







                


