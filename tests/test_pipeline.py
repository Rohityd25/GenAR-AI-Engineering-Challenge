"""
End-to-end pipeline integration tests.
Verifies full data flow from raw input to evaluated multi-format reports.
"""

from pathlib import Path
import pytest
from src.pipeline import SafetyReportPipeline


def test_pipeline_execution_synthetic(tmp_path):
    # Test on the real dataset if present, or synthetic
    dataset_path = r"C:\Users\ROHIT YADAV\Downloads\Bisoprolol_icsr_sample_1068rows.xlsx"
    if not Path(dataset_path).exists():
        pytest.skip("Dataset file not available at test path.")

    out_dir = tmp_path / "test_output"
    pipeline = SafetyReportPipeline(
        input_data_path=dataset_path,
        config_path="configs/pader_config.yaml",
        output_dir=str(out_dir),
        provider="deterministic",
        auto_approve=True,
    )

    results = pipeline.run()

    # Verify all expected artifacts exist
    assert (out_dir / "analyses.json").exists()
    assert (out_dir / "context_packets.json").exists()
    assert (out_dir / "review_store.json").exists()
    assert (out_dir / "report_output.md").exists()
    assert (out_dir / "report_output.html").exists()
    assert (out_dir / "report_output.docx").exists()
    assert (out_dir / "evaluation_report.json").exists()

    # Verify evaluation metrics
    eval_summary = results["evaluation"]["overall_summary"]
    assert eval_summary["overall_grounding_precision_pct"] == 100.0
    assert eval_summary["total_ungrounded"] == 0
    assert eval_summary["overall_status"] == "PASS"

    # Verify report content contains all 8 sections
    report_text = (out_dir / "report_output.md").read_text(encoding="utf-8")
    assert "1. Reporting Period and Product Identification" in report_text
    assert "2. Narrative Summary and Overall Safety Analysis" in report_text
    assert "3. Summary Analysis of Cases" in report_text
    assert "4. Reaction and Adverse Event Analysis" in report_text
    assert "5. Serious Cases and 15-Day Alert Reports" in report_text
    assert "6. Trends and Important Observations" in report_text
    assert "7. History of Safety Actions Taken" in report_text
    assert "8. Line Listing and Case Index" in report_text

    # Verify key data grounding
    assert "1024 unique safety cases" in report_text
    assert "1023 (99.9%)" in report_text
    assert "Acute kidney injury" in report_text
