"""
Context Packet Assembler
Constructs minimal, strictly-scoped JSON context packets for each report section.
Enforces the core PV principle: each section LLM call only receives data declared in its configuration.
"""

from typing import Any, Dict, List
from src.config import ReportConfig, SectionConfig
from src.data_loader import DatasetMetadata


class PacketAssembler:
    """
    Assembles scoped context packets for LLM section generation.
    Maintains complete data isolation between sections.
    """

    def __init__(self, report_config: ReportConfig, metadata: DatasetMetadata):
        self.report_config = report_config
        self.metadata = metadata

    def build_packet(
        self,
        section_config: SectionConfig,
        all_analysis_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Builds an isolated context packet containing ONLY the pre-computed analyses
        requested by the section configuration.
        """
        # Filter pre-computed analyses to only those explicitly declared
        scoped_evidence: Dict[str, Any] = {}
        for analysis_key in section_config.analyses:
            if analysis_key in all_analysis_results:
                scoped_evidence[analysis_key] = all_analysis_results[analysis_key]
            else:
                scoped_evidence[analysis_key] = {
                    "status": "unavailable",
                    "reason": f"Analysis '{analysis_key}' was not found in analysis results."
                }

        packet = {
            "report_metadata": {
                "report_type": self.report_config.report_type,
                "report_title": self.report_config.title,
                "product_name": self.report_config.product_name,
                "regulatory_framework": self.report_config.regulatory_framework,
                "reporting_period_start": self.metadata.reporting_period_start,
                "reporting_period_end": self.metadata.reporting_period_end,
                "total_unique_cases": self.metadata.unique_cases,
                "total_raw_records": self.metadata.total_rows,
            },
            "section_info": {
                "section_id": section_config.section_id,
                "section_name": section_config.name,
                "display_order": section_config.display_order,
                "format_type": section_config.format_type,
                "instructions": section_config.instructions.strip(),
            },
            "declared_analyses": section_config.analyses,
            "evidence_packet": scoped_evidence,
            "data_health_and_limitations": {
                "soc_available": False,
                "soc_note": "No MedDRA System Organ Class (SOC) mapping exists in source dataset; analysis restricted to PT level.",
                "rsi_ccds_available": False,
                "rsi_note": "No Company Core Data Sheet (CCDS) or US Product Label provided; expectedness/labeledness is out of scope.",
                "history_of_actions_available": False,
                "history_of_actions_note": "No regulatory or company history of actions provided.",
                "country_divergence_cases": self.metadata.country_divergence_count,
            }
        }

        return packet

    def build_all_packets(
        self,
        all_analysis_results: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Builds context packets for all sections in the report configuration."""
        packets = {}
        for section in self.report_config.sections:
            packets[section.section_id] = self.build_packet(section, all_analysis_results)
        return packets
