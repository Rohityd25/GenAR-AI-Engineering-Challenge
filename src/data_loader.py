"""
Data Ingestion and Validation Layer
Loads ICSR data (CSV or Excel), validates mandatory columns, handles case-level deduplication,
derives reporting period boundaries dynamically, and logs data health metrics.
"""

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class DatasetMetadata:
    total_rows: int
    unique_cases: int
    reporting_period_start: str
    reporting_period_end: str
    product_name: str
    missing_value_summary: Dict[str, int] = field(default_factory=dict)
    deduplication_notes: str = ""
    country_divergence_count: int = 0


class ICSRDataLoader:
    """
    Loads, cleans, validates, and prepares ICSR line listings.
    Follows PV standard of distinguishing case-level vs. reaction-level representations.
    """

    CRITICAL_COLUMNS = [
        "safetyreportid",
        "receivedate",
        "serious",
        "patient_reaction_reactionmeddrapt",
    ]

    def __init__(self, file_path: str, product_name: str = "Bisoprolol"):
        self.file_path = Path(file_path)
        self.product_name = product_name
        self.raw_df: Optional[pd.DataFrame] = None
        self.case_df: Optional[pd.DataFrame] = None
        self.metadata: Optional[DatasetMetadata] = None

    def load(self) -> Tuple[pd.DataFrame, pd.DataFrame, DatasetMetadata]:
        """
        Loads the dataset and returns (raw_df, case_df, metadata).
        - raw_df: 1 row per reaction entry (reaction-level granularity)
        - case_df: 1 row per unique safetyreportid (case-level granularity)
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.file_path}")

        logger.info(f"Loading ICSR data from {self.file_path}...")
        if self.file_path.suffix.lower() in [".xlsx", ".xls"]:
            self.raw_df = pd.read_excel(self.file_path)
        elif self.file_path.suffix.lower() in [".csv", ".tsv"]:
            sep = "\t" if self.file_path.suffix.lower() == ".tsv" else ","
            self.raw_df = pd.read_csv(self.file_path, sep=sep, low_memory=False)
        else:
            raise ValueError(f"Unsupported file format: {self.file_path.suffix}")

        self._validate_columns()
        self._clean_dates()
        self._deduplicate_cases()
        self._calculate_metadata()

        return self.raw_df, self.case_df, self.metadata

    def _validate_columns(self) -> None:
        """Ensures all expected core columns are present."""
        missing = [col for col in self.CRITICAL_COLUMNS if col not in self.raw_df.columns]
        if missing:
            raise ValueError(f"Dataset is missing critical pharmacovigilance columns: {missing}")

    def _clean_dates(self) -> None:
        """Parses receivedate into ISO date strings."""
        if "receivedate" in self.raw_df.columns:
            # Handle YYYYMMDD integers/strings or ISO strings
            self.raw_df["receivedate_str"] = self.raw_df["receivedate"].astype(str).str.split(".").str[0]
            self.raw_df["receivedate_clean"] = pd.to_datetime(
                self.raw_df["receivedate_str"], format="%Y%m%d", errors="coerce"
            )
            # Fallback for standard date parsing if any NaT
            mask_nat = self.raw_df["receivedate_clean"].isna()
            if mask_nat.any():
                self.raw_df.loc[mask_nat, "receivedate_clean"] = pd.to_datetime(
                    self.raw_df.loc[mask_nat, "receivedate_str"], errors="coerce"
                )

    def _deduplicate_cases(self) -> None:
        """
        Creates deduplicated case-level dataframe preserving the most conservative/highest severity record.
        """
        total_rows = len(self.raw_df)
        unique_ids = self.raw_df["safetyreportid"].nunique()

        # Sort so serious cases / earliest dates are prioritized before dropping duplicates
        sorted_df = self.raw_df.copy()
        if "serious" in sorted_df.columns:
            # Sort serious before not serious
            sorted_df["_is_serious"] = sorted_df["serious"].astype(str).str.lower().isin(["serious", "1", "yes", "true"])
            sorted_df = sorted_df.sort_values(by=["_is_serious", "receivedate_clean"], ascending=[False, True])
        
        self.case_df = sorted_df.drop_duplicates(subset=["safetyreportid"]).copy()
        if "_is_serious" in self.case_df.columns:
            self.case_df = self.case_df.drop(columns=["_is_serious"])

        logger.info(
            f"Deduplication complete: {total_rows} reaction rows -> {unique_ids} unique safety cases."
        )

    def _calculate_metadata(self) -> None:
        """Extracts dataset metadata and data health audit metrics."""
        total_rows = len(self.raw_df)
        unique_cases = len(self.case_df)

        valid_dates = self.case_df["receivedate_clean"].dropna()
        if not valid_dates.empty:
            start_date = valid_dates.min().strftime("%Y-%m-%d")
            end_date = valid_dates.max().strftime("%Y-%m-%d")
        else:
            start_date = "Unknown"
            end_date = "Unknown"

        # Missing value audit on columns used in analyses
        monitored_cols = [
            "safetyreportid", "receivedate", "serious", "patient_reaction_reactionmeddrapt",
            "patient_patientonsetage", "patient_patientonsetageunit", "patient_patientsex",
            "occurcountry", "primarysource_reportercountry", "fulfillexpeditecriteria",
            "patient_reaction_reactionoutcome"
        ]
        missing_summary = {
            col: int(self.raw_df[col].isna().sum())
            for col in monitored_cols
            if col in self.raw_df.columns
        }

        # Country divergence audit
        divergence = 0
        if "occurcountry" in self.case_df.columns and "primarysource_reportercountry" in self.case_df.columns:
            divergence = int(
                (self.case_df["occurcountry"].fillna("").str.lower() !=
                 self.case_df["primarysource_reportercountry"].fillna("").str.lower()).sum()
            )

        dedup_notes = (
            f"Total raw rows: {total_rows}. Unique cases: {unique_cases}. "
            f"Row-to-case ratio: {total_rows / unique_cases:.2f}. "
            f"Case-level tables use 1 record per unique safetyreportid ({unique_cases}); "
            f"Reaction-level tables analyze all unnested MedDRA PT reactions."
        )

        self.metadata = DatasetMetadata(
            total_rows=total_rows,
            unique_cases=unique_cases,
            reporting_period_start=start_date,
            reporting_period_end=end_date,
            product_name=self.product_name,
            missing_value_summary=missing_summary,
            deduplication_notes=dedup_notes,
            country_divergence_count=divergence,
        )
