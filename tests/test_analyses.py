"""
Unit tests for deterministic analysis layer and data loader.
Tests exact mathematical properties against hand-calculated synthetic fixtures and real dataset.
"""

import pandas as pd
import pytest
from src.analyses import (
    AnalysisRegistry,
    normalize_age_to_years,
    unnest_reactions,
    total_cases,
    serious_vs_nonserious,
    breakdown_by_age,
    breakdown_by_sex,
    breakdown_by_country,
    top_reactions,
    top_serious_reactions,
    outcomes_summary,
    trend_over_time,
    alert_cases_summary,
)


@pytest.fixture
def synthetic_data():
    """
    Creates a 10-row synthetic fixture representing 8 unique cases with known answers.
    """
    raw_data = [
        # Case 1: 2 reaction rows, age 70 years, female, serious death, IT, expedite yes
        {"safetyreportid": 1001, "receivedate": "20250110", "serious": "serious", "seriousnessdeath": "yes",
         "seriousnesslifethreatening": "no", "seriousnesshospitalization": "yes", "seriousnessdisabling": "no",
         "seriousnesscongenitalanomali": "no", "seriousnessother": "no", "patient_patientonsetage": 70,
         "patient_patientonsetageunit": "year", "patient_patientsex": "female", "occurcountry": "italy",
         "primarysource_reportercountry": "italy", "fulfillexpeditecriteria": "yes",
         "patient_reaction_reactionmeddrapt": "Bradycardia,Dyspnoea", "patient_reaction_reactionoutcome": "fatal,fatal"},
        {"safetyreportid": 1001, "receivedate": "20250110", "serious": "serious", "seriousnessdeath": "yes",
         "seriousnesslifethreatening": "no", "seriousnesshospitalization": "yes", "seriousnessdisabling": "no",
         "seriousnesscongenitalanomali": "no", "seriousnessother": "no", "patient_patientonsetage": 70,
         "patient_patientonsetageunit": "year", "patient_patientsex": "female", "occurcountry": "italy",
         "primarysource_reportercountry": "italy", "fulfillexpeditecriteria": "yes",
         "patient_reaction_reactionmeddrapt": "Hypotension", "patient_reaction_reactionoutcome": "fatal"},
        
        # Case 2: 1 reaction row, age 80 years, male, serious hospital, FR, expedite yes
        {"safetyreportid": 1002, "receivedate": "20250215", "serious": "serious", "seriousnessdeath": "no",
         "seriousnesslifethreatening": "no", "seriousnesshospitalization": "yes", "seriousnessdisabling": "no",
         "seriousnesscongenitalanomali": "no", "seriousnessother": "yes", "patient_patientonsetage": 80,
         "patient_patientonsetageunit": "year", "patient_patientsex": "male", "occurcountry": "france",
         "primarysource_reportercountry": "france", "fulfillexpeditecriteria": "yes",
         "patient_reaction_reactionmeddrapt": "Acute kidney injury", "patient_reaction_reactionoutcome": "recovering/resolving"},

        # Case 3: 1 reaction row, age 24 months (=2 years), male, serious life-threatening, UK, expedite yes
        {"safetyreportid": 1003, "receivedate": "20250320", "serious": "serious", "seriousnessdeath": "no",
         "seriousnesslifethreatening": "yes", "seriousnesshospitalization": "no", "seriousnessdisabling": "no",
         "seriousnesscongenitalanomali": "no", "seriousnessother": "no", "patient_patientonsetage": 24,
         "patient_patientonsetageunit": "month", "patient_patientsex": "male", "occurcountry": "united kingdom",
         "primarysource_reportercountry": "united kingdom", "fulfillexpeditecriteria": "yes",
         "patient_reaction_reactionmeddrapt": "Bradycardia", "patient_reaction_reactionoutcome": "recovered/resolved"},

        # Case 4: 1 reaction row, age 45 years, female, not serious, CA, expedite no
        {"safetyreportid": 1004, "receivedate": "20250410", "serious": "not serious", "seriousnessdeath": "no",
         "seriousnesslifethreatening": "no", "seriousnesshospitalization": "no", "seriousnessdisabling": "no",
         "seriousnesscongenitalanomali": "no", "seriousnessother": "no", "patient_patientonsetage": 45,
         "patient_patientonsetageunit": "year", "patient_patientsex": "female", "occurcountry": "canada",
         "primarysource_reportercountry": "canada", "fulfillexpeditecriteria": "no",
         "patient_reaction_reactionmeddrapt": "Dizziness", "patient_reaction_reactionoutcome": "recovered/resolved"},

        # Case 5: 1 reaction row, age unknown, unknown sex, serious other, DE, expedite yes
        {"safetyreportid": 1005, "receivedate": "20250505", "serious": "serious", "seriousnessdeath": "no",
         "seriousnesslifethreatening": "no", "seriousnesshospitalization": "no", "seriousnessdisabling": "no",
         "seriousnesscongenitalanomali": "no", "seriousnessother": "yes", "patient_patientonsetage": None,
         "patient_patientonsetageunit": None, "patient_patientsex": "unknown", "occurcountry": "germany",
         "primarysource_reportercountry": "germany", "fulfillexpeditecriteria": "yes",
         "patient_reaction_reactionmeddrapt": "Fatigue", "patient_reaction_reactionoutcome": "unknown"},

        # Case 6: 2 reaction rows, age 68 years, male, serious disabling, ES, reporter FR (divergent), expedite yes
        {"safetyreportid": 1006, "receivedate": "20250612", "serious": "serious", "seriousnessdeath": "no",
         "seriousnesslifethreatening": "no", "seriousnesshospitalization": "no", "seriousnessdisabling": "yes",
         "seriousnesscongenitalanomali": "no", "seriousnessother": "no", "patient_patientonsetage": 68,
         "patient_patientonsetageunit": "year", "patient_patientsex": "male", "occurcountry": "spain",
         "primarysource_reportercountry": "france", "fulfillexpeditecriteria": "yes",
         "patient_reaction_reactionmeddrapt": "Dyspnoea", "patient_reaction_reactionoutcome": "not recovered/not resolved/ongoing"},
        {"safetyreportid": 1006, "receivedate": "20250612", "serious": "serious", "seriousnessdeath": "no",
         "seriousnesslifethreatening": "no", "seriousnesshospitalization": "no", "seriousnessdisabling": "yes",
         "seriousnesscongenitalanomali": "no", "seriousnessother": "no", "patient_patientonsetage": 68,
         "patient_patientonsetageunit": "year", "patient_patientsex": "male", "occurcountry": "spain",
         "primarysource_reportercountry": "france", "fulfillexpeditecriteria": "yes",
         "patient_reaction_reactionmeddrapt": "Hypotension", "patient_reaction_reactionoutcome": "not recovered/not resolved/ongoing"},

        # Case 7: 1 reaction row, age 30 years, female, serious congenital anomaly, IT, expedite yes
        {"safetyreportid": 1007, "receivedate": "20250725", "serious": "serious", "seriousnessdeath": "no",
         "seriousnesslifethreatening": "no", "seriousnesshospitalization": "no", "seriousnessdisabling": "no",
         "seriousnesscongenitalanomali": "yes", "seriousnessother": "no", "patient_patientonsetage": 30,
         "patient_patientonsetageunit": "year", "patient_patientsex": "female", "occurcountry": "italy",
         "primarysource_reportercountry": "italy", "fulfillexpeditecriteria": "yes",
         "patient_reaction_reactionmeddrapt": "Congenital heart disease", "patient_reaction_reactionoutcome": "unknown"},

        # Case 8: 1 reaction row, age 76 years, female, serious hospitalization, UK, expedite yes
        {"safetyreportid": 1008, "receivedate": "20250818", "serious": "serious", "seriousnessdeath": "no",
         "seriousnesslifethreatening": "no", "seriousnesshospitalization": "yes", "seriousnessdisabling": "no",
         "seriousnesscongenitalanomali": "no", "seriousnessother": "no", "patient_patientonsetage": 76,
         "patient_patientonsetageunit": "year", "patient_patientsex": "female", "occurcountry": "united kingdom",
         "primarysource_reportercountry": "united kingdom", "fulfillexpeditecriteria": "yes",
         "patient_reaction_reactionmeddrapt": "Bradycardia", "patient_reaction_reactionoutcome": "recovered/resolved"},
    ]

    raw_df = pd.DataFrame(raw_data)
    raw_df["receivedate_clean"] = pd.to_datetime(raw_df["receivedate"], format="%Y%m%d")
    case_df = raw_df.drop_duplicates(subset=["safetyreportid"]).copy()
    return case_df, raw_df


