from typing import TypedDict, List, Any, Annotated, Optional, Dict
from datetime import datetime
import operator



class AgentState(TypedDict):
    """
    Complete state for autonomous agent.
    Uses reducer annotations for list operations.

    """
    ## Task Management

    task: str
    task_type:str
    task_id:str
    priorities:int

    ### Reasoning chain
    plan: List[str]
    current_step: int
    reasoning_history: Annotated[List[Dict], operator.add]


    ### Data Collection:

    search_queries: Annotated[list[Dict], operator.add]
    search_results: Annotated[List[Dict], operator.add]
    scrape_content: Annotated[List[Dict], operator.add]


    ## Analysis

    extracted_insights: Annotated[List[Dict], operator.add]
    analysis_results: Dict

    ## Mmeory & content

    relevant_memories: List[Dict]
    enitity_content: Dict
    conversation_history: Annotated[List[Dict], operator.add]


    ## Reflection & Validation

    confidence_score: float
    validation_results: Dict
    errors: Annotated[List[str], operator.add]
    retry_count: int


   # Output


    final_output: Optional[str]
    artifacts: Annotated[List[Dict], operator.add]


   #  Meta

    iteration: int
    max_iteration: int
    started_at: datetime
    status:str

  # Resume Processung
    resume_text: Optional[str]
    resume_id: Optional[str]
    resume_embeddings: Optional[List[str]]

  # Job Search Parameters
    job_keywords: List[str]
    job_location: Optional[str]
    experience_level: Optional[str]
    scarepd_jobs_raw: Annotated[List[Dict], operator.add]

  # Job Data
    jobs_data: Annotated[List[Dict], operator.add]
    matched_jobs: List[Dict]

  # User Information
    user_email: Optional[str]
    user_id: Optional[str]

  # Quality check
    quality_check: Dict
    email_status: Dict

  # Report Generation
    report_data: Dict
    final_report: Optional[str]
    pdf_path: Optional[str]

  ## Memory & RAG Fields
    user_id: Optional[str]
    rag_context: Dict
    user_preferences: Dict
    similar_past_searches: List[Dict]


  ## ADVANCED REASONING
    resume_skills: Dict
    job_skills_analysis: List[Dict]
    skill_graph: Dict
    ranked_jobs: List[Dict]
    meta_reasoning: Dict

  ## Agentic Fileds

    goal_id: Optional[str]
    goal_achieved: bool
    goal_progress: float
    goal_reasoning: List[Dict]
    autonomous_cycle: int
    improvements_applied: List[Dict]
    routing_history: List[Dict]
    ranking_adjustments: Dict
    deep_skill_extraction: bool
    enable_alterbative_sources: bool
    learning_completed: bool
    last_executed_node: Optional[str]
   
    







