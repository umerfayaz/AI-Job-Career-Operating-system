from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from typing import Optional
from pathlib import Path
# from dotenv import load_dotenv

# Get the root directory of the project
ROOT_DIR = Path(__file__).resolve().parents[2]
env_path = ROOT_DIR / ".env"

# load_dotenv(env_path)

class Settings(BaseSettings):
    """
    Application Settings with environment variable Support
    """
    
    # Application Control
    auto_start_autonomous: bool = False

    # Email Config
    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: Optional[str] = None
    TO_EMAIL: Optional[str] = None
    CLIENT_ID: Optional[str] = None
    DEFAULT_RECIPT_EMAIL: Optional[str] = None


    IMAP_SERVER: str
    IMAP_PORT: int 
    IMAP_FOLDER: str
    IMAP_EMAIL: str

    # API Keys
    SERPER_API_KEY: str
    GROQ_API_KEY: str
    RAPID_API_KEY: str

    # SLACK API URL 
    SLACK_WEBHOOK_URL: str
    
    # Model Configuration
    PRIMARY_MODEL: str = "llama-3.3-70b-versatile"
    FALLBACK_MODEL: str = "mixtral-8x7b"
    TEMPERATURE: float = 0.0
    MAX_TOKENS: int = 500

    # MCP Configuration
    MCP_WEB_RESEARCH_URL: str = "http://localhost:8001"
    MCP_DATABASE_URL: str = "http://localhost:8002"
    MCP_ANALYTICS_URL: str = "http://localhost:8003"
    MCP_COMMS_URL: str = "http://localhost:8004"

    # Database Configuration
    POSTGRES_URL: str = "postgresql://user:pass@localhost:5432/agent_db"
    REDIS_URL: str = "redis://localhost:6379"
    
    # ChromaDB Path - SINGLE DEFINITION
    # This creates a 'chroma_db' folder in your project root
    CHROMA_PATH: str = str(ROOT_DIR / "chroma_db")

    # Scheduling
    TASK_CHECK_INTERVAL: int = 60
    MAX_CONCURRENT_TASKS: int = 5
    DEFAULT_MAX_ITERATIONS: int = 10
    max_concurrent_agents: int =3
    
    # Monitoring
    ENABLE_TELEMETRY: bool = True
    PROMETHEUS_PORT: int = 9090
    LOG_LEVEL: str = "DEBUG"

    # Agent Behavior
    MIN_CONFIDENCE_THRESHOLD: float = 0.75
    MAX_RETRY_ATTEMPTS: int = 3
    ENABLE_HUMAN_IN_LOOP: bool = False

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # Observability
    OTLP_ENDPOINT: str = "http://localhost:4317"


if __name__ == "__main__":
    s = Settings()
    print(f"PRIMARY_MODEL: {s.PRIMARY_MODEL}")
    print(f"Has GROQ_API_KEY: {hasattr(s, 'GROQ_API_KEY')}")
    print(f"CHROMA_PATH: {s.CHROMA_PATH}")
    print(f"ROOT_DIR: {ROOT_DIR}")