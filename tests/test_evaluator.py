"""
Unit tests for the automated grounding evaluator.
Verifies that hallucinated numbers are flagged and grounded numbers pass with 100% precision.
"""

import pytest
from src.evaluator import GroundingEvaluator


def test_extract_numbers():
    evaluator = GroundingEvaluator()
    text = "In 2025, a total of 1,024 cases were reported, representing 99.9% serious cases."
    nums = evaluator.extract_numbers_from_text(text)
    assert "2025" in nums
    assert "1024" in nums
    assert "99.9" in nums


def test_evaluate_section_grounded():
    evaluator = GroundingEvaluator()
    text = "A total of 1024 cases were reported, with 1023 serious cases (99.9%)."
    packet = {
        "report_metadata": {"total_unique_cases": 1024},
        "section_info": {"section_id": "sec1", "section_name": "Summary"},
        "evidence_packet": {
            "serious_vs_nonserious": {
                "serious_cases": 1023,
                "serious_percentage": 99.9,
            }
        },
        "data_health_and_limitations": {},
    }
    res = evaluator.evaluate_section("sec1", "Summary", text, packet)
    assert res["status"] == "PASS"
    assert res["ungrounded_numbers_count"] == 0
    assert res["grounding_precision_pct"] == 100.0


def test_evaluate_section_hallucination_flagged():
    evaluator = GroundingEvaluator()
    # 99999 is a fabricated number not present in the packet
    text = "A total of 99999 fabricated cases were reported in 2025."
    packet = {
        "report_metadata": {"total_unique_cases": 1024},
        "section_info": {"section_id": "sec1", "section_name": "Summary"},
        "evidence_packet": {"total_cases": {"unique_cases": 1024}},
        "data_health_and_limitations": {},
    }
    res = evaluator.evaluate_section("sec1", "Summary", text, packet)
    assert res["status"] == "FLAGGED"
    assert "99999" in res["ungrounded_tokens"]
