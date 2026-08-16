"""
Human Review & Approval Layer
Manages section-level review states (pending_review, approved, flagged),
reviewer comments, and audit tracking before final report assembly.
"""

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SectionReviewState:
    section_id: str
    section_name: str
    status: str  # "pending_review", "approved", "flagged"
    content: str
    reviewer: Optional[str] = None
    review_comments: Optional[str] = None
    timestamp: Optional[str] = None


class ReviewStore:
    """
    Persists review state in JSON format and provides methods for reviewing and approving sections.
    """

    def __init__(self, store_path: str = "output/review_store.json"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.reviews: Dict[str, SectionReviewState] = {}
        self._load()

    def _load(self) -> None:
        if self.store_path.exists():
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for sec_id, item in data.items():
                    self.reviews[sec_id] = SectionReviewState(**item)
            except Exception as e:
                logger.warning(f"Could not load review store: {e}")

    def save(self) -> None:
        data = {k: asdict(v) for k, v in self.reviews.items()}
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_section(self, section_id: str, section_name: str, content: str, auto_approve: bool = False) -> None:
        status = "approved" if auto_approve else "pending_review"
        reviewer = "System Auto-Approver" if auto_approve else None
        now_str = datetime.now().isoformat()
        
        self.reviews[section_id] = SectionReviewState(
            section_id=section_id,
            section_name=section_name,
            status=status,
            content=content,
            reviewer=reviewer,
            review_comments="Auto-approved during automated pipeline run." if auto_approve else None,
            timestamp=now_str if auto_approve else None,
        )
        self.save()

    def approve_section(self, section_id: str, reviewer: str = "Medical Reviewer", comments: str = "Approved as presented.") -> None:
        if section_id in self.reviews:
            self.reviews[section_id].status = "approved"
            self.reviews[section_id].reviewer = reviewer
            self.reviews[section_id].review_comments = comments
            self.reviews[section_id].timestamp = datetime.now().isoformat()
            self.save()
            logger.info(f"Section '{section_id}' approved by {reviewer}.")
        else:
            raise KeyError(f"Section '{section_id}' not found in review store.")

    def flag_section(self, section_id: str, reviewer: str = "Medical Reviewer", comments: str = "Flagged for revision.") -> None:
        if section_id in self.reviews:
            self.reviews[section_id].status = "flagged"
            self.reviews[section_id].reviewer = reviewer
            self.reviews[section_id].review_comments = comments
            self.reviews[section_id].timestamp = datetime.now().isoformat()
            self.save()
            logger.info(f"Section '{section_id}' flagged by {reviewer}: {comments}")
        else:
            raise KeyError(f"Section '{section_id}' not found in review store.")

    def get_review_status(self) -> Dict[str, Any]:
        return {
            "total_sections": len(self.reviews),
            "approved": sum(1 for r in self.reviews.values() if r.status == "approved"),
            "pending": sum(1 for r in self.reviews.values() if r.status == "pending_review"),
            "flagged": sum(1 for r in self.reviews.values() if r.status == "flagged"),
        }

    def all_approved(self) -> bool:
        return all(r.status == "approved" for r in self.reviews.values())
