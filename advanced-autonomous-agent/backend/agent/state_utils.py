

def normalize_state_lists(state: dict) -> dict:
    LIST_FIELDS = [
        "jobs_data",
        "matched_jobs",
        "reasoning_history",
        "errors",
        "search_results",
        "search_queries",
        "extracted_insights",
        "artifacts",
        "conversation_history",
        "scraped_content"
    ]

    DICT_FIELDS = [
        "analysis_results",
        "quality_check",
        "validation_results",
        "entity_context",
        "email_status",
        "report_data"
    ]

    
    for field in LIST_FIELDS:
        if field not in state or state[field] is None:
            state[field] = []


    for field in DICT_FIELDS:
        if field not in state or state[field] is None:
            state[field] = {}

    return state

