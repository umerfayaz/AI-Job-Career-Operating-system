from groq import Groq
from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
from backend.config.settings import Settings
import structlog
from typing import Dict
import time
import re
logger = structlog.get_logger()


class LMCClient:

    def __init__(self):
        self.settings = Settings()
        self.client = Groq(api_key=self.settings.GROQ_API_KEY)

    async def generate_job_report(self, resume_text: str, matches: dict) -> str:
        """Generate a comprehensive professional job report
        
        CRITICAL: This now expects matches to come from matched_jobs (state),
        NOT from ChromaDB metadata. The URLs from matched_jobs are verified to work.
        """
        with tracer.start_as_current_span("report_generator.run") as parent_span:
            start_agent = time.time()

            try:
                # Extract match data - DIRECTLY from matched_jobs structure
                match_list = []
                
                # Check if matches is the matched_jobs list directly (from state)
                if isinstance(matches, list):
                    logger.info(f"📦 Received {len(matches)} jobs directly from matched_jobs state")
                    matched_jobs_list = matches
                # Or if it's the ChromaDB format
                elif matches and matches.get("metadatas"):
                    logger.info(f"📦 Received {len(matches['metadatas'])} jobs from ChromaDB format")
                    matched_jobs_list = []
                    documents = matches.get("documents", [])
                    
                    for idx, meta in enumerate(matches["metadatas"][:10]):
                        # Build job dict from metadata
                        match_score = meta.get("match_score", 0)
                        if match_score == 0:
                            match_score = meta.get("match_percentage", 0) / 100.0 if meta.get("match_percentage") else 0
                        
                        try:
                            match_score = float(match_score)
                        except (ValueError, TypeError):
                            match_score = 0.0
                        
                        match_percentage = round(match_score * 100, 1)
                        
                        description = documents[idx] if documents and idx < len(documents) else meta.get("description", "")
                        
                        matched_jobs_list.append({
                            "title": meta.get("job_title") or meta.get("title") or "Position Not Specified",
                            "job_id": meta.get("job_id"),
                            "run_id": meta.get("run_id"),
                            "company": meta.get("company") or "Company Not Specified",
                            "location": meta.get("location") or "Remote/Not Specified",
                            "salary": meta.get("salary_range") or meta.get("salary") or "Competitive (not specified)",
                            "description": description[:1500] if description else "Full job description available upon application",
                            "url": meta.get("redirect_url"),
                            "match_percentage": match_percentage,
                            "match_score": match_percentage,
                            "employment_type": meta.get("employment_type") or meta.get("job_type") or "Full-time",
                        })
                else:
                    logger.error("❌ Invalid matches format received")
                    return "No job matches found."

                # Process matched_jobs_list into clean format
                for job in matched_jobs_list[:10]:
                    url = job.get('redirect_url')

                    if not url:
                        logger.warning(f" No url found for job: {job.get('url')}")
                    
                    # Get match score
                    match_score = job.get('match_percentage', job.get('match_score', 0))
                    if isinstance(match_score, (int, float)):
                        match_score = float(match_score)
                    else:
                        match_score = 0.0
                    
                    match_list.append({
                        "title": job.get('title') or job.get('job_title') or "Position Not Specified",
                        "company": job.get('company') or "Company Not Specified",
                        "location": job.get('location') or "Remote/Not Specified",
                        "salary": job.get('salary') or job.get('salary_range') or "Competitive (not specified)",
                        "description": job.get('description', '')[:1500] if job.get('description') else "Full job description available upon application",
                        "url": url,  
                        "match_score": match_score,
                        "employment_type": job.get('employment_type') or job.get('job_type') or "Full-time",
                    })

                # Sort by match score 
                match_list.sort(key=lambda x: x["match_score"], reverse=True)

                if not match_list:
                    return "No job matches found."

                logger.info(f"🔍 Formatted {len(match_list)} matches. Top score: {match_list[0]['match_score']}%")
                logger.info(f"🔗 URLs available: {sum(1 for m in match_list if m['url'])}/{len(match_list)}")

                
                prompt = f"""
    You are an elite career advisor and technical recruiter creating a comprehensive job matching report.

    CRITICAL URL INSTRUCTIONS:
    1. URLs are provided in format: APPLY_URL: https://example.com
    2. You MUST convert these to markdown links: [Apply Here](https://example.com)
    3. Copy the EXACT URL - do not modify or shorten it
    4. Place the Apply link prominently for EVERY job that has a URL

    CANDIDATE PROFILE:
    {resume_text[:2500]}

    MATCHED OPPORTUNITIES ({len(match_list)} positions):
    {self._format_matches_detailed(match_list)}

    Create a DETAILED, PROFESSIONAL report with these sections:

    ## 📊 Executive Summary
    - Write 2-3 paragraphs analyzing the candidate's profile
    - Highlight key strengths and unique value propositions
    - Mention total matches and score distribution (e.g., "Average match score: X%")
    - Identify the candidate's career positioning

    ## 🎯 Detailed Job Analysis

    For the TOP 5 matches, provide:

    ### [Rank]. [Job Title] at [Company] - **Match: [X]%** 🎯
    📍 **Location:** [location] | 💼 **Type:** [employment_type] | 💰 **Salary:** [salary]

    🔗 **[Apply Here](ACTUAL_URL)** ← MUST be clickable markdown link with EXACT URL

    **Match Breakdown:**
    - **Core Alignment (X/10):** Explain specific skill matches
    - **Experience Fit (X/10):** How their experience aligns
    - **Tech Stack Match (X/10):** Technical requirements vs. candidate skills

    **Why This Role Fits:**
    - 3-4 bullet points with SPECIFIC connections between resume and job
    - Quote actual requirements from the job description
    - Reference candidate's exact skills/experience

    **Job Highlights:**
    - Key responsibilities from the description
    - Required qualifications
    - Nice-to-have skills

    **Red Flags/Gaps:**
    - Any missing qualifications
    - Potential concerns (if any)

    **Application Strategy:**
    - Specific resume customization tips for THIS job
    - Key talking points for interview
    - How to address any gaps

    ---

    ## 📋 Skills Alignment Matrix

    Create a detailed table:

    | Candidate Skill/Experience | Required By | Proficiency Level | Relevance |
    |----------------------------|-------------|-------------------|-----------|
    | [From resume] | [Job 1, Job 2, etc.] | Expert/Advanced/Intermediate | High/Med/Low |

    (Include 10-15 rows covering all major skills)

    ## 💼 Comprehensive Application Strategy

    ### Immediate Actions (This Week)
    1. Prioritized application order with reasoning
    2. Resume customization checklist for top 3 roles
    3. Cover letter key points for each

    ### Application Optimization
    - Portfolio/GitHub recommendations
    - LinkedIn profile updates
    - Skill certifications to pursue

    ### Interview Preparation
    - Common technical questions for these roles
    - Behavioral questions to prepare
    - Project examples to highlight

    ### Long-term Career Development
    - Skills to develop for better matches
    - Industry trends to follow
    - Networking strategies

    ## 🎯 Match Score Distribution
    - High matches (70%+): [count]
    - Good matches (50-70%): [count]
    - Moderate matches (30-50%): [count]

    ## 📈 Key Recommendations
    - Top 3 applications to prioritize and why
    - Expected timeline for applications
    - Success probability assessment

    ---

    **Report Quality Guidelines:**
    ✅ Use actual data from job descriptions
    ✅ Be specific, not generic
    ✅ Provide actionable insights
    ✅ Maintain professional tone
    ✅ Include concrete examples
    ✅ Make ALL URLs clickable markdown links: [Apply Here](url)
    ✅ Show match percentages prominently: **Match: 85%** 🎯
    ✅ Make it comprehensive (aim for 3000+ words)
    """
                
                with tracer.start_as_current_span("LLM.call") as llm_span:
                    start_llm = time.time()
                    llm_span.set_attribute("llm.model", "openai/gpt-oss-120b")

                    response = self.client.chat.completions.create(
                        model = "openai/gpt-oss-120b",   
                        messages=[
                            {
                                "role": "system", 
                                "content": "You are a senior career advisor with 15+ years of experience in technical recruiting and career development. You provide detailed, actionable, and highly personalized job matching reports. ALWAYS convert APPLY_URL: links into proper markdown [Apply Here](url) format. Copy URLs EXACTLY as provided - these are verified working links."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.2
                    )

                    MODEL_NAME = response.model

                    logger.warning(f"Model called for  Report geneartion: {MODEL_NAME}")

                    usage = response.usage

                    if usage:
                        llm_span.set_attribute("llm.prompt", prompt[:500])
                        llm_span.set_attribute("llm.prompt_tokens", getattr(usage, "prompt_tokens", 0))
                        llm_span.set_attribute("llm.completion_tokens", getattr(usage, "completion_tokens", 0))
                        llm_span.set_attribute("llm.total_tokens", getattr(usage, "total_tokens", 0))
                    
                    total_tokens = getattr(usage, "total_tokens", 0)
                    MODEL_COSTS = {
                        MODEL_NAME: 0.0001
                    }
                    cost = (total_tokens / 1000) * MODEL_COSTS.get(MODEL_NAME, 0.0001)

                    llm_span.set_attribute("llm.model", MODEL_NAME)
                    llm_span.set_attribute("llm.total_estimated_cost_usd", cost)
                    llm_span.set_attribute("llm.latency_seconds", time.time() - start_llm)

                    report = response.choices[0].message.content or ""
                    
                    # POST-PROCESS: Convert any remaining APPLY_URL markers to markdown links
                    report = self._clean_urls_in_report(report, match_list)
                    
                    # Ensure all URLs are present
                    report = self._ensure_urls_in_report(report, match_list)
                    
                    logger.info(f"✅ Comprehensive LLM report generated ({len(report)} chars)")
                    logger.info(f"🔗 Final URL check: {report.count('](http')} markdown links in report")
                
                # Tracking Resume and Matches
                parent_span.set_attribute("resume.length", len(resume_text))
                parent_span.set_attribute("matches.count", len(match_list))
                parent_span.set_attribute("matches.top_score", match_list[0]["match_score"])

                return report

            except Exception as e:
                logger.error(f"❌ LLM failed: {e}", exc_info=True)
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))
            
            finally:
                parent_span.set_attribute("llm.latency_seconds", time.time() - start_agent)

    def _format_matches_detailed(self, matches):
        """Format matches with full details for LLM - WITH SCORES AND VERIFIED URLS"""
        formatted = []
        for i, m in enumerate(matches, 1):
            # Use the URL DIRECTLY from matched_jobs (which is in the working JSON)
            url = m.get("url", "").strip() if m.get("url") else None
            
            if url:
                apply_line = f"🔗 APPLY_URL: {url}"
                logger.debug(f"  Job #{i}: {m['title'][:30]} -> {url[:50]}...")
            else:
                apply_line = f"🔗 Apply: Not Available (visit company careers page)"
                logger.warning(f"  Job #{i}: {m['title'][:30]} -> NO URL")

            formatted.append(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH #{i}: {m['title']} at {m['company']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 Match Score: {m['match_score']}%  ⭐
📍 Location: {m['location']}
💰 Salary: {m['salary']}
💼 Type: {m['employment_type']}
{apply_line}

📝 FULL JOB DESCRIPTION:
{m['description']}

""")
        return "\n".join(formatted)

    def _clean_urls_in_report(self, report: str, match_list: list[Dict]) -> str:
        """Convert APPLY_URL: markers to proper markdown links"""
        # Pattern to find APPLY_URL: followed by URL
        pattern = r'APPLY_URL:\s*(https?://[^\s\)]+)'
        
        def replace_with_markdown(match):
            url = match.group(1)
            return f"[Apply Here]({url})"
        
        cleaned = re.sub(pattern, replace_with_markdown, report)
        
        # Count how many we converted
        original_count = report.count('APPLY_URL:')
        final_count = cleaned.count('](http')
        
        logger.info(f"🔧 URL Conversion: {original_count} APPLY_URL markers -> {final_count} markdown links")
        
        return cleaned

    def _ensure_urls_in_report(self, report: str, match_list: list[Dict]) -> str:
        """Ensure all URLs are present and clickable - USING VERIFIED URLS FROM JSON"""
        apply_count = report.count("](http")  # Count markdown links
        jobs_with_urls = sum(1 for m in match_list if m.get('url'))

        if apply_count < min(5, jobs_with_urls):
            logger.warning(f"⚠️ Only {apply_count} apply links found, expected {min(5, jobs_with_urls)}")
            report += "\n\n---\n\n## 🔗 Quick Apply Links (Verified URLs)\n\n"

            for i, match in enumerate(match_list[:10], 1):
                url = match.get("url", "").strip() if match.get("url") else None
                
                if url:
                    report += f"{i}. **{match['title']}** at {match['company']} - Match: **{match['match_score']}%** 🎯\n"
                    report += f"   👉 [Apply Here]({url})\n\n"
                else:
                    report += f"{i}. **{match['title']}** at {match['company']} - Match: **{match['match_score']}%** 🎯\n"
                    report += f"   ℹ️ Visit company website to apply\n\n"
        
        return report 
