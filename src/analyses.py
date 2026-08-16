"""
Deterministic Analysis Layer
Pure Python analysis functions producing structured, auditable JSON outputs.
Zero LLM involvement, exact arithmetic, and transparent aggregation logic.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


class AnalysisRegistry:
    """Registry pattern allowing dynamic lookup and execution of analysis functions."""

    _registry: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(func: Callable):
            cls._registry[name] = func
            return func
        return decorator

    @classmethod
    def get(cls, name: str) -> Callable:
        if name not in cls._registry:
            raise KeyError(f"Analysis function '{name}' is not registered.")
        return cls._registry[name]

    @classmethod
    def list_analyses(cls) -> List[str]:
        return list(cls._registry.keys())

    @classmethod
    def execute_all(cls, case_df: pd.DataFrame, raw_df: pd.DataFrame) -> Dict[str, Any]:
        results = {}
        for name, func in cls._registry.items():
            results[name] = func(case_df, raw_df)
        return results


def normalize_age_to_years(row: pd.Series) -> Optional[float]:
    """Normalizes patient onset age to years based on the unit field."""
    age = row.get("patient_patientonsetage")
    unit = str(row.get("patient_patientonsetageunit", "year")).lower() if pd.notna(row.get("patient_patientonsetageunit")) else "year"
    
    if pd.isna(age) or age is None or age == "":
        return None
    try:
        age_val = float(age)
    except (ValueError, TypeError):
        return None

    if "month" in unit:
        return age_val / 12.0
    elif "day" in unit:
        return age_val / 365.25
    elif "week" in unit:
        return age_val / 52.14
    elif "decade" in unit:
        return age_val * 10.0
    elif "hour" in unit:
        return age_val / (365.25 * 24.0)
    return age_val


def unnest_reactions(series: pd.Series) -> List[str]:
    """Splits comma-separated MedDRA PT reaction strings into individual terms."""
    terms = []
    for item in series.dropna():
        for sub in str(item).split(","):
            cleaned = sub.strip()
            if cleaned:
                terms.append(cleaned)
    return terms


@AnalysisRegistry.register("total_cases")
def total_cases(case_df: pd.DataFrame, raw_df: pd.DataFrame) -> Dict[str, Any]:
    """Calculates unique case count and total reaction record count."""
    unique_cases = int(case_df["safetyreportid"].nunique()) if "safetyreportid" in case_df.columns else len(case_df)
    total_raw_rows = len(raw_df)
    
    # Calculate unnested PT mentions
    all_reactions = unnest_reactions(raw_df.get("patient_reaction_reactionmeddrapt", pd.Series()))
    
    return {
        "unique_cases": unique_cases,
        "total_reaction_rows": total_raw_rows,
        "total_pt_mentions": len(all_reactions),
        "distinct_pt_count": len(set(all_reactions)),
        "aggregation_level": "Case-level count based on unique safetyreportid; reaction count based on raw line listings.",
    }


@AnalysisRegistry.register("serious_vs_nonserious")
def serious_vs_nonserious(case_df: pd.DataFrame, raw_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes serious vs. non-serious case counts and breakdowns of independent seriousness criteria.
    Note: Seriousness sub-criteria are independent flags and do not sum to total serious cases.
    """
    total = len(case_df)
    is_serious = case_df["serious"].astype(str).str.lower().isin(["serious", "1", "yes", "true"])
    serious_count = int(is_serious.sum())
    nonserious_count = total - serious_count

    # Seriousness criteria flags (independent yes/no)
    criteria_fields = [
        ("seriousnessdeath", "Death"),
        ("seriousnesslifethreatening", "Life-Threatening"),
        ("seriousnesshospitalization", "Hospitalization / Prolongation"),
        ("seriousnessdisabling", "Disability / Incapacity"),
        ("seriousnesscongenitalanomali", "Congenital Anomaly"),
        ("seriousnessother", "Other Medically Important Condition"),
    ]

    criteria_breakdown = {}
    for col, label in criteria_fields:
        if col in case_df.columns:
            count = int(case_df[col].astype(str).str.lower().isin(["yes", "1", "true"]).sum())
            pct = round((count / total) * 100.0, 2) if total > 0 else 0.0
            criteria_breakdown[label] = {"count": count, "percentage": pct}
        else:
            criteria_breakdown[label] = {"count": 0, "percentage": 0.0}

    return {
        "total_cases": total,
        "serious_cases": serious_count,
        "serious_percentage": round((serious_count / total) * 100.0, 2) if total > 0 else 0.0,
        "nonserious_cases": nonserious_count,
        "nonserious_percentage": round((nonserious_count / total) * 100.0, 2) if total > 0 else 0.0,
        "seriousness_criteria": criteria_breakdown,
        "methodological_note": "Seriousness criteria flags are non-mutually exclusive; a single case may meet multiple criteria.",
    }


