"""
Master Pipeline Orchestrator
Executes the end-to-end Pharmacovigilance Periodic Safety Reporting workflow:
Data Loading -> Deterministic Analysis -> Packet Assembly -> Section Generation ->
Review/Approval -> Document Assembly -> Automated Grounding Evaluation.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.data_loader import ICSRDataLoader
from src.analyses import AnalysisRegistry
from src.config import ReportConfig
from src.packet_assembler import PacketAssembler
from src.llm_generator import LLMGenerator
from src.reviewer import ReviewStore
from src.report_assembler import ReportAssembler
from src.evaluator import GroundingEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class SafetyReportPipeline:
    """
    Coordinates the complete lifecycle of safety report generation.
    """

    def __init__(
        self,
        input_data_path: str,
        config_path: str = "configs/pader_config.yaml",
        output_dir: str = "output",
        provider: str = "auto",
        model: Optional[str] = None,
        auto_approve: bool = True,
    ):
        self.input_data_path = Path(input_data_path)
        self.config_path = Path(config_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.provider = provider
        self.model = model
        self.auto_approve = auto_approve

        self.config = ReportConfig.from_yaml(str(self.config_path))
        self.data_loader = ICSRDataLoader(str(self.input_data_path), product_name=self.config.product_name)
        self.review_store = ReviewStore(store_path=str(self.output_dir / "review_store.json"))

    def run(self) -> Dict[str, Any]:
        """Runs the complete end-to-end report generation pipeline."""
        logger.info("=" * 60)
        logger.info(f"STARTING SAFETY REPORT GENERATION: {self.config.title}")
        logger.info(f"Target Product: {self.config.product_name} | Regulatory Standard: {self.config.regulatory_framework}")
        logger.info("=" * 60)

        # 1. Data Ingestion & Validation
        logger.info("STEP 1: Ingesting and validating ICSR dataset...")
        raw_df, case_df, metadata = self.data_loader.load()
        logger.info(
            f"Data summary: {metadata.total_rows} rows -> {metadata.unique_cases} unique cases. "
            f"Period: {metadata.reporting_period_start} to {metadata.reporting_period_end}."
        )

        # 2. Deterministic Analysis Layer (Pure Python)
        logger.info("STEP 2: Executing deterministic analysis layer (zero LLM calls)...")
        analysis_results = AnalysisRegistry.execute_all(case_df, raw_df)
        analyses_file = self.output_dir / "analyses.json"
        with open(analyses_file, "w", encoding="utf-8") as f:
            json.dump(analysis_results, f, indent=2)
        logger.info(f"Pre-computed analysis results saved to {analyses_file}")

        # 3. Context Packet Assembly
        logger.info("STEP 3: Assembling isolated context packets per section...")
        packet_assembler = PacketAssembler(self.config, metadata)
        all_packets = packet_assembler.build_all_packets(analysis_results)
        packets_file = self.output_dir / "context_packets.json"
        with open(packets_file, "w", encoding="utf-8") as f:
            json.dump(all_packets, f, indent=2)
        logger.info(f"Context packets saved to {packets_file}")

        # 4. LLM Generation Layer (One scoped call per section)
        logger.info(f"STEP 4: Generating section content (Provider: {self.provider})...")
        generator = LLMGenerator(
            prompt_template_path="prompts/section_prompt.txt",
            provider=self.provider,
            model=self.model,
            audit_log_path=str(self.output_dir / "prompt_audit_log.jsonl")
        )

        sections_content = {}
        for section in self.config.sections:
            packet = all_packets[section.section_id]
            logger.info(f"Drafting section [{section.display_order}/{len(self.config.sections)}]: {section.name}...")
            content = generator.generate_section(packet)
            sections_content[section.section_id] = content
            
            # Record in review store
            self.review_store.add_section(
                section_id=section.section_id,
                section_name=section.name,
                content=content,
                auto_approve=self.auto_approve
            )

        # 5. Report Assembly (Markdown, HTML, DOCX)
        logger.info("STEP 5: Assembling final publication reports...")
        assembler = ReportAssembler(self.config, self.review_store)
        export_paths = assembler.export_all(output_dir=str(self.output_dir))
        for fmt, path in export_paths.items():
            logger.info(f" - Generated {fmt.upper()} report at: {path}")

        # 6. Automated Grounding Evaluation
        logger.info("STEP 6: Running automated numeric grounding evaluation...")
        evaluator = GroundingEvaluator()
        eval_results = evaluator.evaluate_report(sections_content, all_packets)
        eval_file = self.output_dir / "evaluation_report.json"
        with open(eval_file, "w", encoding="utf-8") as f:
            json.dump(eval_results, f, indent=2)

        ov = eval_results["overall_summary"]
        logger.info("=" * 60)
        logger.info("EVALUATION RESULTS SUMMARY:")
        logger.info(f" - Total Numbers / Statistics Extracted: {ov['total_numbers_in_report']}")
        logger.info(f" - Factual Grounded Matches: {ov['total_grounded']}")
        logger.info(f" - Ungrounded / Hallucinated Figures: {ov['total_ungrounded']}")
        logger.info(f" - Grounding Precision Score: {ov['overall_grounding_precision_pct']}%")
        logger.info(f" - Overall Status: {ov['overall_status']}")
        logger.info("=" * 60)

        return {
            "metadata": metadata,
            "export_paths": export_paths,
            "evaluation": eval_results,
            "review_status": self.review_store.get_review_status(),
        }


def main():
    parser = argparse.ArgumentParser(description="GenAR Pharmacovigilance Safety Reporting Pipeline")
    parser.add_argument("--input", "-i", default=r"C:\Users\ROHIT YADAV\Downloads\Bisoprolol_icsr_sample_1068rows.xlsx", help="Path to ICSR Excel or CSV dataset")
    parser.add_argument("--config", "-c", default="configs/pader_config.yaml", help="Path to report configuration YAML")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory for generated reports and artifacts")
    parser.add_argument("--provider", "-p", default="auto", help="LLM Provider (openai, gemini, anthropic, ollama, deterministic, auto)")
    parser.add_argument("--model", "-m", default=None, help="Specific LLM model identifier")
    parser.add_argument("--auto-approve", action="store_true", default=True, help="Auto-approve sections for automated build")
    
    args = parser.parse_args()
    pipeline = SafetyReportPipeline(
        input_data_path=args.input,
        config_path=args.config,
        output_dir=args.output_dir,
        provider=args.provider,
        model=args.model,
        auto_approve=args.auto_approve,
    )
    pipeline.run()


if __name__ == "__main__":
    main()
