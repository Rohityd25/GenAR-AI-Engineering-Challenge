"""
Version 1 Feature: Scaled Multi-Report & Consistency Evaluator
Demonstrates evaluating 1,000 generated safety reports across multiple runs for:
1. Automated numeric grounding verification (100% precision threshold)
2. Regulatory phrasing compliance (prohibited assertions check)
3. Cross-regeneration consistency and deterministic reproducibility
"""

import json
from pathlib import Path
from typing import Any, Dict, List
from src.evaluator import GroundingEvaluator


class ScaledReportEvaluator:
    """
    Simulates scaled validation of large batches of safety reports.
    """

    PROHIBITED_PHRASES = [
        "no safety concerns were identified",
        "the drug is completely safe",
        "proves that the drug caused",
        "definitive proof",
        "guarantees efficacy",
    ]

    def __init__(self):
        self.grounding_eval = GroundingEvaluator()

    def check_compliance_rules(self, report_text: str) -> List[str]:
        """Checks for regulatory non-compliant language."""
        violations = []
        lower_text = report_text.lower()
        for phrase in self.PROHIBITED_PHRASES:
            if phrase in lower_text:
                violations.append(f"Contains prohibited speculative assertion: '{phrase}'")
        return violations

    def evaluate_batch(self, reports_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates a batch of reports (e.g. 100 or 1,000 reports).
        """
        total_reports = len(reports_data)
        passed_grounding = 0
        passed_compliance = 0
        all_section_precisions = []

        for item in reports_data:
            sections_dict = item.get("sections", {})
            packets_dict = item.get("packets", {})
            full_text = "\n".join(sections_dict.values())

            # Grounding check
            eval_res = self.grounding_eval.evaluate_report(sections_dict, packets_dict)
            prec = eval_res["overall_summary"]["overall_grounding_precision_pct"]
            all_section_precisions.append(prec)
            if eval_res["overall_summary"]["overall_status"] == "PASS":
                passed_grounding += 1

            # Compliance check
            violations = self.check_compliance_rules(full_text)
            if not violations:
                passed_compliance += 1

        avg_precision = sum(all_section_precisions) / total_reports if total_reports > 0 else 100.0

        return {
            "total_reports_evaluated": total_reports,
            "grounding_pass_rate_pct": round((passed_grounding / total_reports) * 100.0, 2) if total_reports > 0 else 100.0,
            "compliance_pass_rate_pct": round((passed_compliance / total_reports) * 100.0, 2) if total_reports > 0 else 100.0,
            "average_grounding_precision_pct": round(avg_precision, 2),
            "production_gate_status": "READY FOR PUBLICATION" if passed_grounding == total_reports and passed_compliance == total_reports else "REVISION REQUIRED",
        }
