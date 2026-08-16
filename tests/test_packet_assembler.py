"""
Unit tests for context packet assembler.
Verifies data isolation: sections only receive their declared analyses.
"""

import pytest
from src.config import ReportConfig, SectionConfig
from src.data_loader import DatasetMetadata
from src.packet_assembler import PacketAssembler


@pytest.fixture
def mock_setup():
    metadata = DatasetMetadata(
        total_rows=100,
        unique_cases=90,
        reporting_period_start="2024-01-01",
        reporting_period_end="2024-12-31",
        product_name="TestDrug",
        country_divergence_count=2,
    )
    section1 = SectionConfig(
        name="Section 1",
        section_id="sec1",
        analyses=["total_cases", "breakdown_by_sex"],
        instructions="Summarize demographics.",
        display_order=1,
    )
    section2 = SectionConfig(
        name="Section 2",
        section_id="sec2",
        analyses=[],
        instructions="Empty analysis section.",
        display_order=2,
    )
    config = ReportConfig(
        report_type="PADER",
        title="Test Report",
        product_name="TestDrug",
        sections=[section1, section2],
    )
    mock_analyses = {
        "total_cases": {"unique_cases": 90},
        "breakdown_by_sex": {"Female": 50, "Male": 40},
        "top_reactions": {"Bradycardia": 10},
        "outcomes_summary": {"Fatal": 5},
    }
    return config, metadata, mock_analyses


def test_packet_isolation(mock_setup):
    config, metadata, mock_analyses = mock_setup
    assembler = PacketAssembler(config, metadata)

    packet1 = assembler.build_packet(config.sections[0], mock_analyses)
    
    # Section 1 requested total_cases and breakdown_by_sex
    assert "total_cases" in packet1["evidence_packet"]
    assert "breakdown_by_sex" in packet1["evidence_packet"]
    # Section 1 MUST NOT have top_reactions or outcomes_summary
    assert "top_reactions" not in packet1["evidence_packet"]
    assert "outcomes_summary" not in packet1["evidence_packet"]

    # Metadata checks
    assert packet1["report_metadata"]["product_name"] == "TestDrug"
    assert packet1["report_metadata"]["reporting_period_start"] == "2024-01-01"


def test_empty_packet_isolation(mock_setup):
    config, metadata, mock_analyses = mock_setup
    assembler = PacketAssembler(config, metadata)

    packet2 = assembler.build_packet(config.sections[1], mock_analyses)
    # Section 2 declared no analyses
    assert len(packet2["evidence_packet"]) == 0
    assert packet2["section_info"]["instructions"] == "Empty analysis section."
