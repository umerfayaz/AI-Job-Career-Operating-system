import structlog


logger = structlog.get_logger()

class Models:
    def __init__(self, groq_client):
        self.client = groq_client

        self.models_routes = {
            "stretegic_reasoning": [
                "qwen/qwen3-32b",
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
            ],
            "cheap_json": [
                "llama-3.1-8b-instant",
                "qwen/qwen3-32b",
            ],
        }
    
    async def json_completion(self, task_type: str, messages:list, temperature: float = 0.2):
        models = self.models_routes.get(task_type, self.models_routes["cheap_json"])

        last_error = None

        for model in  models:
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    messages=messages
                )

                logger.warning(f"LLM Model called in Gateway:{model}")

                return {
                    "ok": True,
                    "model": model,
                    "content": response.choices[0].message.content,
                    "usage": getattr(response, "usage", None)
                }

            except Exception as e:
                last_error =e
                logger.warning(
                    "LLM model failed trying fallback",
                    model=model,
                    error=str(e)
                )
        
        return {
            "ok": False,
            "model": None,
            "content": None,
            "usage": None,
            "error": str(last_error)
        }


            


