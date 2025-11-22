from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from typing import List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
env_path = ROOT_DIR / ".env"

load_dotenv(env_path)

class Settings(BaseSettings):
    """
    Application Settings with environment variable Support
    """
    auto_start_autonomous: bool =False


    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False
    )

    # Email Config
    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: Optional[str] = None
    TO_EMAIL: Optional[str] = None
    CLIENT_ID: Optional[str] = None

    
    # Model Configuration
    SERPER_API_KEY: str
    PRIMARY_MODEL: str = "openai/gpt-oss-20b"
    GROQ_API_KEY: str
    RAPID_API_KEY: str
    FALLBACK_MODEL: str = "mixtral-8x7b"
    TEMPERATURE: float = 0.6
    MAX_TOKENS: int = 4096

    CHROMA: str = "./chroma_db"

    model_config = SettingsConfigDict(env_file_encoding= "utf-8", env_file = str(ROOT_DIR/ ".env"))
    # MCP Configuration
    MCP_WEB_RESEARCH_URL: str = "http://localhost:8001"
    MCP_DATABASE_URL: str = "http://localhost:8002"
    MCP_ANALYTICS_URL: str = "http://localhost:8003"
    MCP_COMMS_URL: str = "http://localhost:8004"

    # Database
    POSTGRES_URL: str = "postgresql://user:pass@localhost:5432/agent_db"
    REDIS_URL: str = "redis://localhost:6379"
    CHROMA_PATH: str = "./data/chroma"

    # Scheduling
    TASK_CHECK_INTERVAL: int = 60
    MAX_CONCURRENT_TASKS: int = 5
    DEFAULT_MAX_ITERATIONS: int = 10

    # Monitoring
    ENABLE_TELEMETRY: bool = True
    PROMETHEUS_PORT: int = 9090
    LOG_LEVEL: str = "DEBUG"

    # Agent Behavior
    MIN_CONFIDENCE_THRESHOLD: float = 0.75
    MAX_RETRY_ATTEMPTS: int = 3
    ENABLE_HUMAN_IN_LOOP: bool = False



if __name__ == "__main__":
    s = Settings()
    print(f"PRIMARY_MODEL: {s.PRIMARY_MODEL}")
    print(f"Has GROQ_API_KEY: {hasattr(s, 'GROQ_API_KEY')}")