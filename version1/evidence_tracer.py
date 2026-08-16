"""
Version 1 Feature: Sentence-Level Evidence Tracer
Annotates generated regulatory sentences with explicit pointers back to
the exact deterministic JSON metrics in the evidence packet that substantiate each claim.
"""

import json
import re
from typing import Any, Dict, List, Tuple


class EvidenceTracer:
    """
    Tags sentences with substantiating evidence keys from the pre-computed packet.
    """

    def __init__(self, context_packet: Dict[str, Any]):
        self.packet = context_packet
        self.evidence = context_packet.get("evidence_packet", {})
        self.meta = context_packet.get("report_metadata", {})
        self._index_evidence()

    def _index_evidence(self) -> None:
        """Flattens evidence packet into searchable (path, value_str) index."""
        self.index: List[Tuple[str, str]] = []

        def recurse(path: str, obj: Any):
            if isinstance(obj, (int, float, str)):
                val_str = str(obj).strip()
                if val_str:
                    self.index.append((path, val_str))
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    recurse(f"{path}.{k}" if path else k, v)
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    recurse(f"{path}[{idx}]", item)

        recurse("evidence", self.evidence)
        recurse("metadata", self.meta)

    def trace_sentence(self, sentence: str) -> Dict[str, Any]:
        """Identifies which evidence keys support the given sentence."""
        matched_keys = []
        # Find numeric tokens or exact terms in sentence
        tokens = re.findall(r"\b\d+(?:,\d+)*(?:\.\d+)?\b", sentence)
        for t in tokens:
            t_clean = t.replace(",", "")
            for path, val_str in self.index:
                if val_str == t_clean:
                    matched_keys.append({"path": path, "matched_value": val_str})

        return {
            "sentence": sentence.strip(),
            "has_numeric_claim": len(tokens) > 0,
            "supporting_evidence": matched_keys,
            "grounded": len(tokens) == 0 or len(matched_keys) > 0,
        }

    def trace_text(self, text: str) -> List[Dict[str, Any]]:
        """Splits markdown text into sentences and traces evidence for each."""
        # Simple sentence splitter
        raw_sentences = re.split(r"(?<=[.!?])\s+", text)
        results = []
        for s in raw_sentences:
            s_clean = s.strip()
            if s_clean and not s_clean.startswith("#") and not s_clean.startswith("|"):
                results.append(self.trace_sentence(s_clean))
        return results
