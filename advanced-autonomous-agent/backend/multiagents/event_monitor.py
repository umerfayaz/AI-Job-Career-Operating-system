"""
EVENT MONITOR — Detect Triggers and Events
"""

import asyncio
import structlog
from datetime import datetime
from typing import Dict, Optional

logger = structlog.get_logger()


class EventMonitor:

    def __init__(self, memory_system):
        self.memory = memory_system
        self.last_job_count = 0
        self.last_resume_count = 0

    async def detect_new_resume(self) -> Optional[Dict]:
        """Check if a new resume was uploaded."""
        try:
            data = self.memory.resume_collection.get()
            current_count = len(data['ids']) if data else 0

            if current_count > self.last_resume_count:
                new_count = current_count - self.last_resume_count
                self.last_resume_count = current_count

                return {
                    'type': 'new_resume',
                    'new_count': new_count,
                    'timestamp': datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to detect new resume: {e}")

        return None

    async def detect_new_jobs(self) -> Optional[Dict]:
        """Check if new jobs are detected."""
        try:
            data = self.memory.jobs_posting_collection.get()
            current_count = len(data['ids']) if data else 0

            if current_count > self.last_job_count:
                new_count = current_count - self.last_job_count
                self.last_job_count = current_count

                return {
                    'type': 'new_jobs',   
                    'new_count': new_count,
                    'timestamp': datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to detect new jobs: {e}")

        return None

    async def detect_scheduled_trigger(self, interval: int = 1800) -> Dict:
        """Periodic scheduled trigger every 'interval' seconds."""
        return {
            'type': 'scheduled',
            'interval': interval,
            'timestamp': datetime.now().isoformat()
        }

    async def monitor_loop(self, event_queue: asyncio.Queue):
        """Continuous monitor loop that checks for events."""
        logger.info("Event Monitor Loop Started")

        while True:
            try:
                # 1. Check for new resume uploads
                event = await self.detect_new_resume()
                if event:
                    await event_queue.put(event)
                    logger.info(f"Event Detected: {event['type']}")

                # 2. Check for new job postings
                event = await self.detect_new_jobs()
                if event:
                    await event_queue.put(event)
                    logger.info(f"Event Detected: {event['type']}")

                # 3. Scheduled trigger
                event = await self.detect_scheduled_trigger()
                await event_queue.put(event)

                # Wait before next scan
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)


                


    

        



