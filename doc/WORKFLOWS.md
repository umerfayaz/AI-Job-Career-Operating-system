# System Workflows

## Resume Upload Workflow

### Purpose

Convert a user resume into actionable job opportunities.

### Workflow

```txt
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
```

### Output

* Structured candidate profile
* Ranked jobs
* Match scores
* Personalized report

## Complete Autonomous Lifecycle

```mermaid
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
```