def test_total_cases_synthetic(synthetic_data):
    case_df, raw_df = synthetic_data
    res = total_cases(case_df, raw_df)
    assert res["unique_cases"] == 8
    assert res["total_reaction_rows"] == 10
    assert res["total_pt_mentions"] == 11  # (2 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1 + 1)


def test_serious_vs_nonserious_synthetic(synthetic_data):
    case_df, raw_df = synthetic_data
    res = serious_vs_nonserious(case_df, raw_df)
    assert res["total_cases"] == 8
    assert res["serious_cases"] == 7
    assert res["nonserious_cases"] == 1
    assert res["serious_percentage"] == 87.5
    assert res["nonserious_percentage"] == 12.5
    
    # Check criteria flags
    crit = res["seriousness_criteria"]
    assert crit["Death"]["count"] == 1
    assert crit["Life-Threatening"]["count"] == 1
    assert crit["Hospitalization / Prolongation"]["count"] == 3  # Case 1001, 1002, 1008
    assert crit["Disability / Incapacity"]["count"] == 1  # Case 1006
    assert crit["Congenital Anomaly"]["count"] == 1  # Case 1007
    assert crit["Other Medically Important Condition"]["count"] == 2  # Case 1002, 1005


def test_breakdown_by_age_synthetic(synthetic_data):
    case_df, raw_df = synthetic_data
    res = breakdown_by_age(case_df, raw_df)
    dist = {item["age_group"]: item["count"] for item in res["age_distribution"]}
    
    # 1003 (2 yo) -> Pediatric (<18)
    assert dist["Pediatric (<18 years)"] == 1
    # 1004 (45 yo), 1007 (30 yo) -> Adult (18-64)
    assert dist["Adult (18-64 years)"] == 2
    # 1001 (70 yo), 1006 (68 yo) -> Elderly (65-74)
    assert dist["Elderly (65-74 years)"] == 2
    # 1002 (80 yo), 1008 (76 yo) -> Elderly (75+)
    assert dist["Elderly (75+ years)"] == 2
    # 1005 (unknown)
    assert dist["Unknown / Not Reported"] == 1


