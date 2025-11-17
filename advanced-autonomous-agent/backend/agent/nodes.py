from langchain_groq import ChatGroq
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import structlog
from ..core.skills_extractor import SkillsExtractor
from ..core.memory_system import MemoryRAGSystem
from .state import AgentState
from .scraper_engine import IntelligentJobScraper
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
import json
import structlog
import re
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

    def __init__(self, llm: ChatGroq, tools: Dict, mcp_client: Dict):
        # FIXED: Removed trailing commas that created tuples
        self.llm = llm
        self.tools = tools
        self.mcp = mcp_client
        self.embedding_model = None
        self.memory = MemoryRAGSystem(persistent_directory="./chroma_db")
        logger.info(f"Memeory System is Initialized in AgentNodes")

    
    def _get_embedding_model(self):
        if self.embedding_model is None:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self.embedding_model

    def _extract_json(self, text: str) -> dict:
        """
        Extract JSON from LLM response that might be wrapped in markdown code blocks
        """
        # Try to parse as-is first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract from markdown code block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find any JSON object in the text
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # If all else fails, return a default structure
        return {"error": "Could not parse JSON", "raw_text": text}

    async def planner_node(self, state: AgentState) -> AgentState:
        """
        Plan: Break down tasks Into executable steps
        Uses chain of thoughts reasoning
        """
        system_prompt = """You are an expert planner for an autonomous AI agent.
        Given a task, break it down into concrete, actionable steps.
        Consider what information is needed, what tools to use, and validation steps.
        
        Output a JSON plan with:
        - steps: List of step descriptions
        - tools_needed: Tools required for each step
        - success_criteria: How to validate completion
        """

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Task: {state['task']}\nTask_type: {state['task_type']}")
        ]

        response = await self.llm.ainvoke(messages)
        data_plan = self._extract_json(response.content)

        state['plan'] = data_plan.get('steps', [])
        
        # Ensure reasoning_history exists
        if 'reasoning_history' not in state:
            state['reasoning_history'] = []
            
        state['reasoning_history'].append({
            'node': 'planner',
            'action': 'plan',
            'content': data_plan,
            'timestamp': datetime.now().isoformat()
        })

        state = convert_numpy_types(state)

        return state

    async def researcher_node(self, state: AgentState) -> AgentState:
        """
        ACT: Execute Web search using MCP server
        """

        if state['plan'] and len(state['plan']) > state['current_step']:
           current_step = state['plan'][state['current_step']]
        
        else:
            current_step = state.get('task', 'Research and analyze the given topic')

        logger.info(f"Researching Task: {current_step} ")

        query_prompt = f"""Generate 2-3 specific search queries for this research step:

        step: {current_step}
        context: {state['task']}

        Return only the queries as json ARRAY"""

        response = await self.llm.ainvoke([HumanMessage(content=query_prompt)])
        queries = self._extract_json(response.content)

        # Execute searcher Via MCP
        search_results = []

        for query in queries:
            try:
                # FIXED: All params in one dict with 'tool' key
                results = await self.mcp['web_search'].tool_call(
                    tool= "web_search",
                    query= query,
                    max_tokens= 3
                )
                if isinstance(results, list):
                    search_results.extend(results)
                elif results:
                    search_results.append(results)
            
            except (AttributeError, KeyError, TypeError) as e:
                search_results.append({'error':str(e)})


        if isinstance(queries, list):
            state['search_queries'].extend(queries)
        
        else:
            state['search_queries'].append(queries)
        
        state['search_results'].extend(search_results)
        # FIXED: These should be outside the loop
        state['reasoning_history'].append({
            'node': 'researcher',
            'action': 'search',
            'queries': queries,
            'result_count': len(search_results),
            'timestamp': datetime.now().isoformat()
        })

        state = convert_numpy_types(state)

        return state

    async def analyzer_node(self, state: AgentState) -> AgentState:
        """
        OBSERVE: Analyze collected data and extract insights.
        """
        analysis_prompt = f"""Analyze the following research results and extract key insights:

        Task: {state['task']}
        Search Results: {json.dumps(state['search_results'][-10:], indent=2) if state['search_results'] else 'No search results'}
    
        Extract:
        1. Key findings (list of strings)
        2. Patterns and trends (list of strings)
        3. Actionable insights (list of strings)
        4. Data quality assessment (string)
    
        IMPORTANT: Return ONLY valid JSON in this exact format:
       {{
           "key_findings": ["finding 1", "finding 2"],
            "patterns": ["pattern 1", "pattern 2"],
            "insights": ["insight 1", "insight 2"],
            "quality": "good/fair/poor"
        }}
        """
    
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="You are an expert data analyst. Return ONLY valid JSON."),
                HumanMessage(content=analysis_prompt)
            ])
            
            # ✅ SAFE JSON PARSING
            try:
                # Try to parse as JSON
                analysis = json.loads(response.content)
            except json.JSONDecodeError:
                # If JSON parsing fails, create a structured response
                logger.warning("Failed to parse LLM response as JSON, creating fallback analysis")
                analysis = {
                    "key_findings": [response.content[:500]],
                    "patterns": ["Analysis in progress"],
                    "insights": ["Further processing needed"],
                    "quality": "fair"
                }
        
            # ✅ ENSURE analysis is a dict
            if not isinstance(analysis, dict):
                analysis = {
                    "key_findings": [str(analysis)],
                    "patterns": [],
                    "insights": [],
                    "quality": "fair"
                }
            
            # ✅ ENSURE all required keys exist
            analysis.setdefault('key_findings', [])
            analysis.setdefault('patterns', [])
            analysis.setdefault('insights', [])
            analysis.setdefault('quality', 'unknown')
            
            # Store in database (if available)
            if self.mcp.get('database'):
                try:
                    await self.mcp['database'].store_insight(
                        task_id=state['task_id'],
                        insights=analysis.get('key_findings', []),
                        metadata={'timestamp': datetime.now().isoformat()}
                    )
                except Exception as e:
                    logger.warning(f"Failed to store insights in database: {e}")
            
            # Update state
            state['extracted_insights'].append(analysis)
            state['analysis_results'] = analysis
            
            # ✅ SAFE LENGTH CHECK
            insight_count = len(analysis.get('key_findings', []) or [])
            
            state['reasoning_history'].append({
                'node': 'analyzer',
                'action': 'ANALYZE',
                'insight_count': insight_count,
                'quality': analysis.get('quality', 'unknown'),
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"✅ Analysis completed: {insight_count} key findings")
            
        except Exception as e:
            logger.error(f"❌ Analyzer node error: {e}")
            state['errors'].append({
                'node': 'analyzer',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            
            # Add fallback empty analysis
            state['analysis_results'] = {
                "key_findings": ["Analysis failed - using fallback"],
                "patterns": [],
                "insights": [],
                "quality": "poor"
            }

            state = convert_numpy_types(state)
        
        return state

    async def reasoner_node(self, state: AgentState) -> AgentState:
        """
        Reflect: Meta-reasoning about progress and quality
        Implements Reflection Pattern
        """
        reflection_prompt = f"""Reflect on agent's progress:

        Task: {state['task']} 
        plan: {state['plan']}
        current_step: {state['current_step']+1}/{len(state['plan'])}
        Insights so far: {len(state['extracted_insights'])}
        Errors: {state['errors']}

        Evaluate:
        1. Is the Task on track
        2. Is the quality of insights sufficient
        3. Should we retry any steps
        4. Confidence score (0-1)
        5. Next action recommendation 

        Return JSON with evaluation"""

        response = await self.llm.ainvoke([
            SystemMessage(content="You are a meta-reasoning System evaluating agent performance"),
            HumanMessage(content=reflection_prompt)
        ])

        reflection = self._extract_json(response.content)

        state['confidence_score'] = reflection.get('confidence_score', 0.5)
        state['validation_results'] = reflection
        state['reasoning_history'].append({
            'node': 'reasoner',
            'action': 'REFLECT',
            'reflection': reflection,
            'timestamp': datetime.now().isoformat()
        })

        state = convert_numpy_types(state)

        return state

    async def generator_node(self, state: AgentState) ->AgentState:
        """Generate final report with simple-tokens"""

        def trunacate_insights(insights, max_items=3):
            if not insights:
                return []
            
            return insights[-max_items]
        
        def summarize_results(results, max_length =2000):
            if not results:
                return []
            
            results_str = json.dumps(results, indent =2)
            if len(results_str) >max_length:
                if 'key_finings' in results:
                    return {'key_findings': results['key_findings'][:5]}
                return {'summary': results_str[:max_length] + '....(trunacated)'}

        
        condensed_insights = trunacate_insights(state['extracted_insights'], max_items =3)
        condensed_analysis = summarize_results(state['analysis_results'], max_length= 2000)


        search_results_text =""
        if state.get('search_results'):
            search_results_list = []
            for result in state['search_results'][-5:]:
                if isinstance(result, dict):

                    title = result.get('title', '')
                    content = result.get('content', '') or result.get('snipper', '') or result.get('descripiton', '')
                    url = result.get('ur','')
                    search_results_list.append(f"{title}, {content}, {url}")
                else:
                    search_results_list.append(str(result))
            search_results_text = '\n'.join(search_results_list)


        generator_prompt = f""" Generate a comprehensive report based on the analysis:
        
        
        Task: {state['task']}

        Prepared by: {state.get('Umer Fayaz', 'Autonomous Agent')}
        
        key insights: {json.dumps(condensed_insights, indent=2)}
        analysis summary: {json.dumps(condensed_analysis, indent=2)}
        search results : {search_results_text}

        
        Generate a professional markdown report with Executive summary, Key findings, Analysis and Recommendations"""


        response = await self.llm.ainvoke([
            SystemMessage(content= "You are an expert business analyst"),
            HumanMessage(content= generator_prompt)
        ])

        reports = response.content

        state['final_output']=reports


        ##Save to file

        os.makedirs("reports",exist_ok=True)
        filename = f"reports {state['task_id']}_report.md"


        try:
            with open(filename, "w", encoding= 'utf-8') as f:
                f.write(reports)
            print(f"Report in {filename}")
        except Exception as e:
            print(f"failed to save file {e}")

        
        try:
            await self.mcp['database'].tool_call(
                tool_name = 'store_documents',
                collection_name = 'report',
                document = [reports],
                metadata = [{'task_id': state['task_id'], 'timestamp': datetime.now().isoformat()}],
                ids = [f"{state['task_id']}_report"]
            )
        except:
            pass


        state['final_report'] = reports
        state['artifacts'].append({
            'type': 'report',
            'content': reports,
            'filename': filename,
            'timestamp': datetime.now().isoformat()
        })

        state['status'] = 'completed'

        return state

            
    async def memory_node(self, state: AgentState) -> AgentState:
        """ 
        Remember: Query and update long-term memory.
        """
        # Query Memories
        try:
            # FIXED: All params in one dict with 'tool' key
            relevant_memories = await self.mcp['database'].tool_call({
                'tool': 'query_memory',
                'query': state['task'],
                'top_k': 5,
                'filters': {'task_type': state['task_type']}
            })
            state['relevant_memories'] = relevant_memories
        except (AttributeError, KeyError, TypeError) as e:
            # MCP not available - continue without memories
            state['relevant_memories'] = []

        # Updating entity relationships
        if state['extracted_insights']:
            entities = []
            for insight in state['extracted_insights']:
                if 'entities' in insight:
                    entities.extend(insight['entities'])

            if entities:
                try:
                    # FIXED: All params in one dict with 'tool' key
                    await self.mcp['database'].tool_call({
                        'tool': 'update_entities',
                        'entities': entities,
                        'task_id': state['task_id']
                    })
                except (AttributeError, KeyError, TypeError) as e:
                    # MCP not available - continue
                    pass


    async def job_planner_node(self, state: AgentState) -> AgentState:
        """Enhanced Planner specifically for job matching tasks"""
        system_prompt = """You are a expert job search planner.
        Given a resume and preferences, created a targeted job search stretegy
        
        consider:
        -Best job boards for this profile
        -Optimal search keywords
        -Location stretegy
        -Experience level matching
        
        Return json with
        - job_keywords: List of search terms
        - sources: Prioritized list of job boards
        - search_stretegy: Description of approach
        """

        resume_snippet = state.get('resume_text','')[:500] if state.get('resume_text') else ''

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"""
            Resume  (snippet) {resume_snippet}

            Task: {state['task']}
            User Preferences
            - Location : {state.get('job_location', 'Any')}
            - Experience {state.get('job_experience', 'Any')}
            - keywords {state.get('job_keywords', 'Any')}
            
            Create a search stretegy""")
        ]

        response = await self.llm.ainvoke(messages)
        stretegy = self._extract_json(response.content)

        ## Update State with stretegy
        state['job_keywords'] = stretegy.get('job_keywords', state.get('job_keywords', []))
        state['plan'] = stretegy.get('steps', [
            "Scrape jobs from source",
            "Match resume with jobs",
            "Genrate report",
            "Send email"
        ])

        state['reasoning_history'].append({
            'node':'job_planner',
            'Action': 'job_search_stretegy',
            'stretegy': 'stretegy',
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"Job stretegy created: {len(state['job_keywords'])}keywords")

        state = convert_numpy_types(state)

        return state


    async def job_scraper_node(self, state: AgentState) -> AgentState:
        """
        ENHANCED: Multi-source intelligent scraper (no API keys needed).
        """
        keywords = state.get('job_keywords', [])
        location = state.get('job_location', 'Remote')
        experience = state.get('experience_level', 'mid')

        if not keywords:
            # Extract keywords from resume
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

        ## Fix Adding fallback after multiple retries
        if retry_count >= 2 and len(existing_jobs) == 0:
            logger.warning(f" Retry cound {retry_count} Creating fallback for sample jobs")
            fallback_jobs = self._create_sample_jobs(keywords, location)
            state['jobs_data'] = fallback_jobs
            state['reasoning_history'].append({
                'node': 'job_scraper',
                'action': 'fallback_sample_data',
                'reason': 'Multiple Job failers',
                'jobs_created': len(fallback_jobs),
                'timestamp': datetime.now().isoformat()
            })

            return state

        if len(existing_jobs) >100:
            logger.warning(f" Already have {len(existing_jobs)} skipping scraper to avoid explosion")
            return state


        logger.info(f"🚀 Launching intelligent multi-source scraper")
        logger.info(f"🔍 Keywords: {keywords[:5]}")
        logger.info(f"Starting Intelligent scraper {keywords[:3]} in {location}")
        try:
            # 🆕 USE THE NEW INTELLIGENT SCRAPER
            async with IntelligentJobScraper() as scraper:
                jobs = await scraper.scrape_all_sources(
                    keywords=keywords[:3],
                    location=location,
                    max_results=50,
                )
            
            # Deduplicate (scraper already does this, but double-check)
            unique_jobs = []
            seen = set()
            for job in jobs:
                job_key = f"{job.get('title')}_{job.get('company')}"
                if job_key not in seen:
                    seen.add(job_key)
                    unique_jobs.append(job)

            
            if retry_count >0:
                logger.warning(f" Retry {retry_count} Replacing new jobs with the old ones")
                state['jobs_data'] = unique_jobs
            else:
                state['jobs_data'].extend(unique_jobs)

            
            state['reasoning_history'].append({
                'node': 'job_scraper',
                'action': 'intelligent_multi_source_scrape',
                'sources': ['google_search', 'indeed_direct', 'remoteok', 'hackernews'],
                'jobs_found': len(unique_jobs),
                'keywords': keywords,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info(f"✅ Intelligent scraper found {len(unique_jobs)} unique jobs")
            logger.info(f" Total jobs in state: {len(state['jobs_data'])}")

            if len(unique_jobs) == 0 and retry_count <3:
                logger.warning(f" No jobs found {retry_count +1 }/3")
                state['retry_count'] = retry_count + 1
            
        except Exception as e:
            logger.error(f"❌ Intelligent scraper failed: {e}")
            state['errors'].append(f"Scraping error: {str(e)}")
            
            # 🔄 FALLBACK: Create sample data for testing
            if len(state.get('jobs_data', [])) == 0:
                logger.warning(f"Using fallback sample data")
                unique_jobs = self._create_sample_jobs(keywords, location)
                state['jobs_data'] = unique_jobs

            state = convert_numpy_types(state)

        return state
    
    def _create_sample_jobs(self, keywords: List[str], location: str) ->List[Dict]:
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


    async def job_matcher_node(self, state: AgentState) ->AgentState:
        """"Matches Jobs using embedding-based simialrity"""
        resume_text = state.get('resume_text')
        jobs = state.get('jobs_data',[])

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

        try:

            ## Get Embedding model
            model = self._get_embedding_model()


            ## Generate resume Embeddings
            resume_embeddings = model.encode(resume_text, convert_to_numpy=True)

            # Generate JObs embeddings
            job_texts = []
            for job in jobs:
                text = f"{job.get('title', '')} {job.get('description', '')} {job.get('company', '')}"
                job_texts.append(text)

            
            job_embeddings = model.encode(job_texts, convert_to_numpy=True)


            ## Calculate Cosine Simialrity
            similarity = np.dot(job_embeddings, resume_embeddings) / (np.linalg.norm(job_embeddings, axis=1) * np.linalg.norm(resume_embeddings))

            ## Ranks Jobs by similarity
            top_k = min(15, len(jobs))
            top_indices = np.argsort(similarity)[-top_k:][::-1]


            matched_jobs =[]
            seen_job_urls = set()

            for idx in top_indices:
                job = jobs[idx].copy()
                
                # Check for duplicates
                job_url = job.get('url', '')
                if job_url and job_url in seen_job_urls:
                    continue  # Skip duplicate
                
                if job_url:
                    seen_job_urls.add(job_url)
                
                job['match_score'] = float(similarity[idx])
                job['match_percentage'] = float(similarity[idx] * 100)
                
                job = convert_numpy_types(job)
                matched_jobs.append(job)
            
            for job in matched_jobs:
                job['match_score'] =float(job.get('match_score', ''))
                job['match_percentage'] = float(job.get('match_percentage', ''))
                job['composite_score'] = float(job.get('composite_score',0))


            state['matched_jobs'] = matched_jobs

            # In job_matcher_node, after: state['matched_jobs'] = matched_jobs

            # 🆕 Log detailed job info
            logger.info("\n" + "="*70)
            logger.info("📋 MATCHED JOBS DETAILS")
            logger.info("="*70)

            for i, job in enumerate(matched_jobs[:5], 1):  # Show top 5
                logger.info(f"\n{i}. {job.get('title', 'N/A')}")
                logger.info(f"   Company: {job.get('company', 'N/A')}")
                logger.info(f"   Location: {job.get('location', 'N/A')}")
                logger.info(f"   Salary: {job.get('salary', 'N/A')}")
                logger.info(f"   Match: {job.get('match_percentage', 0):.0f}%")
                logger.info(f"   Source: {job.get('source', 'N/A')}")
                
                # Show first 200 chars of description
                desc = job.get('description', 'N/A')[:200]
                logger.info(f"   Description: {desc}...")
                
                # Show tags/skills
                tags = job.get('tags', [])
                if tags:
                    logger.info(f"   Skills: {', '.join(tags[:5])}")
                
                logger.info(f"   Apply: {job.get('url', 'N/A')}")

            logger.info("\n" + "="*70)

            ## Update Confidence score 
            avg_score = float(np.mean([j['match_score'] for j in matched_jobs ])) if matched_jobs else 0
            state['confidence_score'] = avg_score

            state['reasoning_history'].append({
                'node': 'job_matcher',
                'action': 'match_jobs',
                'total_jobs': len(jobs),
                'matched': len(matched_jobs),
                'avg_score': avg_score,
                'timestamp': datetime.now().isoformat()
            })

            logger.info(f"Matched {len(matched_jobs)} avg score: {avg_score:.2f}")

            # 🆕 Show detailed job info in console
            logger.info("\n" + "="*70)
            logger.info("📋 TOP MATCHED JOBS PREVIEW")
            logger.info("="*70)

            for i, job in enumerate(matched_jobs[:3], 1):  # Show top 3
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

        except Exception as e:
            logger.error(f"Job matching error {e}")
            state['errors'].append({
                'node': 'job_matcher',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

            ## Fallback to all jobs

            state['matched_jobs'] = jobs[:10]

            state = convert_numpy_types(state)

        return state

    async def job_quality_checker_node(self, state: AgentState) ->AgentState:
        """Qulaity Check for the job matching results"""

        matched_jobs = state.get('matched_jobs', [])

        quality_check = {
            'passed': True,
            'issues': [],
            'recommnedations':[],
            'quality_score': 1.0
        }

        ## Check quality
        if len(matched_jobs) <5:
            quality_check['passed'] =True
            quality_check['issues'].append(f"Only {len(matched_jobs)} jobs found (need 5+)")
            quality_check['recommnedations'].append("Expand search keywords or location")
            quality_check['quality_score'] -= 0.3

        ## Check matched score
        if matched_jobs:
            avg_score = float(sum(j.get('match_score', 0) for j in matched_jobs ) / (len(matched_jobs)))
            if avg_score <0.3:
                quality_check['passed'] = False
                quality_check['issues'].append(f"Low match score (avg:{avg_score:.2f})")
                quality_check['recommnedations'].append("Redefine resume or broader job search")
                quality_check['quality_score'] = -0.2
            else:
                quality_check['quality_score']= min(1.0, avg_score + 0.3)

        ## Check Job descripiton completeness
        incomplete = sum (1 for j in matched_jobs if not j.get('description'))
        if incomplete > len(matched_jobs) / 2:
            quality_check['issues'].append(f"{incomplete} job missing description")
            quality_check['quality_score'] -= 0.1
            
        ## Clean quality Score
        quality_check['quality_score'] = max(0.0, min(1.0, quality_check['quality_score']))

        ## Update State
        state['quality_check']= quality_check
        state['validation_results']['quality_check'] = quality_check

        ## Update confidence if quality is poor
        if not quality_check['passed']:
            state['confidence_score'] = min(state.get('confidence_score', 0.5), quality_check['quality_score'])

        
        state['reasoning_history'].append({
            'node': 'job_quality_checker',
            'action': 'quality_check',
            'passed': quality_check['passed'],
            'score': quality_check['quality_score'],
            'issues': len(quality_check['issues']),
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"Quality check {quality_check['quality_score']:.2f} ) -"
             f"{'PASSED' if quality_check['passed'] else 'FAILED'}")
        
        state = convert_numpy_types(state)
        
        return state
    
    async def job_report_generator_node(self, state: AgentState) -> AgentState:
        """Generate Job matching report"""

        matched_jobs = state.get('matched_jobs', [])
        resume_text = state.get('resume_text', '')[:500] if state.get('resume_text') else ''

        # 🔧 FIX: Handle no jobs case
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
            
            state['reasoning_history'].append({
                'node': 'job_report_generator',
                'action': 'generate_fallback_report',
                'jobs_included': 0,
                'timestamp': datetime.now().isoformat()
            })
            
            logger.info("📄 Fallback report generated")
            return state

        # EXISTING CODE: Normal report generation when jobs exist
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
            
            # Full description
            description = job.get('description', 'No description available')
            
            # Tags/Skills
            tags = job.get('tags', [])
            tags_str = ', '.join(tags[:8]) if tags else 'Not specified'
            
            # Reasoning
            reasoning = job.get('ranking_reasoning', {})
            why_good = reasoning.get('why_good_fit', [])
            concerns = reasoning.get('potential_concerns', [])
            recommendation = job.get('recommendation', 'Review')
            
            # Build detailed section
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
            
            job_details += f"\n**💡 Recommendation:** {recommendation}\n\n"

        report += job_details

        ## Update store in state
        state['final_output'] = report
        state['final_report'] = report
        state['report_data'] = {
            'report_text': report,
            'matched_jobs': matched_jobs,
            'timestamp': datetime.now().isoformat()
        }

        state['reasoning_history'].append({
            'node': 'job_report_generator',
            'action': 'generate_report',
            'jobs_included': len(matched_jobs),
            'timestamp': datetime.now().isoformat()
        })


        # 🆕 Save detailed JSON file
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
                    'recommendation': job.get('recommendation')
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

            state = convert_numpy_types=(state)
            state['confidence_score'] = float(state.get('confidence_score', 0.0))
            if 'matched_jobs' in state:
                state['matched_jobs'] = convert_numpy_types(state['matched_jobs'])
       
            return state

    async def memory_storage_node(self, state: AgentState) ->AgentState:
        """
        Store resume and Context in Persistent Memory
        """
        user_id = state.get('user_id', 'anonymous')
        resume_text = state.get('resume_text', '')

        if resume_text:
            ## Extract Skills from state
            skills = state.get('job_keywords', [])

            #Store Resume
            resume_id = await self.memory.store_resume(
                user_id =user_id,
                resume_text=resume_text,
                skills=skills,
                experience_years=self._estimate_experience(resume_text),
                metadata= {'task_id': state['task_id']}
            )

            state['resume_id']=resume_id

            logger.info(f"Resume stored in memory: {resume_id}")

        state['reasoning_history'].append({
            'node': 'memory_storage',
            'action': 'store_resume',
            'resume_id': state.get('resume_id'),
            'timestamp': datetime.now().isoformat()
        })

        return state
    
    async def memory_retrieval_node(self, state:AgentState)->AgentState:
        """New: Retrive RAG Context before Matching"""

        user_id = state.get('user_id', 'anonymous')
        resume_text = state.get('resume_text', '')
        jobs = state.get('jobs_data', [])

        ## Get RAG context

        rag_context = await self.memory.get_rag_context_for_matching(
            user_id = user_id,
            resume_text=resume_text,
            current_jobs = jobs
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

        logger.info(f"🧠 RAG Context normalized: {len(rag_context['similar_resumes'])} similar resumes found")
        # Store context in state for other nodes to use

        state['rag_context']=rag_context
        state['user_preferences']= rag_context.get('user_preferences',{})
        state['similar_past_searches']=rag_context.get('similar_resumes', [])


        logger.info(f" RAG Context retriver: quality {rag_context['context_quality']:.2f}")

        state['reasoning_history'].append({
            'node': 'memory_retriver',
            'action': 'retrive_rag_context',
            'context_quality': rag_context['context_quality'],
            'similary_resumes_found': len(rag_context['similar_resumes']),
            'match_history_count': len(rag_context['match_history']),
            'timestamp': datetime.now().isoformat()
        })

        return state


    async def memory_job_storage_node(self, state: AgentState) ->AgentState:
        """RAG: Store Scraped jobs after scraping"""

        jobs= state.get('jobs_data', [])

        if jobs:
            search_context = {
                'keywords': state.get('job_keywords', []),
                'location': state.get('location', 'Remote'),
                'experience_level': state.get('experience_level', 'mid')
            }

            store_count = await self.memory.store_jobs(
                jobs=jobs,
                search_context=search_context
            )

            logger.info(f" Stored: {store_count} jobs in memory")


            state['reasoning_history'].append({
                'node': 'memory_job_storage',
                'action': 'store_jobs',
                'jobs_stored': len(jobs),
                'timestamp': datetime.now().isoformat()
            })

            return state

    async def memory_learning_node(self, state:AgentState)->AgentState:
        """NEW: Store match results and learn from them
        Runs after matching is complete"""

        user_id = state.get('user_id', 'anonymous')
        resume_id = state.get('resume_id', '')
        matched_jobs = state.get('matched_jobs', [])


        ## Store successful matches for learning
        for job in matched_jobs[:10]:
             await self.memory.store_successful_match(
                user_id=user_id,
                resume_id=resume_id,
                job=job,
                match_score= state.get('match_score',0.0),
                user_action= 'shown'
             )

        # learn user preferences from this search

        preferences = {
            'resume_snippet': state.get('resume_text', '')[:500],
            'job_keywords': ', '.join(state.get('job_keywords', [])),  
            'preferred_titles': ', '.join([j.get('title', '') for j in matched_jobs[:3]]),  
            'preferred_companies': ', '.join([j.get('company', '') for j in matched_jobs[:3]]),
            'preferred_location': state.get('job_location', 'Remote'),  
            'avg_match_score': float(state.get('confidence_score', 0)),  
            'timestamp': datetime.now().isoformat() 
        }


        await self.memory.update_user_preferences(
            user_id =user_id,
            preferences=preferences
        )

        logger.info(f" Learning Complete Stored: {len(matched_jobs[:10])} matches")

        state['reasoning_history'].append({
            'node': 'memory_learning',
            'action': 'store_matched_and_learn',
            'matches_stored': len(matched_jobs[:10]),
            'timestamp': datetime.now().isoformat()
        })

        return state

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
    
    # New Advanced Nodes

    async def skills_analysis_node(self, state: AgentState) -> AgentState:
        """Deep Skill Extraction and Analysis"""
        logger.info("Starting Deep skill analysis...")

        # Initialize skill extractor
        if not hasattr(self, 'skill_extractor'):
            self.skill_extractor = SkillsExtractor()

        resume_text = state.get('resume_text', '')
        jobs = state.get('jobs', [])

        # Extract Skills from resume
        resume_skills = self.skill_extractor.extract_from_text(
            text=resume_text,
            include_proficiency=True
        )

        logger.info(f"Extracted {resume_skills['total_count']} skills from resume")
        logger.info(f"Categories: {list(resume_skills['categorized'].keys())}")

        # Extract Skills from each job
        job_skills_analysis = []
        for job in jobs:
            job_text = f"{job.get('title', '')} {job.get('description', '')}"
            job_skills = self.skill_extractor.extract_from_text(
                text=job_text,
                include_proficiency=True
            )

            # Compare with resume
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

        # Build Skill Graph
        skill_graph = self.skill_extractor.build_skill_graph(resume_skills['skills'])

        # Store in State
        state['resume_skills'] = resume_skills
        state['job_skills_analysis'] = job_skills_analysis
        state['skill_graph'] = skill_graph

        # Log reasoning
        state['reasoning_history'].append({
            'node': 'skills_analysis',
            'action': 'deep_skill_extraction',
            'resume_skills_count': resume_skills['total_count'],
            'categories': list(resume_skills['categorized'].keys()),
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"✅ Skills analysis complete: {resume_skills['total_count']} skills identified")

        return state
    
    async def intelligent_ranker_node(self, state: AgentState) ->AgentState:
        """Ranks Jobs by compoiste score with expllanation"""
        logger.info(f" Starting intelligent ranker")

        matched_jobs = state.get('matched_jobs', [])
        job_skill_analysis = state.get('job_skill_analysis', [])
        rag_context = state.get('rag_context', {})
        user_preferences = state.get('user_preferences', {})

        ranked_jobs = []
        for job in matched_jobs:
            # Skill comparison
            skill_comp =next(
                (ja['skill_comparion'] for ja in job_skill_analysis
                if ja ['job_title'] == job.get('title')),
                None
            )

            ## Calculate Compsite ScorE
            scores = self._calculate_composite_score(
                job,
                skill_comp,
                rag_context,
                user_preferences
            )

            ## Genrate Reasoning
            reasoning = self._generate_job_reasoning(
                job,
                skill_comp,
                scores

            )

            ## Add ranking data
            job['composite_score']=float(scores['composite'])
            job['score_breakdown']=scores
            job['ranking_reasoning']=reasoning
            job['recommendation'] = self._generate_recommendation(scores)

            ranked_jobs.append(job)

            ## Sort by composite Score
            ranked_jobs.sort(key=lambda x: x['composite_score'], reverse=True)

            ## Add rank numbers
            for i, job in enumerate(ranked_jobs, 1):
                job['rank'] =i
            
            ## Store ranked jobs
            state['ranked_jobs'] = ranked_jobs[:15]

            ## Update matched jobs with ranked
            state['matched_jobs'] = ranked_jobs[:15]

            state['reasoning_history'].append({
                'node': 'intelligent_ranker',
                'action': 'multi_factor_ranking',
                'jobs_ranked': len(ranked_jobs),
                'top_score': ranked_jobs[0]['composite_score'] if ranked_jobs else 0,
                'timestamp': datetime.now().isoformat()
            })
        
        logger.info(f" Ranked {len(ranked_jobs)} jobs - Top score: {ranked_jobs[0]['composite_score']:.2f}" if ranked_jobs else "No jobs to work")
        
        return state

    def _calculate_composite_score(self, job: Dict, skill_comp: Dict, rag_context: Dict, user_prefs: Dict) ->Dict:
        """Calculate Multifacctor composite score """

        scores = {}

        # Skill match score
        if skill_comp:
            skill_score = (
                skill_comp.get('match_percenatage', 0) / 100 * 0.7 +
                skill_comp.get('strength_score', 0) * 0.3
            )
        else:
            skill_score = job.get('match_score', 0.5)
        scores['skill_match'] = skill_score

        ## Embedding score
        embedding_score = job.get('matched_score', 0.5)
        scores['embedding_similarity'] =embedding_score

        # Location Preferences

        job_location = (job.get('location')  or "").lower()
        preferred_location = user_prefs.get('preferred_location', ['remote'])[0].lower()
        location_score = 1.0 if preferred_location in job_location else 0.5
        scores['location_match'] = location_score

        ## Check if similar jobs were good matches as past
        similar_matches = rag_context.get('similar_past_jobs',[])
        history_score = 0.7
        if similar_matches:
            avg_similarity = float(np.mean([m.get('similarity', 0.5) for m in similar_matches[:3]]))
            history_score = avg_similarity
        scores['historical_performance'] =history_score

        # Job source quality
        source_quality = {
            'indeed_direct': 0.9,
            'google_search': 0.8,
            'remoteok': 0.85,
            'hackernews': 0.95,
            'sample_data': 0.3
        }

        source_score =  source_quality.get(job.get('source', 'unknown'), 0.5)
        scores['source_quality']=source_score

        # Completeness

        completeness = 0.0
        if job.get('title'): completeness += 0.3
        if job.get('company'): completeness +=0.3
        if job.get('description') and len(job.get('description', '')) >50: completeness += 0.4
        scores['completeness'] = completeness


        ## Calculate Compsites
        composite = (
            scores['skill_match'] * 0.40 +
            scores['embedding_similarity'] * 0.25 +
            scores['location_match'] * 0.15 +
            scores['historical_performance'] * 0.10 +
            scores['source_quality'] * 0.05 +
            scores['completeness'] * 0.05 
        )

        scores['composite'] = composite
    
        return scores
    

    def _generate_job_reasoning(self, job:Dict, skill_comp: Dict, scores: Dict) ->Dict:
        """Generate Detailed reasoning for job recommendation"""

        reason_good = []
        reason_concern = []

        # Skill match reasoning
        if skill_comp:
            match_pct = skill_comp.get('match_percentage', 0)
            if match_pct >= 70:
                reason_good.append(f" Strong skill match ({match_pct:.0f}) % of requirement met")
            elif match_pct >= 50:
                reason_good.append(f"Good skill overlap {match_pct:.0f}% match")
            else:
                reason_good.append(f" Only {match_pct:.0f}% skill match")

            ## Misiing Skills
            critical_missing = skill_comp.get('critical_missing', [])
            if critical_missing:
                reason_concern.append(f" Critical missing skills {', '.join(critical_missing[:3])}")
            
            # Strenghts
            strengths = skill_comp.get('strength_score', 0)
            if strengths >=0.8:
               reason_good.append("Your skills are at senior/expert level for this role")
            
            # Location
        if scores.get('location_match', 0) >=0.9:
           reason_good.append("Perfect Location match")
            
        #Source quality

        if scores.get('source_quality', 0) >= 0.8:
            reason_good.append("From reputable job source")

        
        ## Overall resoning
        composite = scores.get('composite', 0)
        if composite >= 0.8:
            overall = "Excellent match - Highly recommended"
        
        elif composite >= 0.6:
            overall = "Good match - Worth applying"
        
        elif composite >= 0.4:
            overall = "Moderate match - Consider if interested"
        
        else:
            "Lower match - may not be ideal"
        
        return {
            'why_good_fit': reason_good,
            'potential_concerns': reason_concern,
            'overall_assessment': overall,
            'confidence': composite
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
    
    async def meta_reasoner_node(self, state:AgentState) ->AgentState:
        """Meta reasoning about the cognitive search Evaluates and suggests improvements"""
        logger.info(f" Starting Meta Reasoning")

        matched_jobs = state.get('matched_jobs', [])
        resume_skills = state.get('resume_skills', {})
        rag_context = state.get('rag_context', {})

        ## Evaluate Search Quality
        evaluation = {
            'search_quality': self._evaluate_search_quality(matched_jobs),
            'skill_coverage': self._evaluate_skill_coverage(matched_jobs, resume_skills),
            'diversity_score': self._evaluate_diversity(matched_jobs),
            'context_quality': rag_context.get('context_quality', 0.0)
        }

        # Generate Insights
        insights = self._generate_meta_insights(evaluation, state)

        # Suggestions inprovments
        suggestions = self._generate_suggestions(evaluation, matched_jobs, resume_skills)


        # Calculate Overall Confidence
        overall_confidence = np.mean([
            evaluation['search_quality'],
            evaluation['skill_coverage'],
            evaluation['diversity_score'],
            evaluation['context_quality']
        ]) 

        # Store meta-reasoning results

        state['meta_reasoning']= {
            'evaluation': evaluation,
            'insights': insights,
            'suggestions': suggestions,
            'overall_confidence': overall_confidence
        }

        # Update main Confidence score
        state['confidence_score'] = float(overall_confidence)

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

        # Check composite score
        scores = [j.get('composite_score', 0) for j in jobs]
        avg_score = np.mean(scores)

        # Check if we have high qaulity matches
        high_quality = sum(1 for s in scores if s >= 0.6)
        quality_ratio = high_quality / len(jobs)

        return (avg_score * 0.6 + quality_ratio * 0.4)
    
    def _evaluate_skill_coverage(self, jobs: List[Dict], resume_skills: Dict) ->float:
        """Evaluate how well jobs utilize resume skills"""

        if not jobs or not resume_skills:
            return 0.5
        
        # Check if job matches resume skills
        resume_categories = set(resume_skills.get('categorized', {}).keys())

        relevant_count = 0
        for job in jobs:
            job_text = f"{job.get('title', '')} {job.get('descripiton', '')}".lower()

            # Check if jobs mention resume categories
            if any(cat in job_text for cat in resume_categories):
                relevant_count += 1
        
        return relevant_count / len(jobs) if jobs else 0.0
    
    def _evaluate_diversity(self, jobs: List[Dict])-> float:
        """Evaluate diversity of jobs results"""

        if not jobs:
            return 0.0

        # Check companies doversity
        companies = set(j.get('companies', 'unknown') for j in jobs)
        company_diversity = min(1.0, len(companies) / max(5, len(jobs) * 0.5))

        # check location
        locations = set(j.get('location', 'unknown') for j in jobs)
        location_diversity = min(1.0, len(locations) / 3)


        return (company_diversity * 0.6 + location_diversity * 0.4 )

    def _generate_meta_insights(self, evaluation: Dict, state:AgentState) ->List[str]:
        """Generate High-levels insights search"""
        insights = []

        # Quality insights
        quality = evaluation['search_quality']
        if quality >= 0.7:
            insights.append("Search produced high quality matches")
        
        elif quality <= 0.5:
            insights.append("Serach quality can be improved -  Consider broader criteria")
        
        # skill coverage
        coverage = evaluation['skill_coverage']

        if coverage >= 0.8:
            insights.append("Jobs strongy align with your skill set")
        elif coverage < 0.5:
            insights.append("Many jobs don't fully utilize with your skills - Consider specializing Search")
        
        # Context quality
        context_qual = evaluation['context_quality']

        if context_qual >= 0.7:
            insights.append("Strong context available - results improving by time")
        
        elif context_qual < 0.3:
            insights.append("Limited data - system will improve with future searches")
        
        # job count
        job_count = len(state.get('matched_jobs', []))

        if job_count < 5:
            insights.append(f"Only {job_count} Found - Consider more broader searches")
        
        elif job_count >=10:
            insights.append(f" Found {job_count} opportunities - Strong job market presence")
        
        return insights
    
    def _generate_suggestions(self, evaluation: Dict, jobs: List[Dict], resume_skills: Dict) -> List[str]:
        """Generate actionable suggestions"""
        suggestions = []

        # Search quality suggestions
        if evaluation['search_quality'] < 0.6:
             suggestions.append("Try adding more specific keywords related to your experience")
             suggestions.append("Consider expanding location preferences")

    # Skill development suggestions
        if jobs:
            # Find commonly required skills user doesn't have
            all_required = set()
            for job in jobs[:5]:
                desc = job.get('description', '').lower()
                # Simple keyword extraction (could be enhanced)
                for skill_cat in ['python', 'react', 'aws', 'kubernetes']:
                    if skill_cat in desc:
                        all_required.add(skill_cat)
            
            user_skills = set(s['name'] for s in resume_skills.get('skills', []))
            missing = all_required - user_skills
            
            if missing:
                suggestions.append(f"Consider learning: {', '.join(list(missing)[:3])}")

        # Application strategy
        if evaluation['diversity_score'] < 0.5:
            suggestions.append("Results are concentrated - try searching different job boards")

        return suggestions

   


        



    
    
    



         


















        










    















    
 











