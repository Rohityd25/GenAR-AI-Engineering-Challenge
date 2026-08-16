"""
Report Configuration Layer
Defines Pydantic schemas for declarative report definitions and loads YAML/JSON configs.
Enables generalization to PADER, PSUR, PBRER, DSUR, and CSR without code changes.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


class SectionConfig(BaseModel):
    name: str
    section_id: str
    analyses: List[str] = Field(default_factory=list)
    instructions: str = ""
    required_in_final: bool = True
    display_order: int = 0
    format_type: str = "prose_and_tables"  # prose_and_tables, tabular_only, metadata_only


class ReportConfig(BaseModel):
    report_type: str
    title: str
    product_name: str
    regulatory_framework: str = "US FDA 21 CFR 314.80 / ICH E2C"
    version: str = "1.0"
    sections: List[SectionConfig] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str) -> "ReportConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