@AnalysisRegistry.register("breakdown_by_age")
def breakdown_by_age(case_df: pd.DataFrame, raw_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes age distribution normalized to years and binned into standardized pharmacovigilance brackets:
    <18 (Pediatric), 18-64 (Adult), 65-74 (Elderly), 75+ (Elderly >=75), and Unknown.
    """
    total = len(case_df)
    normalized_ages = case_df.apply(normalize_age_to_years, axis=1)

    bins = {
        "Pediatric (<18 years)": 0,
        "Adult (18-64 years)": 0,
        "Elderly (65-74 years)": 0,
        "Elderly (75+ years)": 0,
        "Unknown / Not Reported": 0,
    }

    numeric_ages = []
    for age in normalized_ages:
        if age is None or pd.isna(age):
            bins["Unknown / Not Reported"] += 1
        elif age < 18:
            bins["Pediatric (<18 years)"] += 1
            numeric_ages.append(age)
        elif age < 65:
            bins["Adult (18-64 years)"] += 1
            numeric_ages.append(age)
        elif age < 75:
            bins["Elderly (65-74 years)"] += 1
            numeric_ages.append(age)
        else:
            bins["Elderly (75+ years)"] += 1
            numeric_ages.append(age)

    summary_table = []
    for bracket, count in bins.items():
        summary_table.append({
            "age_group": bracket,
            "count": count,
            "percentage": round((count / total) * 100.0, 2) if total > 0 else 0.0,
        })

    age_stats = {}
    if numeric_ages:
        age_stats = {
            "mean_age": round(float(np.mean(numeric_ages)), 1),
            "median_age": round(float(np.median(numeric_ages)), 1),
            "min_age": round(float(np.min(numeric_ages)), 1),
            "max_age": round(float(np.max(numeric_ages)), 1),
            "total_with_numeric_age": len(numeric_ages),
        }

    return {
        "total_cases": total,
        "age_distribution": summary_table,
        "statistics": age_stats,
        "bucketing_rules": "Ages normalized from patient_patientonsetageunit (days/months/years) to years. Bins: <18, 18-64, 65-74, 75+, Unknown.",
    }


@AnalysisRegistry.register("breakdown_by_sex")
def breakdown_by_sex(case_df: pd.DataFrame, raw_df: pd.DataFrame) -> Dict[str, Any]:
    """Computes case-level patient sex breakdown."""
    total = len(case_df)
    sex_col = case_df["patient_patientsex"].astype(str).str.lower().str.strip()
    
    female_count = int(sex_col.isin(["female", "f", "2"]).sum())
    male_count = int(sex_col.isin(["male", "m", "1"]).sum())
    unknown_count = total - (female_count + male_count)

    return {
        "total_cases": total,
        "sex_distribution": [
            {"sex": "Female", "count": female_count, "percentage": round((female_count / total) * 100.0, 2) if total > 0 else 0.0},
            {"sex": "Male", "count": male_count, "percentage": round((male_count / total) * 100.0, 2) if total > 0 else 0.0},
            {"sex": "Unknown / Not Reported", "count": unknown_count, "percentage": round((unknown_count / total) * 100.0, 2) if total > 0 else 0.0},
        ],
    }


@AnalysisRegistry.register("breakdown_by_country")
def breakdown_by_country(case_df: pd.DataFrame, raw_df: pd.DataFrame, top_n: int = 10) -> Dict[str, Any]:
    """
    Computes geographic distribution based on occurcountry, documenting any divergence
    against primarysource_reportercountry.
    """
    total = len(case_df)
    country_series = case_df["occurcountry"].fillna("Unknown / Not Reported").astype(str).str.strip().str.title()
    counts = country_series.value_counts()

    top_countries = []
    for country, count in counts.head(top_n).items():
        top_countries.append({
            "country": str(country),
            "count": int(count),
            "percentage": round((count / total) * 100.0, 2) if total > 0 else 0.0,
        })

    other_count = int(counts.iloc[top_n:].sum()) if len(counts) > top_n else 0
    if other_count > 0:
        top_countries.append({
            "country": "Other Countries",
            "count": other_count,
            "percentage": round((other_count / total) * 100.0, 2) if total > 0 else 0.0,
        })

    divergence_count = 0
    if "occurcountry" in case_df.columns and "primarysource_reportercountry" in case_df.columns:
        divergence_count = int(
            (case_df["occurcountry"].fillna("").str.lower() !=
             case_df["primarysource_reportercountry"].fillna("").str.lower()).sum()
        )

    return {
        "total_cases": total,
        "country_distribution": top_countries,
        "unique_countries_count": len(counts),
        "primary_field": "occurcountry",
        "reportercountry_divergence_cases": divergence_count,
        "note": f"occurcountry was chosen as primary geographic indicator. Divergence with primarysource_reportercountry was observed in {divergence_count} cases.",
    }


@AnalysisRegistry.register("top_reactions")
def top_reactions(case_df: pd.DataFrame, raw_df: pd.DataFrame, top_n: int = 15) -> Dict[str, Any]:
    """Computes most frequently reported MedDRA Preferred Terms across all reaction listings."""
    reactions = unnest_reactions(raw_df.get("patient_reaction_reactionmeddrapt", pd.Series()))
    total_pt_mentions = len(reactions)
    counts = pd.Series(reactions).value_counts()

    results = []
    for pt, count in counts.head(top_n).items():
        results.append({
            "preferred_term": str(pt),
            "count": int(count),
            "percentage_of_pt_mentions": round((count / total_pt_mentions) * 100.0, 2) if total_pt_mentions > 0 else 0.0,
        })

    return {
        "total_pt_mentions": total_pt_mentions,
        "unique_pt_count": len(counts),
        "top_reactions": results,
        "granularity": "MedDRA Preferred Term (PT) level. (System Organ Class grouping unavailable in raw dataset).",
    }


@AnalysisRegistry.register("top_serious_reactions")
def top_serious_reactions(case_df: pd.DataFrame, raw_df: pd.DataFrame, top_n: int = 15) -> Dict[str, Any]:
    """Computes most frequently reported MedDRA Preferred Terms restricted to serious reports."""
    serious_raw = raw_df[raw_df["serious"].astype(str).str.lower().isin(["serious", "1", "yes", "true"])]
    reactions = unnest_reactions(serious_raw.get("patient_reaction_reactionmeddrapt", pd.Series()))
    total_serious_pt = len(reactions)
    counts = pd.Series(reactions).value_counts()

    results = []
    for pt, count in counts.head(top_n).items():
        results.append({
            "preferred_term": str(pt),
            "count": int(count),
            "percentage_of_serious_pt_mentions": round((count / total_serious_pt) * 100.0, 2) if total_serious_pt > 0 else 0.0,
        })

    return {
        "total_serious_pt_mentions": total_serious_pt,
        "unique_serious_pt_count": len(counts),
        "top_serious_reactions": results,
    }


@AnalysisRegistry.register("outcomes_summary")
def outcomes_summary(case_df: pd.DataFrame, raw_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Summarizes reaction-level outcomes from patient_reaction_reactionoutcome.
    Handles unnesting of comma-delimited outcome values.
    """
    outcomes = []
    for item in raw_df.get("patient_reaction_reactionoutcome", pd.Series()).dropna():
        for sub in str(item).split(","):
            cleaned = sub.strip().lower()
            if cleaned:
                outcomes.append(cleaned)

    total_outcomes = len(outcomes)
    counts = pd.Series(outcomes).value_counts()

    outcome_labels = {
        "recovered/resolved": "Recovered / Resolved",
        "unknown": "Unknown / Not Reported",
        "not recovered/not resolved/ongoing": "Not Recovered / Not Resolved / Ongoing",
        "recovering/resolving": "Recovering / Resolving",
        "fatal": "Fatal",
        "recovered/resolved with sequelae": "Recovered / Resolved with Sequelae",
    }

    summary = []
    for raw_key, count in counts.items():
        label = outcome_labels.get(raw_key, raw_key.title())
        summary.append({
            "outcome": label,
            "raw_value": str(raw_key),
            "count": int(count),
            "percentage": round((count / total_outcomes) * 100.0, 2) if total_outcomes > 0 else 0.0,
        })

    return {
        "total_outcome_records": total_outcomes,
        "outcomes_distribution": summary,
        "methodological_note": "Outcomes are recorded at the reaction level; individual patients may have multiple reactions with differing outcomes.",
    }


@AnalysisRegistry.register("trend_over_time")
def trend_over_time(case_df: pd.DataFrame, raw_df: pd.DataFrame, freq: str = "M") -> Dict[str, Any]:
    """
    Calculates monthly case intake volume based on receivedate.
    """
    valid_dates_case = case_df["receivedate_clean"].dropna()
    total_cases = len(valid_dates_case)
    
    monthly_counts = valid_dates_case.dt.to_period("M").value_counts().sort_index()

    trend = []
    for period, count in monthly_counts.items():
        trend.append({
            "period": str(period),
            "count": int(count),
            "percentage": round((count / total_cases) * 100.0, 2) if total_cases > 0 else 0.0,
        })

    counts_arr = list(monthly_counts.values)
    monthly_stats = {
        "monthly_mean": round(float(np.mean(counts_arr)), 1) if counts_arr else 0.0,
        "monthly_min": int(np.min(counts_arr)) if counts_arr else 0,
        "monthly_max": int(np.max(counts_arr)) if counts_arr else 0,
        "peak_month": str(monthly_counts.idxmax()) if not monthly_counts.empty else "N/A",
    }

    return {
        "total_cases_analyzed": total_cases,
        "monthly_trend": trend,
        "summary_statistics": monthly_stats,
        "interpretive_caution": "Numeric trends reflect spontaneous reporting intake over time and do not represent incidence rates or confirmed safety signals.",
    }


@AnalysisRegistry.register("alert_cases_summary")
def alert_cases_summary(case_df: pd.DataFrame, raw_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyzes 15-day expedited alert status based on fulfillexpeditecriteria.
    Distinguishes expedited serious reports from non-expedited reports.
    """
    total = len(case_df)
    expedite_col = case_df["fulfillexpeditecriteria"].astype(str).str.lower().str.strip()
    
    expedited_count = int(expedite_col.isin(["yes", "1", "true"]).sum())
    non_expedited_count = total - expedited_count

    # Serious & Expedited intersection
    is_serious = case_df["serious"].astype(str).str.lower().isin(["serious", "1", "yes", "true"])
    is_expedite = expedite_col.isin(["yes", "1", "true"])
    serious_expedited = int((is_serious & is_expedite).sum())

    # Death cases
    death_count = int(case_df["seriousnessdeath"].astype(str).str.lower().isin(["yes", "1", "true"]).sum()) if "seriousnessdeath" in case_df.columns else 0

    return {
        "total_cases": total,
        "expedited_15_day_alert_cases": expedited_count,
        "expedited_percentage": round((expedited_count / total) * 100.0, 2) if total > 0 else 0.0,
        "non_expedited_cases": non_expedited_count,
        "non_expedited_percentage": round((non_expedited_count / total) * 100.0, 2) if total > 0 else 0.0,
        "serious_expedited_cases": serious_expedited,
        "fatal_cases": death_count,
        "regulatory_context": "Cases fulfilling expedite criteria require 15-day alert submission to regulatory authorities.",
    }


@AnalysisRegistry.register("case_listing")
def case_listing(case_df: pd.DataFrame, raw_df: pd.DataFrame, limit: int = 50) -> Dict[str, Any]:
    """
    Generates a structured sample case listing table for reference indexing.
    """
    selected_cases = case_df.head(limit)
    rows = []
    
    for _, row in selected_cases.iterrows():
        case_id = str(row.get("safetyreportid", "UNK"))
        recv_date = str(row.get("receivedate_str", row.get("receivedate", "UNK")))
        country = str(row.get("occurcountry", "UNK")).title()
        sex = str(row.get("patient_patientsex", "UNK")).title()
        age = str(int(row.get("patient_patientonsetage"))) if pd.notna(row.get("patient_patientonsetage")) else "UNK"
        serious = "Yes" if str(row.get("serious", "")).lower() in ["serious", "yes", "1"] else "No"
        reactions = str(row.get("patient_reaction_reactionmeddrapt", "UNK"))
        outcome = str(row.get("patient_reaction_reactionoutcome", "UNK"))
        expedite = "Yes" if str(row.get("fulfillexpeditecriteria", "")).lower() in ["yes", "1"] else "No"

        rows.append({
            "safetyreportid": case_id,
            "receivedate": recv_date,
            "country": country,
            "age": age,
            "sex": sex,
            "serious": serious,
            "expedited": expedite,
            "reactions": reactions,
            "outcome": outcome,
        })

    return {
        "sample_size": len(rows),
        "total_cases": len(case_df),
        "listings": rows,
    }
