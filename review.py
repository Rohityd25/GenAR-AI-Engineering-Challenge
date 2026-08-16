"""
Human Review & Audit CLI
Allows medical reviewers to inspect, approve, or flag generated report sections
prior to final publication assembly.
"""

import argparse
import sys
from src.reviewer import ReviewStore
from src.config import ReportConfig
from src.report_assembler import ReportAssembler


def interactive_review(store_path: str = "output/review_store.json", config_path: str = "configs/pader_config.yaml"):
    store = ReviewStore(store_path)
    config = ReportConfig.from_yaml(config_path)

    print("=" * 60)
    print("PHARMACOVIGILANCE HUMAN REVIEW & APPROVAL CONSOLE")
    print("=" * 60)

    status = store.get_review_status()
    print(f"Total Sections: {status['total_sections']} | Approved: {status['approved']} | Pending: {status['pending']} | Flagged: {status['flagged']}")
    print("-" * 60)

    for sec in sorted(config.sections, key=lambda s: s.display_order):
        rev = store.reviews.get(sec.section_id)
        if not rev:
            print(f"[{sec.section_id}] {sec.name}: NO CONTENT GENERATED")
            continue

        print(f"\nSection: {sec.name} ({sec.section_id})")
        print(f"Current Status: [{rev.status.upper()}] (Reviewer: {rev.reviewer or 'None'})")
        print("Preview:")
        preview_lines = rev.content.split("\n")[:8]
        for l in preview_lines:
            print(f"  {l}")
        if len(rev.content.split("\n")) > 8:
            print("  [... content truncated for preview ...]")

        choice = input("\nAction ([A]pprove / [F]lag / [S]kip / [Q]uit): ").strip().lower()
        if choice == "a":
            comments = input("Approval comment (optional): ").strip() or "Approved by medical reviewer."
            store.approve_section(sec.section_id, reviewer="Medical Reviewer", comments=comments)
        elif choice == "f":
            comments = input("Flag reason / revision notes: ").strip() or "Requires further data verification."
            store.flag_section(sec.section_id, reviewer="Medical Reviewer", comments=comments)
        elif choice == "q":
            break

    print("\nReview session updated.")
    print("Re-assembling reports with updated review statuses...")
    assembler = ReportAssembler(config, store)
    paths = assembler.export_all("output")
    print(f"Updated reports assembled at: {paths['markdown']}")


def main():
    parser = argparse.ArgumentParser(description="Human Review Console for Safety Reports")
    parser.add_argument("--store", default="output/review_store.json", help="Path to review store JSON")
    parser.add_argument("--config", default="configs/pader_config.yaml", help="Path to report configuration YAML")
    parser.add_argument("--approve-all", action="store_true", help="Batch approve all pending sections")
    parser.add_argument("--reviewer", default="Medical Reviewer", help="Reviewer name for audit log")
    args = parser.parse_args()

    store = ReviewStore(args.store)
    if args.approve_all:
        for sec_id in store.reviews:
            store.approve_section(sec_id, reviewer=args.reviewer, comments="Batch approved via CLI.")
        config = ReportConfig.from_yaml(args.config)
        assembler = ReportAssembler(config, store)
        assembler.export_all("output")
        print("All sections approved and report re-assembled.")
    else:
        interactive_review(args.store, args.config)


if __name__ == "__main__":
    main()
