import structlog


logger = structlog.get_logger()
    
class ApplyTimingAgent:    
    def __init__(self, shared_context):
        self.shared_context = shared_context

    async def run(self, mode, user_id):

        logger.info(f"Starting apply timing function for {user_id}")
    
