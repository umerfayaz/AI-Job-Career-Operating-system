# System Workflows

This document describes the core workflows of the AI Job Career Operating System.

The platform contains:

1. Resume Upload Workflow
2. Job Matching Workflow
3. Report Generation Workflow
4. Applied Job Tracking Workflow
5. No Response Workflow
6. Dead Application Workflow
7. Strategic Optimization Workflow
8. Autonomous Refetch Workfl

Purpose:

Convert a user resume into actionable job opportunities.

Workflow:

User uploads resume
→ Resume Parser
→ Skills Extraction
→ Profile Analysis
→ LangGraph Workflow Start
→ Job Search
→ Hybrid Retrieval
→ Reranking
→ Report Generation
→ Report Delivery

Output:

Structured candidate profile
Ranked jobs
Match scores
Personalized report


# Section 3 — Job Matching Workflow

## Job Matching Workflow

Purpose:

Identify the most relevant jobs for a candidate.

Workflow:

Resume
→ Embedding Generation
→ Dense Retrieval
→ Keyword Retrieval
→ RRF Fusion
→ Reranker
→ Match Scoring
→ Ranked Results

Components:

ChromaDB
Hybrid Retriever
RRF Fusion
Cross Encoder Reranker


# Section 4 — Report Generation Workflow

## Report Generation Workflow

Purpose:

Transform job matches into a user-friendly report.

Workflow:

Matched Jobs
→ Report Generator Agent
→ Ranking Summary
→ Recommendation Section
→ Action Links
→ Email Delivery

Generated Content:

Top matched jobs
Match explanations
Job links
Career recommendations


# Section 5 — Applied Job Workflow

This is where your platform becomes unique.


## Applied Job Tracking Workflow

Purpose:

Track jobs after the user applies.

Workflow:

User clicks Apply
→ Job saved in PostgreSQL
→ Status = applied
→ Tracking record created
→ Tracking email sent

Database State:

Job ID
User ID
Applied Date
Current Status
Tracking Metadata




# Section 6 — No Response Workflow

## No Response Workflow

Purpose:

Detect applications receiving no employer response.

Trigger:

Configured response window expires.

Workflow:

Applied Job
→ Outcome Tracker
→ No employer response
→ Status becomes no_response
→ Notification Agent
→ User receives update email

Actions:

Update metrics
Notify user
Trigger Follow-Up Agent


# Section 7 — Follow-Up Agent Workflow

## Follow-Up Agent Workflow

Purpose:

Help users re-engage employers.

Workflow:

Status = no_response
→ Follow-Up Agent
→ Generate follow-up email
→ Deliver template to user

Generated Content:

Follow-up email
Reminder message
Communication suggestions


# Section 8 — Dead Application Workflow

This is where Brain4 becomes important.

## Dead Application Workflow

Purpose:

Detect failed opportunities.

Trigger:

Extended inactivity period.

Workflow:

no_response
→ Monitoring Window Expires
→ Status becomes dead_application
→ Metrics Updated
→ Strategic Agent Triggered

Impact:

Response rate decreases
Dead application count increases
Source quality metrics updated


# Section 9 — Strategic Agent Workflow

This is your Brain3.

## Strategic Agent Workflow

Purpose:

Improve job sourcing performance.

Inputs:

- Response rates
- Dead applications
- Successful matches
- Interview rates

Workflow:

Metrics Analysis
→ Failure Detection
→ Policy Creation
→ Source Agent Trigger

Possible Decisions:

Change keywords
Adjust filters
Switch APIs
Modify sourcing strategy


# Section 10 — Source Agent Workflow

## Source Agent Workflow

Purpose:

Implement sourcing improvements.

Workflow:

Strategic Policy
→ Source Agent
→ Keyword Update
→ Source Selection
→ Search Configuration Update

Example:

Old Source:
JSearch API

New Source:
Remotive API

Example:

Old Keywords:
Frontend Developer

New Keywords:
AI Engineer
LangGraph Developer
Remote AI Developer

# Section 11 — Autonomous Refetch Workflow

This is the final feedback loop.

## Autonomous Refetch Workflow

Purpose:

Launch improved job searches after strategic updates.

Workflow:

Dead Applications Increase
→ Strategic Agent
→ Source Agent
→ New Keywords
→ New Job Source
→ Autonomous Search
→ Fresh Job Pool
→ Matching Pipeline
→ New Report

Outcome:

Continuous sourcing improvement.

# Section 12 — Complete System Loop

End with the strongest diagram:

## Complete Autonomous Lifecycle

flowchart TD

A[Resume Upload]

A --> B[Job Matching]

B --> C[Report Generated]

C --> D[User Applies]

D --> E[Applied Status]

E --> F[Outcome Tracking]

F --> G[No Response]

G --> H[Follow Up Agent]

G --> I[Dead Application]

I --> J[Metrics Update]

J --> K[Strategic Agent]

K --> L[Source Agent]

L --> M[New Keywords]

L --> N[New Job Source]

M --> O[Autonomous Refetch]

N --> O

O --> B


