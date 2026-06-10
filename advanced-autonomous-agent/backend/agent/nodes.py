from langchain_groq import ChatGroq
import numpy as np
from sentence_transformers import CrossEncoder
import os
import time
import structlog
from ..core.skills_extractor import SkillsExtractor
from ..core.memory_system import MemoryRAGSystem
from .state import AgentState
from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
from backend.multiagents.agents_team import SharedContext
from backend.retrieval.hybrid_retrival import HybridRetriever
from .scraper_engine import IntelligentJobScraper
from backend.core.stage_event import EmitStage
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
import json
import hashlib
import structlog
import re
import asyncio
from typing import Dict, List

logger = structlog.get_logger()

def convert_numpy_types(obj):
    """Convert numpy types to Python native types for serialization"""
    import numpy as np
    
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj

class AgentNodes:
    """
    All graph nodes implementing ReAct, Reflexion, and ToT patterns.
    """

    def __init__(self, agent_app, llm: ChatGroq, memory: MemoryRAGSystem):
        self.llm = llm
        self.agent_app = agent_app
        self.emit_stage = EmitStage()
        self.shared_context = SharedContext()
        self.embedding_model = None
        self.reranker_model = None
        self.memory_system  = memory
        
    def _get_reranker_model(self):

        logger.warning("Loading CrossEncoder")
        if self.reranker_model is None:
            self.reranker_model = CrossEncoder(
                "BAAI/bge-reranker-v2-m3"
            )
        logger.warning("CrossEncoder Loaded")
        
        return self.reranker_model

    def _calculate_display_score(self, job: Dict, all_jobs: List[Dict]) -> float:
      
        raw_rerank = job.get('rerank_score', 0)
        
       
        sigmoid = 1 / (1 + np.exp(-raw_rerank * 0.5))
        
        
        all_reranks = [j.get('rerank_score', 0) for j in all_jobs]
        rank = sorted(all_reranks).index(raw_rerank)
        percentile = rank / max(len(all_reranks) - 1, 1) 
        
     
        blended = (sigmoid * 0.4) + (percentile * 0.6)
        display = 0.55 + (blended * 0.40)  
        
        return round(display * 100, 1)

        
    def _extract_json(self, text: str) -> dict:
        """
        Extract JSON from LLM response that might be wrapped in markdown code blocks
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return {"error": "Could not parse JSON", "raw_text": text}

    # async def planner_node(self, state: AgentState, config) -> AgentState:
    #     """
    #     Plan: Break down tasks Into executable steps
    #     Uses chain of thoughts reasoning
    #     """
    #     system_prompt = """You are an expert planner for an autonomous AI agent.
    #     Given a task, break it down into concrete, actionable steps.
    #     Consider what information is needed, what tools to use, and validation steps.
        
    #     Output a JSON plan with:
    #     - steps: List of step descriptions
    #     - tools_needed: Tools required for each step
    #     - success_criteria: How to validate completion
    #     """

    #     messages = [
    #         SystemMessage(content=system_prompt),
    #         HumanMessage(content=f"Task: {state['task']}\nTask_type: {state['task_type']}")
    #     ]

    #     response = await self.llm.ainvoke(messages)
    #     data_plan = self._extract_json(response.content)

    #     state['plan'] = data_plan.get('steps', [])
        
    #     if 'reasoning_history' not in state:
    #         state['reasoning_history'] = []
            
    #     state['reasoning_history'].append({
    #         'node': 'planner',
    #         'action': 'plan',
    #         'content': data_plan,
    #         'run_id': state.get('run_id'),
    #         'timestamp': datetime.now().isoformat()
    #     })

    #     state = convert_numpy_types(state)

    #     return state

    # async def researcher_node(self, state: AgentState, config) -> AgentState:
    #     """
    #     ACT: Execute Web search using MCP server
    #     """

    #     if state['plan'] and len(state['plan']) > state['current_step']:
    #        current_step = state['plan'][state['current_step']]
        
    #     else:
    #         current_step = state.get('task', 'Research and analyze the given topic')

    #     logger.info(f"Researching Task: {current_step} ")

    #     query_prompt = f"""Generate 2-3 specific search queries for this research step:

    #     step: {current_step}
    #     context: {state['task']}

    #     Return only the queries as json ARRAY"""

    #     response = await self.llm.ainvoke([HumanMessage(content=query_prompt)])
    #     queries = self._extract_json(response.content)
    #     search_results = []

    #     for query in queries:
    #         try:
    #             results = await self.mcp['web_search'].tool_call(
    #                 tool= "web_search",
    #                 query= query,
    #                 max_tokens= 3
    #             )
    #             if isinstance(results, list):
    #                 search_results.extend(results)
    #             elif results:
    #                 search_results.append(results)
            
    #         except (AttributeError, KeyError, TypeError) as e:
    #             search_results.append({'error':str(e)})


    #     if isinstance(queries, list):
    #         state['search_queries'].extend(queries)
        
    #     else:
    #         state['search_queries'].append(queries)
        
    #     state['search_results'].extend(search_results)
    #     if 'reasoning_history' not in state:
    #         state['reasoning_history'] = []

    #     state['reasoning_history'].append({
    #         'node': 'researcher',
    #         'action': 'search',
    #         'queries': queries,
    #         'run_id': state.get('run_id'),
    #         'result_count': len(search_results),
    #         'timestamp': datetime.now().isoformat()
    #     })

    #     state = convert_numpy_types(state)

    #     return state

    # async def analyzer_node(self, state: AgentState, config) -> AgentState:
    #     """
    #     OBSERVE: Analyze collected data and extract insights.
    #     """
    #     analysis_prompt = f"""Analyze the following research results and extract key insights:

    #     Task: {state['task']}
    #     Search Results: {json.dumps(state['search_results'][-10:], indent=2) if state['search_results'] else 'No search results'}
    
    #     Extract:
    #     1. Key findings (list of strings)
    #     2. Patterns and trends (list of strings)
    #     3. Actionable insights (list of strings)
    #     4. Data quality assessment (string)
    
    #     IMPORTANT: Return ONLY valid JSON in this exact format:
    #    {{
    #        "key_findings": ["finding 1", "finding 2"],
    #         "patterns": ["pattern 1", "pattern 2"],
    #         "insights": ["insight 1", "insight 2"],
    #         "quality": "good/fair/poor"
    #     }}
    #     """
    
    #     try:
    #         response = await self.llm.ainvoke([
    #             SystemMessage(content="You are an expert data analyst. Return ONLY valid JSON."),
    #             HumanMessage(content=analysis_prompt)
    #         ])
    
    #         try:
    #             analysis = json.loads(response.content)
    #         except json.JSONDecodeError:
    #             logger.warning("Failed to parse LLM response as JSON, creating fallback analysis")
    #             analysis = {
    #                 "key_findings": [response.content[:500]],
    #                 "patterns": ["Analysis in progress"],
    #                 "insights": ["Further processing needed"],
    #                 "quality": "fair"
    #             }
    #         if not isinstance(analysis, dict):
    #             analysis = {
    #                 "key_findings": [str(analysis)],
    #                 "patterns": [],
    #                 "insights": [],
    #                 "quality": "fair"
    #             }
            
    #         analysis.setdefault('key_findings', [])
    #         analysis.setdefault('patterns', [])
    #         analysis.setdefault('insights', [])
    #         analysis.setdefault('quality', 'unknown')
            
    #         if self.mcp.get('database'):
    #             try:
    #                 await self.mcp['database'].store_insight(
    #                     task_id=state['task_id'],
    #                     insights=analysis.get('key_findings', []),
    #                     metadata={'timestamp': datetime.now().isoformat()}
    #                 )
    #             except Exception as e:
    #                 logger.warning(f"Failed to store insights in database: {e}")
            
    #         state['extracted_insights'].append(analysis)
    #         state['analysis_results'] = analysis
            
    #         insight_count = len(analysis.get('key_findings', []) or [])
            
    #         if 'reasoning_history' not in state:
    #             state['reasoning_history'] = []

    #         state['reasoning_history'].append({
    #             'node': 'analyzer',
    #             'action': 'ANALYZE',
    #             'run_id': state.get('run_id'),
    #             'insight_count': insight_count,
    #             'quality': analysis.get('quality', 'unknown'),
    #             'timestamp': datetime.now().isoformat()
    #         })
            
    #         logger.info(f"✅ Analysis completed: {insight_count} key findings")
            
    #     except Exception as e:
    #         logger.error(f"❌ Analyzer node error: {e}")
    #         state['errors'].append({
    #             'node': 'analyzer',
    #             'error': str(e),
    #             'timestamp': datetime.now().isoformat()
    #         })
            
    #         # Add fallback empty analysis
    #         state['analysis_results'] = {
    #             "key_findings": ["Analysis failed - using fallback"],
    #             "patterns": [],
    #             "insights": [],
    #             "quality": "poor"
    #         }

    #         state = convert_numpy_types(state)
        
    #     return state

    # async def reasoner_node(self, state: AgentState, config) -> AgentState:
    #     """
    #     Reflect: Meta-reasoning about progress and quality
    #     Implements Reflection Pattern
    #     """
    #     reflection_prompt = f"""Reflect on agent's progress:

    #     Task: {state['task']} 
    #     plan: {state['plan']}
    #     current_step: {state['current_step']+1}/{len(state['plan'])}
    #     Insights so far: {len(state['extracted_insights'])}
    #     Errors: {state['errors']}

    #     Evaluate:
    #     1. Is the Task on track
    #     2. Is the quality of insights sufficient
    #     3. Should we retry any steps
    #     4. Confidence score (0-1)
    #     5. Next action recommendation 

    #     Return JSON with evaluation"""

    #     response = await self.llm.ainvoke([
    #         SystemMessage(content="You are a meta-reasoning System evaluating agent performance"),
    #         HumanMessage(content=reflection_prompt)
    #     ])

    #     reflection = self._extract_json(response.content)

    #     state['confidence_score'] = reflection.get('confidence_score', 0.5)
    #     state['validation_results'] = reflection

    #     if 'reasoning_history' not in state:
    #         state['reasoning_history'] = []

    #     state['reasoning_history'].append({
    #         'node': 'reasoner',
    #         'action': 'REFLECT',
    #         'run_id': state.get('run_id'),
    #         'reflection': reflection,
    #         'timestamp': datetime.now().isoformat()
    #     })

    #     state = convert_numpy_types(state)

    #     return state

    # async def generator_node(self, state: AgentState, config) ->AgentState:
    #     """Generate final report with simple-tokens"""

    #     def trunacate_insights(insights, max_items=3):
    #         if not insights:
    #             return []
            
    #         return insights[-max_items]
        
    #     def summarize_results(results, max_length =2000):
    #         if not results:
    #             return []
            
    #         results_str = json.dumps(results, indent =2)
    #         if len(results_str) >max_length:
    #             if 'key_finings' in results:
    #                 return {'key_findings': results['key_findings'][:5]}
    #             return {'summary': results_str[:max_length] + '....(trunacated)'}

        
    #     condensed_insights = trunacate_insights(state['extracted_insights'], max_items =3)
    #     condensed_analysis = summarize_results(state['analysis_results'], max_length= 2000)


    #     search_results_text =""
    #     if state.get('search_results'):
    #         search_results_list = []
    #         for result in state['search_results'][-5:]:
    #             if isinstance(result, dict):

    #                 title = result.get('title', '')
    #                 content = result.get('content', '') or result.get('snipper', '') or result.get('descripiton', '')
    #                 url = result.get('url','')
    #                 search_results_list.append(f"{title}, {content}, {url}")
    #             else:
    #                 search_results_list.append(str(result))
    #         search_results_text = '\n'.join(search_results_list)


    #     generator_prompt = f""" Generate a comprehensive report based on the analysis:
        
        
    #     Task: {state['task']}

    #     Prepared by: {state.get('Umer Fayaz', 'Autonomous Agent')}
        
    #     key insights: {json.dumps(condensed_insights, indent=2)}
    #     analysis summary: {json.dumps(condensed_analysis, indent=2)}
    #     search results : {search_results_text}

        
    #     Generate a professional markdown report with Executive summary, Key findings, Analysis and Recommendations"""

    #     response = await self.llm.ainvoke([
    #         SystemMessage(content= "You are an expert business analyst"),
    #         HumanMessage(content= generator_prompt)
    #     ])

    #     reports = response.content

    #     state['final_output']=reports

    #     os.makedirs("reports",exist_ok=True)
    #     filename = f"reports {state['task_id']}_report.md"

    #     try:
    #         with open(filename, "w", encoding= 'utf-8') as f:
    #             f.write(reports)
    #         print(f"Report in {filename}")
    #     except Exception as e:
    #         print(f"failed to save file {e}")

        
    #     try:
    #         await self.mcp['database'].tool_call(
    #             tool_name = 'store_documents',
    #             collection_name = 'report',
    #             document = [reports],
    #             metadata = [{'task_id': state['task_id'], 'timestamp': datetime.now().isoformat()}],
    #             ids = [f"{state['task_id']}_report"]
    #         )
    #     except:
    #         pass


    #     state['final_report'] = reports
    #     state['artifacts'].append({
    #         'type': 'report',
    #         'content': reports,
    #         'filename': filename,
    #         'run_id': state.get('run_id'),
    #         'timestamp': datetime.now().isoformat()
    #     })

    #     state['status'] = 'completed'

    #     return state

            
    # async def memory_node(self, state: AgentState, config) -> AgentState:
    #     """ 
    #     Remember: Query and update long-term memory.
    #     """
    #     try:
    #         relevant_memories = await self.mcp['database'].tool_call({
    #             'tool': 'query_memory',
    #             'query': state['task'],
    #             'top_k': 5,
    #             'filters': {'task_type': state['task_type']}
    #         })
    #         state['relevant_memories'] = relevant_memories
    #     except (AttributeError, KeyError, TypeError) as e:
    #         state['relevant_memories'] = []

    #     if state['extracted_insights']:
    #         entities = []
    #         for insight in state['extracted_insights']:
    #             if 'entities' in insight:
    #                 entities.extend(insight['entities'])

    #         if entities:
    #             try:
    #                 await self.mcp['database'].tool_call({
    #                     'tool': 'update_entities',
    #                     'entities': entities,
    #                     'task_id': state['task_id']
    #                 })
    #             except (AttributeError, KeyError, TypeError) as e:
    #                 pass


    async def job_planner_node(self, state: AgentState, config) -> AgentState:
        """Enhanced Planner specifically for job matching tasks"""

        with tracer.start_as_current_span("planner_node.state") as parent_span:
            planner_node = time.time()
            parent_span.set_attribute("planner", "node")
            user_id = state.get("user_id")
            stretegy = {}

            await self.emit_stage.emit_staging_start(
                run_id=state.get("run_id"),
                stage="planning",
                message="Analyzing your experience and skills..."
            )

            system_prompt = """You are an expert job search strategist with deep knowledge of applicant tracking systems (ATS), industry hiring patterns, and job market dynamics.

            Given a resume and job preferences, create a comprehensive, targeted job search strategy that maximizes relevant opportunities.

            ANALYZE:
            1. **Profile Assessment**
            - Core skills and technical competencies
            - Years of experience and seniority level
            - Industry background and domain expertise
            - Career trajectory and growth areas
            - Unique value propositions and differentiators

            2. **Market Positioning**
            - Job titles that match experience (exact, adjacent, and aspirational)
            - Industries with highest demand for this profile
            - Geographic markets with concentration of relevant opportunities
            - Salary ranges aligned with experience and location
            - Remote vs on-site vs hybrid suitability

            3. **Search Optimization**
            - Primary keywords (hard skills, technologies, certifications)
            - Secondary keywords (soft skills, methodologies, tools)
            - Boolean search combinations for maximum coverage
            - Negative keywords to filter out irrelevant results
            - Alternative terminology used across different industries

            4. **Platform Strategy**
            - Mainstream job boards (LinkedIn, Indeed, Glassdoor)
            - Niche/specialized platforms for specific industries or roles
            - Company career pages for target employers
            - Startup job boards (AngelList, Wellfound) if applicable
            - Remote-first platforms (Remote.co, We Work Remotely) if relevant
            - Industry-specific boards and professional association sites

            5. **Application Approach**
            - Daily application targets and time allocation
            - Priority tiers for opportunities (dream → stretch → solid fit → backup)
            - Networking strategies (alumni networks, LinkedIn connections, industry events)
            - Direct outreach vs application portal recommendations
            - Timeline expectations and follow-up cadence

            """

            resume_snippet = state.get('resume_text','')[:500] if state.get('resume_text') else ''

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"""
                Resume  (snippet) {resume_snippet}

                Task: {state['task']}
                User Preferences
                - Location : {state.get('job_location', 'Any')}
                - Experience {state.get('experience_level', 'Any')}
                - keywords {state.get('job_keywords', 'Any')}

                Retuen only valid JSON

                Schema:
                {{
                "job_keywords": [
                    "python",
                    "fastapi"
                ],
                "steps": [
                    "Scrape jobs from source",
                    "Match resume with jobs",
                    "Generate report",
                    "Send email"
                ]
                }}

                Rules:
                - No markdown
                - No explanations
                - No code fences
                - No extra text
                - Output must be parseable by json.loads()

                
                Create a search stretegy""")
            ]
        
            
            await self.emit_stage.emit_staging_done(
                    run_id=state.get("run_id"),
                    stage="planning"
                )
            

            await self.emit_stage.emit_staging_start(
                run_id=state.get("run_id"),
                stage="building_stretegy",
                message="Building a personalized job stretegy..."
            )

            try:  
                with tracer.start_as_current_span("llm.response") as llm_span:
                    llm_latency = time.time()
                    llm_span.set_attribute("llm.model", "openai/gpt-oss-120b")
                    llm_span.set_attribute("llm.temperature", 0.2)

                    response = await self.llm.ainvoke(messages)
                    stretegy = json.loads(response.content)

                    llm_span.set_attribute("llm.latency_seconds", time.time() - llm_latency)


                    usage = getattr(response, "usage", None)

                    if usage:
                        llm_span.set_attribute("llm.prompt", str(messages[:500]))
                        llm_span.set_attribute("llm.prompt_tokens", getattr(usage , "prompt_tokens", 0))
                        llm_span.set_attribute("llm.completion_tokens", getattr(usage, "completion_tokens", 0))
                        llm_span.set_attribute("llm.total_tokens", getattr(usage, "total_tokens", 0))

                        # Cost of LLM Model Tracking
                        total_tokens = getattr(usage, "total_tokens", 0)
                        model_cost = {
                            "openai/gpt-oss-120b": 0.0001
                        }
                        cost=(total_tokens / 1000) * model_cost.get("openai/gpt-oss-120b", 0)

                        llm_span.set_attribute("llm.estimated_cost_usd", cost)
            
            except Exception as e:
                if "llm_span" in locals():
                    llm_span.record_exception(e)
                    llm_span.set_status(Status(StatusCode.ERROR, str(e)))
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
            
            
            await self.emit_stage.emit_staging_done(
                run_id=state.get("run_id"),
                stage="building_stretegy",
            )

            if 'run_id' not in state or not state.get('run_id'):
                logger.warning('run id is missing in job scraper node')
                if hasattr(self, 'agent_app') and self.agent_app.multi_agent_orchestrator:
                    run_id = await self.agent_app.multi_agent_orchestrator.shared_context.read(f"current_run_id_{user_id}")
                    if run_id:
                        state['run_id'] = run_id
                        logger.info(f"Retrieved run_id {run_id}")

            state['job_keywords'] = stretegy.get('job_keywords', state.get('job_keywords', []))
            state['plan'] = stretegy.get('steps', [
                "Scrape jobs from source",
                "Match resume with jobs",
                "Genrate report",
                "Send email"
            ])

            if 'reasoning_history' not in state:
                state['reasoning_history'] = []

            state['reasoning_history'].append({
                'node': 'job_planner',
                'action': 'job_search_strategy',
                'keywords_count': len(stretegy.get("job_keywords", [])),
                'steps_count': len(stretegy.get("steps", [])),
                'run_id': state.get('run_id'),
                'timestamp': datetime.now().isoformat()
            })

            logger.info(f"Job stretegy created: {len(state['job_keywords'])}keywords")

            state = convert_numpy_types(state)

            parent_span.set_attribute("planner_node.latency_seconds", time.time() - planner_node)
        
            return state

    async def job_scraper_node(self, state: AgentState, config) -> AgentState:
        """
        ENHANCED: Multi-source intelligent scraper (no API keys needed).
        """

        with tracer.start_as_current_span("job_scraper.state") as parent_span:
            start_scraper = time.time()
            parent_span.set_attribute("scraper", "node")

            try:
                user_id = state.get("user_id")
                keywords = state.get("job_keywords")
                location = state.get("job_location")
                preferred_source = "JSearch"
                mode = "default"
                run_id = state.get("run_id")
                source_config = None
                workflow_type = state.get("workflow_type", "frontend_workflow") 

                unique_jobs = []
                cached_jobs = None

                shared_context = self.agent_app.multi_agent_orchestrator.shared_context

                logger.error(f"""
                    SCRAPER ATTEMPTING READ
                    STATE_RUN_ID: {run_id}
                    KEY: job_source_config_{run_id}
                    """)
                
                if workflow_type == "autonomous_workflow":  
                    source_config = await shared_context.read(f"job_source_config_{run_id}")
                    logger.warning(f"Scraper node recieved config : {source_config}")
                
                if not source_config:
                    logger.warning("No Config Found in source agent, Using Default keywords")

                
                logger.error(f"""
                    SCRAPER READ RESULT
                    RUN_ID: {run_id}
                    CONFIG: {source_config}
                """)
                
                if source_config:
                    mode = source_config.get("mode", "default")
                    source_type = source_config.get("source")
                    preferred_source = source_config.get("preferred_source", "JSearch")
                    logger.warning(f"final preferred source inside scraper: {preferred_source}")

                    if source_type == "agent":
                        keywords = source_config.get('keywords', keywords)
                        location = source_config.get('location', location)

                        state["job_keywords"] = keywords
                        state["job_location"] = location

                        logger.info(f"SCRAPER USING KEYWORDS",
                            keywords=keywords,
                            location=location
                        )
                    
                    logger.warning(f"""Final Config Called in Srcaper Node,
                        keywords : {keywords},
                        location : {location},
                        preferred_source : {preferred_source}",
                        mode: {mode}
                """)
                
                search_key = f"{','.join(keywords[:3])}_{location}".lower().replace(' ', '_')

                # Check cache logic stays the same
                try:
                    search_marker = f"search_{search_key}"
                
                    cached_jobs = self.agent_app.memory.job_collection.get(
                        where= {
                            "$and": [
                                {"search_key": search_key},
                                {"run_id": run_id},
                                {"is_fresh": True}
                            ]
                        },
                        limit=50
                    )

                    if cached_jobs and cached_jobs.get("metadatas"):
                        state['jobs_data'] = [
                            {
                                "title": meta.get("job_title"),
                                "company": meta.get("company"),
                                "description": meta.get("description"),
                                "url": meta.get("url"),
                                "location": meta.get("location"),
                                "salary": meta.get("salary_range"),
                                "source": meta.get("source"),
                                "cached": True
                            }
                            for meta in cached_jobs["metadatas"]
                        ]

                        logger.info(f" Loaded {len(state['jobs_data'])} cached jobs")
                        return state
                
                except:
                    pass
            
                if not keywords:
                    resume_text = state.get('resume_text', '')
                    if resume_text:
                        keyword_prompt = f"""Extract 3-5 job search keywords from this resume:
                        {resume_text[:1000]}
                        
                        Return only a JSON array of keywords."""
                        
                        response = await self.llm.ainvoke([HumanMessage(content=keyword_prompt)])
                        keywords = self._extract_json(response.content)
                        if isinstance(keywords, list):
                            state['job_keywords'] = keywords
                
                existing_jobs = state.get('jobs_data', [])
                retry_count = state.get('retry_count', 0)

                # Fallback sample jobs logic
                if retry_count >= 2 and len(existing_jobs) == 0:
                    logger.warning(f" Retry count {retry_count} - Creating fallback sample jobs")
                    fallback_jobs = self._create_sample_jobs(keywords, location)
                    state['jobs_data'] = fallback_jobs

                    if 'reasoning_history' not in state:
                        state['reasoning_history'] = []

                    state['reasoning_history'].append({
                        'node': 'job_scraper',
                        'action': 'fallback_sample_data',
                        'reason': 'Multiple Job failures',
                        'run_id': state.get('run_id'),
                        'jobs_created': len(fallback_jobs),
                        'timestamp': datetime.now().isoformat()
                    })

                    return state

                if len(existing_jobs) > 100:
                    logger.warning(f" Already have {len(existing_jobs)} - skipping scraper to avoid explosion")
                    return state

                logger.info(f"🚀 Launching intelligent multi-source scraper")
                logger.info(f"🔍 Keywords: {keywords}")
                logger.info(f"📍 Location: {location}")
                
                try:

                    shared_context = self.agent_app.multi_agent_orchestrator.shared_context
                    event_bus = self.agent_app.multi_agent_orchestrator.event_bus

                    await self.emit_stage.emit_staging_start(
                        run_id=state.get("run_id"),
                        stage="calling_job_api",
                        message="Searching accross multiple job platforms...."
                    )
                
                    async with IntelligentJobScraper(shared_context, event_bus) as scraper:
                        jobs = await scraper.scrape_all_sources(
                            keywords=keywords,
                            run_id=run_id,
                            location=location,
                            max_results=50,
                            preferred_source=preferred_source
                        )

                    # Popping Source agent Config key
                    if workflow_type == "autonomous_workflow" and source_config:
                        await self.shared_context.pop(f"job_source_config_{run_id}")
                        logger.warning(f"Popping jobs Source config key:{run_id}")

                    await self.emit_stage.emit_staging_done(
                        run_id=state.get("run_id"),
                        stage="calling_job_api"
                    )

                    unique_jobs = []
                    seen = set()
                    for job in jobs:
                        job_key = hash((job.get("title"), job.get("company"), job.get("location")))
                        if job_key not in seen:
                            seen.add(job_key)
                            unique_jobs.append(job)
                    
                    try:
                        stored_count = await self.agent_app.memory.store_jobs(
                            unique_jobs,
                            {
                                "run_id": run_id,
                                "search_key": search_key
                            }
                        )
                        logger.info(f" Stored {stored_count} job count in memory for run_id={run_id}")
                    
                    except Exception as e:
                        logger.error(f"Failed storing jobs in memory {e}")
                        state["errors"].append(f"Memory stored jobs failed {str(e)}")
                
                    if retry_count > 0:
                        logger.warning(f"⚠️ Retry {retry_count} - Replacing old jobs with new ones")
                        state['jobs_data'] = unique_jobs
                    else:
                        state['jobs_data'].extend(unique_jobs)

                    if 'reasoning_history' not in state:
                        state['reasoning_history'] = []

                    state['reasoning_history'].append({
                        'node': 'job_scraper',
                        'action': 'intelligent_multi_source_scrape',
                        'sources': ['google_search', 'indeed_direct', 'remoteok', 'hackernews'],
                        'jobs_found': len(unique_jobs),
                        'run_id': state.get('run_id'),
                        'keywords': keywords,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    logger.info(f"Intelligent scraper found {len(unique_jobs)} unique jobs")
                    logger.info(f" Total jobs in state: {len(state['jobs_data'])}")

                    if not state.get('run_id'):
                        logger.error("❌ CRITICAL: Lost run_id after scraping!")
                        state['run_id'] = run_id  # Restore it
                        logger.info(f" Restored run_id: {run_id}")

                
                    if len(unique_jobs) > 0:
                        try:
                            search_marker = f"search_{search_key}"
                            self.agent_app.memory.job_collection.add(
                                ids=[search_marker],
                                documents=[f"Search completed: {keywords[:3]} in {location}"],
                                metadatas=[{
                                    "type": search_marker,
                                    "keywords": ",".join(keywords[:3]),
                                    "location": location,
                                    "searched_at": datetime.now().isoformat(),
                                    "jobs_found": len(unique_jobs)
                                }]
                            )
                            logger.info(f" Marked search completed: {search_key}")
                        except Exception as e:
                            logger.warning(f" Failed to mark search: {e}")
                    
                    # Log sample job URLs
                    logger.info("📋 Sample job URLs:")
                    for i, job in enumerate(unique_jobs[:3], 1):
                        url = job.get('url') or job.get('apply_url') or job.get('job_apply_link')
                        logger.info(f"   {i}. {job.get('title')} -> {url or 'No URL'}")

                    # Handle empty results
                    if len(unique_jobs) == 0 and retry_count < 3:
                        logger.warning(f"No jobs found - retry {retry_count + 1}/3")
                        state['retry_count'] = retry_count + 1
                    
                except Exception as e:
                    logger.error(f" Intelligent scraper failed: {e}")
                    state['errors'].append(f"Scraping error: {str(e)}")
                    
                    # Fallback to sample data if completely failed
                    if len(state.get('jobs_data', [])) == 0:
                        logger.warning(f" Using fallback sample data")
                        unique_jobs = self._create_sample_jobs(keywords, location)
                        state['jobs_data'] = unique_jobs

            
                final_run_id = state.get('run_id')
                if not final_run_id:
                    logger.error(" CRITICAL: run_id missing at end of job_scraper_node!")
                    state['run_id'] = run_id  
                    logger.info(f" Restored run_id at end: {run_id}")
                else:
                    logger.info(f" run_id confirmed at end of scraper: {final_run_id}")

                # Convert numpy types
                state = convert_numpy_types(state)

                parent_span.set_attribute("scraper.run_id", run_id)
                parent_span.set_attribute("scraper.workflow_type", workflow_type)
                parent_span.set_attribute("scraper.preferred_source", preferred_source)
                parent_span.set_attribute("scraper.jobs_found", len(unique_jobs))
                parent_span.set_attribute("scraper.retry_count", retry_count)

                parent_span.set_attribute("scraper.cache_hit", bool(cached_jobs and cached_jobs.get("metadatas")))
                parent_span.set_attribute("scraper.cached_job_count", len(cached_jobs.get("metadatas", [])) if cached_jobs else 0)
                parent_span.set_attribute("scraper.success", len(unique_jobs) > 0)
                return state

            except Exception as e:
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                return state

            finally:
                parent_span.set_attribute("scraper.latency_seconds", time.time() - start_scraper)


    def _create_sample_jobs(self, keywords: List[str], location: str,) ->List[Dict]:
        """
        FALLBACK: create sample jobs for testing
        """
        sample_jobs = []

        for i, keyword in enumerate(keywords[:3], 1):
            sample_jobs.append({
                'title': f"{keyword}  Senior position",
                'company': f"Tech Company {i}",
                'description': f"We are looking for a  experinced {keyword} professional Remote Friendly , competitive salary great benefits",
                'url': f"https://exmaple.com/job/{i}",
                'location': location,
                'salary': '$50k-$150k',
                'source': 'fallback_jobs',
                'fallback': True,
                'scraped_at': datetime.now().isoformat()            
            })
        return sample_jobs


    async def job_matcher_node(self, state: AgentState, config) ->AgentState:
        """"Matches Jobs using embedding-based simialrity"""

        #Tracing matcher with Opentelemty
        with tracer.start_as_current_span("matcher_node.state") as parent_span:
            start_matcher = time.time()
            parent_span.set_attribute("matcher", "node" )

            try:
                resume_text = state.get('resume_text')
                user_id = state.get("user_id")
                jobs = state.get('jobs_data',[])
                run_id = state.get('run_id')

                if not run_id:
                    logger.info("No run_id - No match")
                    state['matched_jobs'] = []
                    return state

                fresh_jobs = self.agent_app.memory.job_collection.get(
                    where = {
                        "$and": [
                            {"run_id": run_id},
                            {"is_fresh": True}
                        ]
                    },
                    limit =100,
                    include = ["metadatas", "documents"]
                )
                
                if not fresh_jobs or not fresh_jobs.get("ids"):
                    logger.warning(f"No fresh jobs found for run_id {run_id}")
                    state['matched_jobs'] = []
                    return state
                
                jobs = []
                for idx, job_id in enumerate(fresh_jobs["ids"]):
                    metadata = fresh_jobs["metadatas"][idx]
                    jobs.append({
                        "id": job_id,
                        "title": metadata.get("job_title", ""),
                        "company": metadata.get("company", ""),
                        "description": metadata.get("description", ""),
                        "url": metadata.get("url", ""),
                        "location": metadata.get("location", ""),
                        "salary": metadata.get("salary_range", ""),
                        "source": metadata.get("source", ""),
                        "skills": metadata.get("skills", []),
                        "experience": metadata.get("experience", "")
                    })
                

                if not resume_text:
                    logger.warning(f"No resume text found, Skipping matching")
                    state['matched_jobs'] = jobs[:10] if jobs else []
                    return state
                
                if not jobs:
                    logger.warning("No match jobs found")
                    state['errors'].append("No jobs match found")
                    return state
                
                if len(jobs) > 200:
                    logger.info(f" Too many jobs ({len(jobs)}) Sampling 200 for matching")

                    jobs = jobs[:200]
                
                logger.info(f" Matching resume within {len(jobs)}")

                await self.emit_stage.emit_staging_start(
                            run_id=state.get("run_id"),
                            stage="matching_resume",
                            message="Finding best matches for your profile...."
                        )

                # Tracing emebedding with opentelemetry
                with tracer.start_as_current_span("matcher.embeddings") as embed_span:
                    start_embed =  time.time()
                    
                    try:
                        reranker_model = self._get_reranker_model()

                        logger.warning(f"Resume matcher node model type: {type(self.memory_system.embedding_model)}")

                        hybrid_retriever = HybridRetriever(
                            self.memory_system.embedding_model,
                            reranker_model
                        )
    
                        canidate_jobs = hybrid_retriever.retrieve(
                            resume_text=resume_text,
                            user_id=user_id,
                            jobs=jobs,
                            top_k=30
                        )

                        logger.warning(f" Hybrid returned {len(canidate_jobs)} jobs")

                        matched_jobs = []
                        seen_job_urls = set()

                        for job in canidate_jobs:
                            job = job.copy()

                            job_url = job.get("url", "")

                            if job_url and job_url in seen_job_urls:
                                continue

                            if job_url:
                                seen_job_urls.add(job_url)
                            
                            rrf_score = float(job.get("rrf_score", 0))
                            dense_score = float(job.get("dense_score", 0))
                            rerank_score = float(job.get("rerank_score", 0))

                            job["rrf_score"] = rrf_score
                            job["dense_score"] = dense_score
                            job["rerank_score"] = rerank_score

                            job["match_percentage"] = self._calculate_display_score(job, canidate_jobs)

                            job = convert_numpy_types(job)

                            matched_jobs.append(job)

                        await asyncio.sleep(0.3)

                        await self.emit_stage.emit_staging_done(
                            run_id=state.get("run_id"),
                            stage="matching_resume"
                        )

                        for job in matched_jobs:
                            job['rerank_score'] =float(job.get('rerank_score', 0))
                            job['match_percentage'] = float(job.get('match_percentage', 0))

                        state['matched_jobs'] = matched_jobs

                        logger.info("\n" + "="*70)
                        logger.info("MATCHED JOBS DETAILS")
                        logger.info("="*70)

                        for i, job in enumerate(matched_jobs[:5], 1):  
                            logger.info(f"\n{i}. {job.get('title', 'N/A')}")
                            logger.info(f"   Company: {job.get('company', 'N/A')}")
                            logger.info(f"   Location: {job.get('location', 'N/A')}")
                            logger.info(f"   Salary: {job.get('salary', 'N/A')}")
                            logger.info(f"   Match: {job.get('match_percentage', 0):.0f}%")
                            logger.info(f"   Source: {job.get('source', 'N/A')}")
                            
                            desc = job.get('description', 'N/A')[:200]
                            logger.info(f"   Description: {desc}...")
                            
                            tags = job.get('tags', [])
                            if tags:
                                logger.info(f"   Skills: {', '.join(tags[:5])}")
                            
                            logger.info(f"   Apply: {job.get('url', 'N/A')}")

                        logger.info("\n" + "="*70)

                        avg_score = float(np.mean([j['match_percentage'] for j in matched_jobs ])) if matched_jobs else 0
                        state['confidence_score'] = avg_score

                        if 'reasoning_history' not in state:
                            state['reasoning_history'] = []

                        state['reasoning_history'].append({
                            'node': 'job_matcher',
                            'action': 'matched_jobs',
                            'total_jobs': len(jobs),
                            'matched': len(matched_jobs),
                            'run_id': state.get('run_id'),
                            'avg_score': avg_score,
                            'timestamp': datetime.now().isoformat()
                        })

                        logger.info(f"Matched {len(matched_jobs)} avg score: {avg_score:.2f}")

                        logger.info("\n" + "="*70)
                        logger.info("📋 TOP MATCHED JOBS PREVIEW")
                        logger.info("="*70)

                        for i, job in enumerate(matched_jobs[:3], 1):  
                            logger.info(f"\n{i}. {job.get('title', 'N/A')}")
                            logger.info(f"   🏢 {job.get('company', 'N/A')}")
                            logger.info(f"   📍 {job.get('location', 'N/A')}")
                            logger.info(f"   💰 {job.get('salary', 'N/A')}")
                            logger.info(f"   🎯 Match: {job.get('match_percentage', 0):.0f}%")
                            
                            desc = job.get('description', '')[:150]
                            logger.info(f"   📝 {desc}...")
                            
                            tags = job.get('tags', [])
                            if tags:
                                logger.info(f"   🏷️ {', '.join(tags[:5])}")

                        logger.info("\n" + "="*70 + "\n")

                        embed_span.set_attribute("embed.job_count", len(jobs))
                        embed_span.set_attribute("embed.canidate_count", len(canidate_jobs) )
                        embed_span.set_attribute("embed.success", True)

                    except Exception as e:
                        embed_span.record_exception(e)
                        embed_span.set_status(Status(StatusCode.ERROR, str(e)))

                        logger.error(f"Job matching error {e}")
                        state['errors'].append({
                            'node': 'job_matcher',
                            'error': str(e),
                            'timestamp': datetime.now().isoformat()
                        })
                        state['matched_jobs'] = jobs[:10]
                        state = convert_numpy_types(state)

                        return state

                    finally:
                        embed_span.set_attribute("embed.latency_seconds", time.time() - start_embed)
            
                parent_span.set_attribute("matcher.user_id", str(user_id))
                parent_span.set_attribute("matcher.job_count", len(jobs))
                parent_span.set_attribute("matcher.matched_count", len(matched_jobs))
                parent_span.set_attribute("matcher.avg_score", avg_score)
                parent_span.set_attribute("matcher.success", len(matched_jobs) > 0)
                return state

            except Exception as e:
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                return state

            finally:
                parent_span.set_attribute("matcher.latency_seconds", time.time() - start_matcher)

    async def job_quality_checker_node(self, state: AgentState, config) ->AgentState:
        """Quality Check for the job matching results"""

        matched_jobs = state.get('matched_jobs', [])

        quality_check = {
            'passed': True,
            'issues': [],
            'recommendations':[],
            'quality_score': 1.0
        }

        if len(matched_jobs) <5:
            quality_check['passed'] =True
            quality_check['issues'].append(f"Only {len(matched_jobs)} jobs found (need 5+)")
            quality_check['recommendations'].append("Expand search keywords or location")
            quality_check['quality_score'] -= 0.3

        if matched_jobs:
            avg_score = float(sum(j.get('match_percentage', 0) for j in matched_jobs ) / (len(matched_jobs)))
            if avg_score <0.3:
                quality_check['passed'] = False
                quality_check['issues'].append(f"Low match score (avg:{avg_score:.2f})")
                quality_check['recommendations'].append("Redefine resume or broader job search")
                quality_check['quality_score'] -= 0.2
            else:
                quality_check['quality_score']= min(1.0, avg_score + 0.3)

        incomplete = sum (1 for j in matched_jobs if not j.get('description'))
        if incomplete > len(matched_jobs) / 2:
            quality_check['issues'].append(f"{incomplete} job missing description")
            quality_check['quality_score'] -= 0.1
        
        await self.emit_stage.emit_staging_start(
            run_id=state.get("run_id"),
            stage="quality_checking",
            message="checking matching result's quality..."
        )

        await asyncio.sleep(3.0)

        quality_check['quality_score'] = max(0.0, min(1.0, quality_check['quality_score']))

        state['quality_check']= quality_check
        state['validation_results']['quality_check'] = quality_check

        await asyncio.sleep(0.2)
          
        await self.emit_stage.emit_staging_done(
            run_id=state.get("run_id"),
            stage="quality_checking"
        )
        
        if not quality_check['passed']:
            state['confidence_score'] = min(state.get('confidence_score', 0.5), quality_check['quality_score'])

        if 'reasoning_history' not in state:
            state['reasoning_history'] =[]

        state['reasoning_history'].append({
            'node': 'job_quality_checker',
            'action': 'quality_check',
            'passed': quality_check['passed'],
            'run_id': state.get('run_id'),
            'score': quality_check['quality_score'],
            'issues': len(quality_check['issues']),
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"Quality check {quality_check['quality_score']:.2f} ) -"
             f"{'PASSED' if quality_check['passed'] else 'FAILED'}")
        
        state = convert_numpy_types(state)
        
        return state
    
    async def job_report_generator_node(self, state: AgentState, config) -> AgentState:
        """Generate Job matching report"""

        matched_jobs = state.get('matched_jobs', [])
        resume_text = state.get('resume_text', '')[:500] if state.get('resume_text') else ''

        if not matched_jobs or len(matched_jobs) == 0:
            logger.warning("⚠️ No matched jobs - generating fallback report")
            
            report = f"""# Job Match Report - No Results Found

    ## Summary
    Unfortunately, we were unable to find matching jobs at this time.

    ### Resume Summary
    {resume_text}

    ### What Happened
    The job scraping process completed but did not return any matching positions. This could be due to:
    - Temporary network issues
    - Rate limiting from job boards
    - Very specific search criteria
    - Limited job availability

    ### Recommendations
    1. **Broaden your search**: Try adding more keywords or alternative job titles
    2. **Expand location**: Consider additional locations beyond "{state.get('job_location', 'N/A')}"
    3. **Adjust filters**: Try different experience levels or industries
    4. **Try again later**: Job boards update frequently
    5. **Visit job sites directly**: Check LinkedIn, Indeed, Glassdoor manually

    ### Next Steps
    - Retry the search with different keywords
    - Consider related roles (e.g., "Data Scientist", "ML Researcher", "AI Developer")
    - Set up job alerts on major platforms

    ---
    *Note: This is a fallback report. The system will work on improving job discovery.*
    """
            
            state['final_output'] = report
            state['final_report'] = report
            state['report_data'] = {
                'report_text': report,
                'matched_jobs': [],
                'timestamp': datetime.now().isoformat(),
                'fallback': True
            }
            state['status'] = 'completed_with_warnings'


            if 'reasoning_history' not in state:
                state['reasoning_history'] = []
            
            state['reasoning_history'].append({
                'node': 'job_report_generator',
                'action': 'generate_fallback_report',
                'jobs_included': 0,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info("📄 Fallback report generated")
            return state

        report_prompt = f"""Generate a professional job matching report:

        Resume Summary {resume_text}

        Found {len(matched_jobs)} Matching jobs

        Top matches:
        {json.dumps(matched_jobs[:5], indent=2)}

        Create a report with:
        # job match report

        ## Exective summary
        [Overview of matches]

        ## Top 10 Opportunities
        [Detailed list with job matches]

        ## Recommendations
        [Career advice and next steps]

        ## Application Tips
        [Tailored Advice]

        Use professioanal markdown report"""

        response = await self.llm.ainvoke([
            SystemMessage(content="You are an expert career adviser and recruiter."),
            HumanMessage(content=report_prompt)
        ])

        report = response.content

        ## ADD Job detailed sections with FULL DETAILS
        job_details = "\n\n## 📋 Detailed Job Matches\n\n"

        for i, job in enumerate(matched_jobs[:10], 1):
            title = job.get('title', 'N/A')
            company = job.get('company', 'N/A')
            location = job.get('location', 'N/A')
            salary = job.get('salary', 'Not specified')
            match_pct = job.get('match_percentage', 0)
            composite = job.get('composite_score', 0)
            url = job.get('url', '#')
            source = job.get('source', 'N/A')
            job_type = job.get('job_type', 'N/A')
            
            description = job.get('description', 'No description available')
    
            tags = job.get('tags', [])
            tags_str = ', '.join(tags[:8]) if tags else 'Not specified'
            
            reasoning = job.get('ranking_reasoning', {})
            why_good = reasoning.get('why_good_fit', [])
            concerns = reasoning.get('potential_concerns', [])
            recommendations = job.get('recommendations', 'Review')
            
            job_details += f"""
        ---

        ### Job #{i}: {title}

        **🏢 Company:** {company}  
        **📍 Location:** {location}  
        **💰 Salary:** {salary}  
        **⏰ Type:** {job_type}  
        **🎯 Match Score:** {match_pct:.0f}% | Quality: {composite:.2f}  
        **🔗 Source:** {source}  

        **Apply Here:** {url}

        #### 📝 Job Description
        {description}

        #### 🏷️ Required Skills/Technologies
        {tags_str}

        #### ✅ Why This Job Matches You
        """
            
            if why_good:
                for reason in why_good[:3]:
                    job_details += f"- {reason}\n"
            else:
                job_details += "- Strong match based on your resume and experience\n"
            
            if concerns:
                job_details += "\n#### ⚠️ Things to Consider\n"
                for concern in concerns[:2]:
                    job_details += f"- {concern}\n"
            
            job_details += f"\n**💡 Recommendations:** {recommendations}\n\n"

        report += job_details

        ## Update store in state
        state['final_output'] = report
        state['final_report'] = report
        state['report_data'] = {
            'report_text': report,
            'matched_jobs': matched_jobs,
            'timestamp': datetime.now().isoformat()
        }

        if 'reasoning_history' not in state:
            state['reasoning_history'] = []

        state['reasoning_history'].append({
            'node': 'job_report_generator',
            'action': 'generate_report',
            'jobs_included': len(matched_jobs),
            'timestamp': datetime.now().isoformat()
        })
    
        try:
            detailed_json = {
                'summary': {
                    'total_jobs': len(matched_jobs),
                    'avg_match': sum(j.get('match_percentage', 0) for j in matched_jobs) / len(matched_jobs) if matched_jobs else 0,
                    'timestamp': datetime.now().isoformat(),
                    'keywords': state.get('job_keywords', []),
                    'location': state.get('job_location', 'N/A')
                },
                'jobs': []
            }
            
            for i, job in enumerate(matched_jobs, 1):
                detailed_json['jobs'].append({
                    'rank': i,
                    'title': job.get('title'),
                    'company': job.get('company'),
                    'location': job.get('location'),
                    'salary': job.get('salary'),
                    'job_type': job.get('job_type'),
                    'description': job.get('description'),  # FULL description
                    'url': job.get('url'),
                    'source': job.get('source'),
                    'tags': job.get('tags', []),
                    'match_percentage': job.get('match_percentage', 0),
                    'composite_score': job.get('composite_score', 0),
                    'ranking_reasoning': job.get('ranking_reasoning', {}),
                    'recommendations': job.get('recommendations')
                })
            
            os.makedirs("reports/detailed", exist_ok=True)
            json_path = f"reports/detailed/{state['task_id']}_full_details.json"
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(detailed_json, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Detailed JSON saved: {json_path}")
            state['json_report_path'] = json_path

        except Exception as e:
            logger.warning(f"Failed to save JSON: {e}")

        logger.info(f"📄 Job report generated: {len(report)} characters")

        state = convert_numpy_types(state)
        state['confidence_score'] = float(state.get('confidence_score', 0.0))
        if 'matched_jobs' in state:
            state['matched_jobs'] = convert_numpy_types(state['matched_jobs'])
    
        return state
    
    async def ensure_resume_node(self, state, config):

        if state.get("resume_text"):
            return state

        resume_id = state.get("resume_id")
        user_id = state.get("user_id")

        resume_text = None

        if resume_id:
            resume_text = await self.agent_app.memory.get_resume_by_id(resume_id)
            if resume_text:
                logger.info(" Resume loaded using resume_id")
                state["resume_text"] = resume_text
                return state

        try:
            prefs = self.agent_app.memory.preferences_collection.get(ids=[user_id])
            if prefs and prefs.get("metadatas"):
                resume_text = prefs["metadatas"][0].get("resume_text")
                if resume_text:
                    logger.info(" Resume loaded from preferences")
                    state["resume_text"] = resume_text
                    return state
        except Exception as e:
            logger.warning(f" Preferences fetch failed: {e}")


        logger.warning(" No resume found → fallback to jobs")

        jobs = state.get("jobs_data", [])
        resume_text = " ".join(
            f"{job.get('title', '')} {job.get('description', '')}"
            for job in jobs
        )

        state["resume_text"] = resume_text or ""

        return state

    async def memory_storage_node(self, state: AgentState, config) ->AgentState:
        """
        Store resume and Context in Persistent Memory
        """
        with tracer.start_as_current_span("memory_node.state") as parent_span:
            start_memory = time.time()
            parent_span.set_attribute("memory_storage", "node")

            try:
                resume_text = state.get('resume_text', '')
                if not resume_text:
                    logger.info("No resume text found in memory storage node -- skipping")
                    return state
                
                user_id=state.get("user_id")
                if not user_id:
                    raise ValueError("Missing authentication user id")

                if resume_text:
                    await self.emit_stage.emit_staging_start(
                        run_id=state.get("run_id"),
                        stage="storing_jobs",
                        message="storing jobs"
                    )

                    ## Extract Skills from state
                    skills = state.get('job_keywords', [])
                    

                    #Store Resume
                    resume_id = await self.agent_app.memory.store_resume(
                        user_id =user_id,
                        resume_text=resume_text,
                        skills=skills,
                        experience_years=self._estimate_experience(resume_text),
                        metadata= {'task_id': state['task_id']}
                    )

                    await self.emit_stage.emit_staging_done(
                        run_id=state.get("run_id"),
                        stage="storing_jobs"
                    )

                    logger.info(f"Resume stored in memory: {resume_id} |  user_id={user_id}")

                if 'reasoning_history' not in state:
                    state['reasoning_history'] = []

                state['reasoning_history'].append({
                    'node': 'memory_storage',
                    'action': 'store_resume',
                    'run_id': state.get('run_id'),
                    'resume_id': state.get('resume_id'),
                    'timestamp': datetime.now().isoformat()
                })

                parent_span.set_attribute("memory.resume_length", len(resume_text))
                parent_span.set_attribute("memory.resume_stored", bool(resume_id))
                parent_span.set_attribute("memory.skills_count", len(skills))
                return state
            
            except Exception as e:
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                return state

            finally:
                parent_span.set_attribute("memory.latency_seconds", time.time() - start_memory)
            


    
    async def memory_retrieval_node(self, state:AgentState, config)->AgentState:
        """New: Retrive RAG Context before Matching"""

        with tracer.start_as_current_span("retrievel_node.state") as parent_span:
            start_retrieval = time.time()
            parent_span.set_attribute("memory_retrieval", "node")
            
            try:
                user_id = state.get('user_id', 'anonymous')
                jobs = state.get('jobs_data', [])
                resume_text = state.get('resume_text', '')


                await self.emit_stage.emit_staging_start(
                    run_id=state.get("run_id"),
                    stage="retrieving_context",
                    message="Retrieving better context for matching.."
                )

                ## Get RAG context
                rag_context = await self.agent_app.memory.get_rag_context_for_matching(
                    user_id = user_id,
                    resume_text=resume_text,
                    current_jobs = jobs,
                    run_id = state["run_id"]
                )

                rag_context = rag_context  or {}
                
                rag_context = {
                    "similar_resumes": rag_context.get("similar_resumes", []),
                    "similar_jobs": rag_context.get("similar_jobs", []),
                    "match_history": rag_context.get("match_history", []),
                    "user_preferences": rag_context.get("user_preferences", {}),
                    "similar_past_jobs": rag_context.get("similar_past_jobs", []),
                    "context_quality": rag_context.get("context_quality", 0.0),
                }

                await self.emit_stage.emit_staging_done(
                    run_id=state.get("run_id"),
                    stage="retrieving_context"
                )


                logger.info(f"🧠 RAG Context normalized: {len(rag_context['similar_resumes'])} similar resumes found")
                # Store context in state for other nodes to use

                state['rag_context']=rag_context
                state['user_preferences']= rag_context.get('user_preferences',{})
                state['similar_past_searches']=rag_context.get('similar_resumes', [])


                logger.info(f" RAG Context retriver: quality {rag_context['context_quality']:.2f}")

                if 'reasoning_history' not in state:
                    state['reasoning_history'] = []

                state['reasoning_history'].append({
                    'node': 'memory_retriver',
                    'action': 'retrive_rag_context',
                    'context_quality': rag_context['context_quality'],
                    'similary_resumes_found': len(rag_context['similar_resumes']),
                    'match_history_count': len(rag_context['match_history']),
                    'timestamp': datetime.now().isoformat()
                })

                parent_span.set_attribute("retrieval.similarity_resumes",len(rag_context["similar_resumes"]))
                parent_span.set_attribute("retrieval.context_quality", float(rag_context["context_quality"]))
                parent_span.set_attribute("retrieval.similar_jobs", len(rag_context["similar_jobs"]))
                return state
            
            except Exception as e:
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                return state
            finally:
                parent_span.set_attribute("retrieval.latency_seconds", time.time() - start_retrieval)


    async def memory_job_storage_node(self, state: AgentState, config) -> AgentState:

        with tracer.start_as_current_span("job_storage.state") as parent_span:
            start_job_storage = time.time()
            parent_span.set_attribute("job_storage", "node")

            try:
                jobs = state.get('jobs_data', [])
                
                if not jobs:
                    logger.info("No jobs to store")
                    return state

            
                run_id = state.get('run_id')
                user_id = state.get("user_id")
                
                if not run_id:
                    logger.error("❌ CRITICAL: run_id missing in memory_job_storage_node!")
                    logger.error(f"   State keys: {list(state.keys())}")
                    
                
                    if hasattr(self, 'agent_app') and self.agent_app.multi_agent_orchestrator:
                        run_id = await self.agent_app.multi_agent_orchestrator.shared_context.read(f"current_run_id_{user_id}")
                        if run_id:
                            state['run_id'] = run_id
                            logger.info(f" Recovered run_id from shared_context: {run_id}")
                        else:
                            logger.error("❌ shared_context also has no run_id!")
                
                logger.info(f"📦 Storing {len(jobs)} jobs with run_id: {run_id}")

                keywords = state.get('job_keywords', [])
                location = state.get('job_location', 'remote')
                search_key = f"{','.join(keywords[:3])}_{location}".lower().replace(' ', '_')
                search_fingerprint = hashlib.sha256(search_key.encode()).hexdigest()[:16]

                logger.info(f" Search fingerprint: {search_fingerprint}")
                
                search_context = {
                    'keywords': keywords,
                    'location': location, 
                    'experience_level': state.get('experience_level', 'mid'),
                    'run_id': state.get('run_id'),
                    'search_key': search_key,
                    'search_fingerprint': search_fingerprint,  
                    'timestamp': datetime.now().isoformat(),
                    'source': 'langgraph_workflow',
                    'is_fresh': True
                }
                
            
                if not search_context.get('run_id'):
                    logger.error("❌ CRITICAL: run_id missing from search_context!")
                    search_context['run_id'] = run_id
                
            
                logger.info(f"📋 search_context being passed to store_jobs:")
                logger.info(f"   - run_id: {search_context['run_id']}")
                logger.info(f"   - keywords: {search_context['keywords']}")
                logger.info(f"   - location: {search_context['location']}")
                
                
                state['search_context'] = search_context
                store_count = await self.agent_app.memory.store_jobs(
                    jobs=jobs,
                    search_context=search_context
                )
                
                logger.info(f" Successfully stored {store_count} jobs with run_id: {run_id}")

            
                if 'reasoning_history' not in state:
                    state['reasoning_history'] = []

                state['reasoning_history'].append({
                    'node': 'memory_job_storage',
                    'action': 'store_jobs',
                    'jobs_stored': len(jobs),
                    'run_id': run_id,  
                    'timestamp': datetime.now().isoformat()
                })

                parent_span.set_attribute("job_storage.run_id", run_id)
                parent_span.set_attribute("job_storage.jobs_count", len(jobs))
                parent_span.set_attribute("job_storage.store_count", store_count)
                parent_span.set_attribute("job_storage.search_fingerprint", search_fingerprint)
                return state
            
            except Exception as e:
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                return state
            finally:
                parent_span.set_attribute("memory_job.latency_seconds", time.time() - start_job_storage)
            
    async def memory_learning_node(self, state:AgentState, config)->AgentState:
        """NEW: Store match results and learn from them
        Runs after matching is complete"""

        with tracer.start_as_current_span("memory_learning.state") as parent_span:
            start_memory_learning = time.time()
            parent_span.set_attribute("memory_learning", "node")

            try:        
                user_id = state.get("user_id")
                resume_id = state.get("resume_id") or "unknown_resume"
                resume_text = state.get("resume_text") or ""

                matched_jobs = state.get("matched_jobs") or []
                for job in matched_jobs[:10]:
                    await self.agent_app.memory.store_successful_match(
                        user_id=user_id,
                        resume_id=resume_id,
                        job=job,
                        rerank_score= job.get('rerank_score',0.0),
                        user_action= 'shown',
                        run_id = state.get('run_id')
                    )

                preferences = {
                    'resume_snippet': resume_text[:500],
                    'job_keywords': ', '.join(state.get('job_keywords', [])),  
                    'preferred_titles': ', '.join([j.get('title', '') for j in matched_jobs[:3] if j.get('title')]),  
                    'preferred_companies': ', '.join([j.get('company', '') for j in matched_jobs[:3] if j.get('company')]),
                    'preferred_location': state.get('job_location', 'Remote'),  
                    'avg_match_score': float(state.get('confidence_score', 0)),  
                    'timestamp': datetime.now().isoformat() 
                }

                await self.agent_app.memory.update_user_preferences(
                    user_id =user_id,
                    preferences=preferences
                )

                logger.info(f" Learning Complete Stored: {len(matched_jobs[:10])} matches")

                if 'reasoning_history' not in state:
                    state['reasoning_history'] = []

                state['reasoning_history'].append({
                    'node': 'memory_learning',
                    'action': 'store_matched_and_learn',
                    'run_id': state.get('run_id'),
                    'matches_stored': len(matched_jobs[:10]),
                    'timestamp': datetime.now().isoformat()
                })

                parent_span.set_attribute("learning.matches_stored", len(matched_jobs[:10]))
                parent_span.set_attribute("learning.avg_match_score", state.get("confidence_score", 0))
                parent_span.set_attribute("learning.keywords_count", len(state.get("job_keywords", [])))
                parent_span.set_attribute("learning.company_count", len([
                        j for j in matched_jobs[:3]
                        if j.get("company")
                    ])
                )
                parent_span.set_attribute("learning.titles", (preferences.get("preferred_titles")))
                return state

            
            except Exception as e:
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                return state
            finally:
                parent_span.set_attribute("learning.latency_seconds", time.time() - start_memory_learning)

    def _estimate_experience(self, resume_text: str) ->int:
        """HELPER: Estimate years of experience from resume"""
        import re

        patterns = [
             r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
             r'experience:\s*(\d+)\+?\s*years?',
             r'(\d+)\+?\s*years?\s+in'
        ]

        for pattern in patterns:
            match = re.search(pattern, resume_text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 3
    
    async def skills_analysis_node(self, state: AgentState, config) -> AgentState:
        """Deep Skill Extraction and Analysis"""

        with tracer.start_as_current_span("skill_node.state") as parent_span:
            start_skill_analysis = time.time()
            parent_span.set_attribute("skill_analysis", "node")

            try:
                await self.emit_stage.emit_staging_start(
                    run_id=state.get("run_id"),
                    stage="skill_analysis",
                    message="Analyzing deep skills and gaps..."
                )
            
                if not hasattr(self, 'skill_extractor'):
                    self.skill_extractor = SkillsExtractor()

                resume_text = state.get('resume_text') or ""
                
                if not resume_text:
                    raise ValueError("resume text is missing - ensure_resume_node is not executed")

                jobs = state.get('jobs_data', [])
                
                resume_skills = self.skill_extractor.extract_from_text(
                    text=resume_text,
                    include_proficiency=True
                )

                logger.info(f"Extracted {resume_skills['total_count']} skills from resume")
                logger.info(f"Categories: {list(resume_skills['categorized'].keys())}")
                
                await self.emit_stage.emit_staging_done(
                    run_id=state.get("run_id"),
                    stage="skill_analysis"
                )

                job_skills_analysis = []
                for job in jobs:
                    job_text = f"{job.get('title', '')} {job.get('description', '')}"
                    job_skills = self.skill_extractor.extract_from_text(
                        text=job_text,
                        include_proficiency=True
                    )

                    comparison = self.skill_extractor.compare_skills(
                        resume_skills['skills'],
                        job_skills['skills']
                    )

                    job_skills_analysis.append({
                        'job_id': job.get('url', ''),
                        'job_title': job.get('title', ''),
                        'required_skills': job_skills['skills'],
                        'skill_comparison': comparison
                    })

                skill_graph = self.skill_extractor.build_skill_graph(resume_skills['skills'])
            
                state['resume_skills'] = resume_skills
                state['job_skills_analysis'] = job_skills_analysis
                state['skill_graph'] = skill_graph
            
                if 'reasoning_history' not in state:
                    state['reasoning_history'] = []

                state['reasoning_history'].append({
                    'node': 'skills_analysis',
                    'action': 'deep_skill_extraction',
                    'resume_skills_count': resume_skills['total_count'],
                    'categories': list(resume_skills['categorized'].keys()),
                    'timestamp': datetime.now().isoformat()
                })

                logger.info(f"✅ Skills analysis complete: {resume_skills['total_count']} skills identified")

                parent_span.set_attribute("skills.jobs_count", len(jobs))
                parent_span.set_attribute("skills.resume_skill_count", resume_skills["total_count"])
                return state
            
            except Exception as e:
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                return state
            finally:
                parent_span.set_attribute("skills.latency_seconds", time.time() - start_skill_analysis)
    
    async def intelligent_ranker_node(self, state: AgentState, config) ->AgentState:
        """Ranks Jobs by compoiste score with expllanation"""

        with tracer.start_as_current_span("intelligent_ranker.state") as parent_span:
            start_intelligent_ranker = time.time()
            parent_span.set_attribute("intelligent_ranker", "node")

            try:
                await self.emit_stage.emit_staging_start(
                    run_id=state.get("run_id"),
                    stage="ranking_jobs",
                    message="Ranking jobs intelligently.."
                )

                matched_jobs = state.get('matched_jobs', [])
                job_skill_analysis = state.get('job_skills_analysis', [])
                rag_context = state.get('rag_context', {})
                user_preferences = state.get('user_preferences', {})

                ranked_jobs = []
                for job in matched_jobs:
                    
                    skill_comp =next(
                        (ja['skill_comparison'] for ja in job_skill_analysis
                        if ja ['job_title'] == job.get('title')),
                        None
                    )

                    scores = self._calculate_composite_score(
                        job,
                        skill_comp,
                        rag_context,
                        user_preferences
                    )
        
                    reasoning = self._generate_job_reasoning(
                        job,
                        skill_comp,
                        scores

                    )

                    job['composite_score']=float(scores['composite'])
                    job['score_breakdown']=scores
                    job['ranking_reasoning']=reasoning
                    job['recommendations'] = self._generate_recommendation(scores)

                    ranked_jobs.append(job)
        
                ranked_jobs.sort(key=lambda x: x['composite_score'], reverse=True)
            
                for i, job in enumerate(ranked_jobs, 1):
                    job['rank'] =i
                
                state['ranked_jobs'] = ranked_jobs[:15]
            
                state['matched_jobs'] = ranked_jobs[:15]

                if 'reasoning_history' not in state:
                    state['reasoning_history'] = []

                state['reasoning_history'].append({
                    'node': 'intelligent_ranker',
                    'action': 'multi_factor_ranking',
                    'jobs_ranked': len(ranked_jobs),
                    'top_score': ranked_jobs[0]['composite_score'] if ranked_jobs else 0,
                    'timestamp': datetime.now().isoformat()
                })
                
                await self.emit_stage.emit_staging_done(
                    run_id=state.get("run_id"),
                    stage="ranking_jobs"
                )
                logger.info(f" Ranked {len(ranked_jobs)} jobs - Top score: {ranked_jobs[0]['composite_score']:.2f}" if ranked_jobs else "No jobs to work")

                parent_span.set_attribute("ranked.received_jobs", len(matched_jobs))
                parent_span.set_attribute("ranker.jobs_ranked", len(ranked_jobs))
                parent_span.set_attribute("ranker.top_score", ranked_jobs[0]["composite_score"] if ranked_jobs else 0)
                parent_span.set_attribute("ranker.jobs_output", len(state["ranked_jobs"]))
                return state
            
            except Exception as e:
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
                return state
            finally:
                parent_span.set_attribute("ranker.latency_seconds", time.time() - start_intelligent_ranker)

    def _calculate_composite_score(self, job: Dict, skill_comp: Dict, rag_context: Dict, user_prefs: Dict) ->Dict:
        """Calculate Multifacctor composite score """

        scores = {}

        if skill_comp:
            skill_score = (
                skill_comp.get('match_percentage', 0) / 100 * 0.7 +
                skill_comp.get('strength_score', 0) * 0.3
            )
        else:
            skill_score = job.get('dense_score', 0.5)
        scores['skill_match'] = skill_score

    
        embedding_score = job.get('rerank_score', 0.5)
        scores['embedding_similarity'] =embedding_score

        job_location = (job.get('location')  or "").lower()
        preferred_location = user_prefs.get('preferred_location', ['remote'])[0].lower()
        location_score = 1.0 if preferred_location in job_location else 0.5
        scores['location_match'] = location_score

        similar_matches = rag_context.get('similar_past_jobs',[])
        history_score = 0.7
        if similar_matches:
            avg_similarity = float(np.mean([m.get('similarity', 0.5) for m in similar_matches[:3]]))
            history_score = avg_similarity
        scores['historical_performance'] =history_score

        
        source_quality = {
            'indeed_direct': 0.9,
            'google_search': 0.8,
            'remoteok': 0.85,
            'hackernews': 0.95,
            'sample_data': 0.3
        }

        source_score =  source_quality.get(job.get('source', 'unknown'), 0.5)
        scores['source_quality']=source_score

        
        completeness = 0.0
        if job.get('title'): completeness += 0.3
        if job.get('company'): completeness +=0.3
        if job.get('description') and len(job.get('description', '')) >50: completeness += 0.4
        scores['completeness'] = completeness


        composite = (
            scores['skill_match'] * 0.55 +
            scores['embedding_similarity'] * 0.20 +
            scores['location_match'] * 0.10 +
            scores['historical_performance'] * 0.05 +
            scores['source_quality'] * 0.05 +
            scores['completeness'] * 0.05 
        )

        scores['composite'] = composite    
        return scores

    def _generate_job_reasoning(self, job:Dict, skill_comp: Dict, scores: Dict) ->Dict:
        """Generate Detailed reasoning for job recommendation"""

        reason_good = []
        reason_concern = []
        
        if skill_comp:
            match_pct = skill_comp.get('match_percentage', 0)
            if match_pct >= 70:
                reason_good.append(f" Strong skill match ({match_pct:.0f}) % of requirement met")
            elif match_pct >= 50:
                reason_good.append(f"Good skill overlap {match_pct:.0f}% match")
            else:
                reason_good.append(f" Only {match_pct:.0f}% skill match")
            
            critical_missing = skill_comp.get('critical_missing', [])
            if critical_missing:
                reason_concern.append(f" Critical missing skills {', '.join(critical_missing[:3])}")
            
            strengths = skill_comp.get('strength_score', 0)
            if strengths >=0.8:
               reason_good.append("Your skills are at senior/expert level for this role")
        
        if scores.get('location_match', 0) >=0.9:
           reason_good.append("Perfect Location match")

        if scores.get('source_quality', 0) >= 0.8:
            reason_good.append("From reputable job source")
        
        composite = scores.get('composite', 0)
        if composite >= 0.8:
            overall = "Excellent match - Highly recommended"
        
        elif composite >= 0.6:
            overall = "Good match - Worth applying"
        
        elif composite >= 0.4:
            overall = "Moderate match - Consider if interested"
        
        else:
             overall = "Lower match - may not be ideal"
        
        return {
            'why_good_fit': reason_good,
            'potential_concerns': reason_concern,
            'overall_assessment': overall,
            'confidence': round(composite, 2)
        }
    
    def _generate_recommendation(self, scores: Dict) ->str:
        """Generate Action reccomendation"""

        composite = scores.get('composite', 0)

        if composite >= 0.75:
            return "STRONGLY recommend - apply immediatly"
        
        elif composite >= 0.60:
            return "RECOMMENDED - Good Opportunity"
        
        elif composite >= 0.45:
            return "CONSIDER -  If interested"
        
        else:
            return "SKIP -  Better matches available"
    
    async def meta_reasoner_node(self, state:AgentState, config) ->AgentState:
        """Meta reasoning about the cognitive search Evaluates and suggests improvements"""

        matched_jobs = state.get('matched_jobs', [])
        resume_skills = state.get('resume_skills', {})
        rag_context = state.get('rag_context', {})
        
        evaluation = {
            'search_quality': self._evaluate_search_quality(matched_jobs),
            'skill_coverage': self._evaluate_skill_coverage(matched_jobs, resume_skills),
            'diversity_score': self._evaluate_diversity(matched_jobs),
            'context_quality': rag_context.get('context_quality', 0.0)
        }
        
        insights = self._generate_meta_insights(evaluation, state, config)

        suggestions = self._generate_suggestions(evaluation, matched_jobs, resume_skills)

        overall_confidence = np.mean([
            evaluation['search_quality'],
            evaluation['skill_coverage'],
            evaluation['diversity_score'],
            evaluation['context_quality']
        ]) 

        state['meta_reasoning']= {
            'evaluation': evaluation,
            'insights': insights,
            'suggestions': suggestions,
            'overall_confidence': overall_confidence
        }
        state['confidence_score'] = float(overall_confidence)

        if 'reasoning_history' not in state:
            state['reasoning_history'] = []           

        state['reasoning_history'].append({
            'node': 'meta_reasoner',
            'action': 'meta_cognitive_evaluation',
            'overall_confidence': overall_confidence,
            'insight_count': len(insights),
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f" Meta reasoning complete {overall_confidence:.2f}")

        return state
    
    def _evaluate_search_quality(self, jobs: List[Dict]) ->float:
        """EValuate overall quality of search results"""
        if not jobs:
            return 0.0

        scores = [j.get('composite_score', 0) for j in jobs]
        avg_score = np.mean(scores)

        high_quality = sum(1 for s in scores if s >= 0.6)
        quality_ratio = high_quality / len(jobs)

        return (avg_score * 0.6 + quality_ratio * 0.4)
    
    def _evaluate_skill_coverage(self, jobs: List[Dict], resume_skills: Dict) ->float:
        """Evaluate how well jobs utilize resume skills"""

        if not jobs or not resume_skills:
            return 0.5
        
        resume_categories = set(resume_skills.get('categorized', {}).keys())

        relevant_count = 0
        for job in jobs:
            job_text = f"{job.get('title', '')} {job.get('descripiton', '')}".lower()
    
            if any(cat in job_text for cat in resume_categories):
                relevant_count += 1
        
        return relevant_count / len(jobs) if jobs else 0.0
    
    def _evaluate_diversity(self, jobs: List[Dict])-> float:
        """Evaluate diversity of jobs results"""

        if not jobs:
            return 0.0
    
        companies = set(j.get('companies', 'unknown') for j in jobs)
        company_diversity = min(1.0, len(companies) / max(5, len(jobs) * 0.5))

        locations = set(j.get('location', 'unknown') for j in jobs)
        location_diversity = min(1.0, len(locations) / 3)

        return (company_diversity * 0.6 + location_diversity * 0.4 )

    def _generate_meta_insights(self, evaluation: Dict, state:AgentState, config) ->List[str]:
        """Generate High-levels insights search"""
        insights = []

        quality = evaluation['search_quality']
        if quality >= 0.7:
            insights.append("Search produced high quality matches")
        
        elif quality <= 0.5:
            insights.append("Serach quality can be improved -  Consider broader criteria")
        
        coverage = evaluation['skill_coverage']

        if coverage >= 0.8:
            insights.append("Jobs strongy align with your skill set")
        elif coverage < 0.5:
            insights.append("Many jobs don't fully utilize with your skills - Consider specializing Search")
        
        context_qual = evaluation['context_quality']

        if context_qual >= 0.7:
            insights.append("Strong context available - results improving by time")
        
        elif context_qual < 0.3:
            insights.append("Limited data - system will improve with future searches")
        
        job_count = len(state.get('matched_jobs', []))

        if job_count < 5:
            insights.append(f"Only {job_count} Found - Consider more broader searches")
        
        elif job_count >=10:
            insights.append(f" Found {job_count} opportunities - Strong job market presence")
        
        return insights
    
    def _generate_suggestions(self, evaluation: Dict, jobs: List[Dict], resume_skills: Dict) -> List[str]:
        """Generate actionable suggestions"""
        suggestions = []

        if evaluation['search_quality'] < 0.6:
             suggestions.append("Try adding more specific keywords related to your experience")
             suggestions.append("Consider expanding location preferences")

        if jobs:
            all_required = set()
            for job in jobs[:5]:
                desc = job.get('description', '').lower()
                for skill_cat in ['python', 'react', 'aws', 'kubernetes']:
                    if skill_cat in desc:
                        all_required.add(skill_cat)
            
            user_skills = set(s['name'] for s in resume_skills.get('skills', []))
            missing = all_required - user_skills
            
            if missing:
                suggestions.append(f"Consider learning: {', '.join(list(missing)[:3])}")

        if evaluation['diversity_score'] < 0.5:
            suggestions.append("Results are concentrated - try searching different job boards")

        return suggestions

   


        



    
    
    



         


















        










    















    
 











