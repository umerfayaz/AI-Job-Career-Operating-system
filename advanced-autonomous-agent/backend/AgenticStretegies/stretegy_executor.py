import structlog
from backend.core.event_bus import get_event_bus



event_bus = get_event_bus()
logger = structlog.get_logger()


class stretegyExecutor:

    def __init__(self,  shared_context, event_bus, outcome_database):
        self.shared_context = shared_context
        self.event_bus =  event_bus
        self.outcome_database = outcome_database
    
    async def execute(self, actions: dict, user_id: str, run_id:str):
        logger.warning("Starting stretegy executor agent")

        if actions.get("targeting_adjustment"):
            mode = actions["targeting_adjustment"]
            await self.shared_context.write(
                f"targeting_resume_{run_id}",
                {"mode": mode},
                "stretegy_executor"
            )
        
            await self.event_bus.emit({
                "type": "STRETEGY_TARGETING_UPDATED",
                "payload": {
                    "user_id": user_id,
                    "run_id": run_id,
                    "mode": mode
                }
            })

            logger.info("Stretgic Agent calling targeting resume function")
        
        if actions.get("resume_stretegy"):
            mode = actions["resume_stretegy"]
            await self.shared_context.write(
                f"apply_resume_stretegy_{run_id}",
                {"mode": mode},
                "stretegy_executor"
            )

            await self.event_bus.emit({
                "type": "STRETEGY_RESUME_UPDATED",
                "payload": {
                    "user_id": user_id,
                    "run_id": run_id,
                    "mode":mode
                }
            })

            logger.info("Stretgic Agent calling resume stretegy function")
        
        if actions.get("source_stretegy") == "shift":
            mode = actions["source_stretegy"]
            await self.shared_context.write(
                f"apply_source_stretegy_{run_id}",
                {"mode": mode},
                "stretegy_executor"
            )

            logger.warning(f"Shift stretegy reached in stretegy executor for: {run_id}")

            await self.event_bus.emit({
                "type": "STRETEGY_SOURCE_UPDATED",
                "payload": {
                    "user_id": user_id,
                    "run_id": run_id,
                    "mode": mode
                }
            })
        
        if actions.get("application_timing"):
            mode = actions["application_timing"]
            await self.shared_context.write(
                f"apply_timing_{run_id}",
                {"mode": mode},
                "stretegy_executor"
            )

            await self.event_bus.emit({
                "type": "STRETEGY_APPLICATION_UPDATED",
                "payload": {
                    "user_id": user_id,
                    "run_id": run_id,
                    "mode": mode
                }
            })

            logger.info("Stretegic Agent calling Application timing function")
        
        if actions.get("follow_up_stretegy") == "reminder":
            mode = actions["follow_up_stretegy"]
            await self.shared_context.write(
                f"apply_followup_stretegy_{run_id}",
                {"mode": mode},
                "stretegy_executor"
            )

            logger.warning(f"Followup reminder reached in stretegy executor for {run_id}")

            await self.event_bus.emit({
                "type": "STRETEGY_FOLLOWUP_UPDATED",
                "payload": {
                    "user_id": user_id,
                    "run_id": run_id,
                    "mode": mode
                }
            })

            logger.warning("Stretegic Agent is calling followup function")
    
        if actions.get("apply_volume"):
            mode = actions["apply_volume"]
            await self.shared_context.write(
                f"apply_volume_stretegy_{run_id}",
                {"mode": mode},
                "stretegy_executor"
            )

            await self.event_bus.emit({
                "type": "STRETEGY_VOLUME_UPDATED",
                "payload": {
                    "user_id": user_id,
                    "run_id": run_id,
                    "mode": mode
                }
            })

            logger.info("Stretegic Agent is calling apply volume function")

    
    

    


