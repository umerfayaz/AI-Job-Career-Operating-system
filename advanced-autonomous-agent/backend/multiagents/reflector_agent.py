"""Reflector - Agent Quality check and feeback loop"""

from typing import List, Dict, Any

class RefelctorAgent:
    def __ini__(self, quality_threshold: Dict[str, float] = None):
        self.threshold = quality_threshold or {
            "min_match_score": 0.6,
            "min_jobs_count": 5,
            "min_report_lenght": 500
        }

    def check_quality(self, report_data: Dict[str, Any]) ->Dict[str, Any]:
        """Evaluates report quality and provides Feddbacl"""

        issues =[]
        recomendations = []


        ## Check job matches
        jobs =  report_data.get("matched_jobs", [])
        if not jobs:
            issues.append("No matched jobs found")
            recomendations.append("Broaden search criteria or update resume")
        
        avg_score = sum(j.get("matched_score", []) for j in jobs) / len(jobs) if jobs else 0


        if avg_score < self.threshold["min_match_score"]:
            issues.append(f"Average match score is too low {avg_score}")
            recomendations.append("Consider adjusting matching algorithms or resume keywords")
        
        if len(jobs) < self.threshold["min_jobs_count"]:
            issues.append(f"Only {len(jobs)} jobs found")
            recomendations.append("Expand search to more jobs or locations")

        
        ## Check report Completness
        report_text =  report_data.get("report_text", "")
        if len(report_text) < self.threshold["min_report_length"]:
            issues.append("Report too short")
            recomendations.append("Generate more detailed report")

        quality_score = self._calculate_quality_score(report_data, issues)

        return {
            "passed": len(issues) == 0,
            "quality_score": quality_score,
            "issues": issues,
            "recomendations": recomendations,
            "requires_retry": quality_score < 0.7
        }