def test_breakdown_by_sex_synthetic(synthetic_data):
    case_df, raw_df = synthetic_data
    res = breakdown_by_sex(case_df, raw_df)
    dist = {item["sex"]: item["count"] for item in res["sex_distribution"]}
    # Females: 1001, 1004, 1007, 1008 -> 4
    assert dist["Female"] == 4
    # Males: 1002, 1003, 1006 -> 3
    assert dist["Male"] == 3
    # Unknown: 1005 -> 1
    assert dist["Unknown / Not Reported"] == 1


def test_breakdown_by_country_synthetic(synthetic_data):
    case_df, raw_df = synthetic_data
    res = breakdown_by_country(case_df, raw_df)
    dist = {item["country"]: item["count"] for item in res["country_distribution"] if item["country"] != "Other Countries"}
    assert dist["Italy"] == 2  # 1001, 1007
    assert dist["United Kingdom"] == 2  # 1003, 1008
    assert dist["France"] == 1  # 1002
    assert dist["Canada"] == 1  # 1004
    assert dist["Germany"] == 1  # 1005
    assert dist["Spain"] == 1  # 1006
    assert res["reportercountry_divergence_cases"] == 1  # 1006 (occur Spain, reporter France)


def test_top_reactions_synthetic(synthetic_data):
    case_df, raw_df = synthetic_data
    res = top_reactions(case_df, raw_df, top_n=5)
    top_map = {item["preferred_term"]: item["count"] for item in res["top_reactions"]}
    # Bradycardia appears 3 times (1001 row 1, 1003, 1008)
    assert top_map["Bradycardia"] == 3
    # Dyspnoea appears 2 times (1001 row 1, 1006 row 1)
    assert top_map["Dyspnoea"] == 2
    # Hypotension appears 2 times (1001 row 2, 1006 row 2)
    assert top_map["Hypotension"] == 2


def test_alert_cases_summary_synthetic(synthetic_data):
    case_df, raw_df = synthetic_data
    res = alert_cases_summary(case_df, raw_df)
    assert res["total_cases"] == 8
    assert res["expedited_15_day_alert_cases"] == 7  # All except 1004
    assert res["non_expedited_cases"] == 1  # 1004
    assert res["fatal_cases"] == 1  # 1001


def test_age_normalization_units():
    row_days = pd.Series({"patient_patientonsetage": 365.25, "patient_patientonsetageunit": "day"})
    assert normalize_age_to_years(row_days) == pytest.approx(1.0, 0.01)

    row_months = pd.Series({"patient_patientonsetage": 18, "patient_patientonsetageunit": "month"})
    assert normalize_age_to_years(row_months) == 1.5

    row_decades = pd.Series({"patient_patientonsetage": 7, "patient_patientonsetageunit": "decade"})
    assert normalize_age_to_years(row_decades) == 70.0
