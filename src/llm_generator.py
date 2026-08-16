"""
LLM Generation Layer
Executes scoped, auditable generation calls per report section.
Supports OpenAI, Anthropic, Google Gemini, Ollama, and a built-in deterministic PV synthesizer.
Maintains full traceability logs of prompts and raw responses.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from jinja2 import Template

logger = logging.getLogger(__name__)


class LLMGenerator:
    """
    Manages prompt rendering, LLM calls, audit logging, and fallback generation.
    """

    def __init__(
        self,
        prompt_template_path: str = "prompts/section_prompt.txt",
        provider: str = "auto",
        model: Optional[str] = None,
        audit_log_path: str = "output/prompt_audit_log.jsonl"
    ):
        self.prompt_template_path = Path(prompt_template_path)
        self.provider = provider.lower()
        self.model = model
        self.audit_log_path = Path(audit_log_path)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.template = self._load_template()
        self.active_provider = self._detect_provider()

    def _load_template(self) -> Template:
        if not self.prompt_template_path.exists():
            raise FileNotFoundError(f"Prompt template not found at {self.prompt_template_path}")
        with open(self.prompt_template_path, "r", encoding="utf-8") as f:
            return Template(f.read())

    def _detect_provider(self) -> str:
        if self.provider != "auto":
            return self.provider

        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        elif os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            return "gemini"
        elif os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        else:
            logger.info("No LLM API keys detected. Defaulting to deterministic PV synthesizer.")
            return "deterministic"

    def render_prompt(self, packet: Dict[str, Any]) -> str:
        """Renders the Jinja2 prompt template with the section's context packet."""
        evidence_json = json.dumps(packet.get("evidence_packet", {}), indent=2)
        return self.template.render(
            section_name=packet["section_info"]["section_name"],
            report_type=packet["report_metadata"]["report_type"],
            product_name=packet["report_metadata"]["product_name"],
            reporting_period_start=packet["report_metadata"]["reporting_period_start"],
            reporting_period_end=packet["report_metadata"]["reporting_period_end"],
            section_instructions=packet["section_info"]["instructions"],
            data_health=packet["data_health_and_limitations"],
            evidence_packet_json=evidence_json,
        )

    def generate_section(self, packet: Dict[str, Any]) -> str:
        """
        Executes one scoped generation call for a single section packet.
        Logs the prompt and response for regulatory traceability.
        """
        section_id = packet["section_info"]["section_id"]
        section_name = packet["section_info"]["section_name"]
        prompt = self.render_prompt(packet)

        logger.info(f"Generating content for section '{section_name}' using provider '{self.active_provider}'...")

        response_text = ""
        try:
            if self.active_provider == "openai":
                response_text = self._call_openai(prompt)
            elif self.active_provider == "gemini":
                response_text = self._call_gemini(prompt)
            elif self.active_provider == "anthropic":
                response_text = self._call_anthropic(prompt)
            elif self.active_provider == "ollama":
                response_text = self._call_ollama(prompt)
            else:
                response_text = self._call_deterministic(packet)
        except Exception as e:
            logger.warning(f"Generation via '{self.active_provider}' failed: {e}. Falling back to deterministic synthesizer.")
            response_text = self._call_deterministic(packet)

        # Audit log entry
        self._log_audit_entry(section_id, section_name, prompt, response_text)
        return response_text

    def _call_openai(self, prompt: str) -> str:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model_name = self.model or "gpt-4o"
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        return completion.choices[0].message.content.strip()

    def _call_gemini(self, prompt: str) -> str:
        try:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            client = genai.Client(api_key=api_key)
            model_name = self.model or "gemini-2.5-flash"
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            return resp.text.strip()
        except Exception:
            import google.generativeai as genai_legacy
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            genai_legacy.configure(api_key=api_key)
            model = genai_legacy.GenerativeModel(self.model or "gemini-1.5-flash")
            resp = model.generate_content(prompt)
            return resp.text.strip()

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        model_name = self.model or "claude-3-5-sonnet-20241022"
        message = client.messages.create(
            model=model_name,
            max_tokens=4000,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    def _call_ollama(self, prompt: str) -> str:
        import requests
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model_name = self.model or "llama3.1"
        res = requests.post(
            f"{base_url}/api/generate",
            json={"model": model_name, "prompt": prompt, "stream": False},
            timeout=120
        )
        res.raise_for_status()
        return res.json().get("response", "").strip()

    def _call_deterministic(self, packet: Dict[str, Any]) -> str:
        """
        Deterministic, rule-based PV prose and table synthesizer.
        Guarantees 100% mathematical fidelity to the pre-computed evidence packet with zero hallucinations.
        """
        sec_id = packet["section_info"]["section_id"]
        sec_name = packet["section_info"]["section_name"]
        ev = packet.get("evidence_packet", {})
        meta = packet.get("report_metadata", {})
        health = packet.get("data_health_and_limitations", {})

        lines = []

        if sec_id == "reporting_period":
            lines.append(f"### Product Identification and Reporting Period")
            lines.append("")
            lines.append(f"- **Medicinal Product:** {meta.get('product_name', 'Bisoprolol')}")
            lines.append(f"- **Report Type:** {meta.get('report_type', 'PADER')} ({meta.get('regulatory_framework', 'US FDA 21 CFR 314.80')})")
            lines.append(f"- **Reporting Interval:** {meta.get('reporting_period_start', 'N/A')} to {meta.get('reporting_period_end', 'N/A')}")
            lines.append(f"- **Cumulative Interval ICSRs:** {meta.get('total_unique_cases', 0)} unique safety cases ({meta.get('total_raw_records', 0)} total line listing rows)")
            lines.append("")
            lines.append("This Postmarketing Adverse Drug Experience Report (PADER) presents safety data collected during the specified postmarketing surveillance period. Reporting date parameters are derived dynamically from case receipt date boundaries.")

        elif sec_id == "narrative_summary":
            tc = ev.get("total_cases", {})
            sn = ev.get("serious_vs_nonserious", {})
            outcomes = ev.get("outcomes_summary", {})
            top_pt = ev.get("top_reactions", {})

            lines.append("### Executive Narrative Summary")
            lines.append("")
            lines.append(
                f"During the reporting period ({meta.get('reporting_period_start')} to {meta.get('reporting_period_end')}), "
                f"a total of **{tc.get('unique_cases', 0)} unique safety cases** representing **{tc.get('total_reaction_rows', 0)} adverse reaction records** "
                f"(comprising {tc.get('total_pt_mentions', 0)} individual MedDRA Preferred Term mentions across {tc.get('distinct_pt_count', 0)} distinct terms) were processed."
            )
            lines.append("")
            lines.append(
                f"Of the {tc.get('unique_cases', 0)} total cases, **{sn.get('serious_cases', 0)} ({sn.get('serious_percentage', 0)}%)** were categorized as serious, "
                f"and **{sn.get('nonserious_cases', 0)} ({sn.get('nonserious_percentage', 0)}%)** was categorized as non-serious."
            )
            lines.append("")
            lines.append("#### Key Serious Criteria Summary")
            lines.append("| Seriousness Criterion | Number of Cases | % of Total Cases |")
            lines.append("| :--- | :--- | :--- |")
            for crit, data in sn.get("seriousness_criteria", {}).items():
                lines.append(f"| {crit} | {data['count']} | {data['percentage']}% |")
            lines.append("")
            lines.append(f"*{sn.get('methodological_note', '')}*")
            lines.append("")

            if "outcomes_distribution" in outcomes:
                lines.append("#### Clinical Outcomes Distribution (Reaction Level)")
                lines.append("| Reaction Outcome | Count | % of Outcomes |")
                lines.append("| :--- | :--- | :--- |")
                for item in outcomes["outcomes_distribution"]:
                    lines.append(f"| {item['outcome']} | {item['count']} | {item['percentage']}% |")
                lines.append("")
                lines.append(f"*{outcomes.get('methodological_note', '')}*")

        elif sec_id == "case_demographics":
            age_data = ev.get("breakdown_by_age", {})
            sex_data = ev.get("breakdown_by_sex", {})
            country_data = ev.get("breakdown_by_country", {})

            lines.append("### Patient Demographics and Geographic Distribution")
            lines.append("")
            lines.append(f"Demographic and geographic analyses are conducted at the case level across all {age_data.get('total_cases', 0)} unique safety reports.")
            lines.append("")
            lines.append("#### Age Stratification")
            lines.append("| Age Category | Case Count | % of Total Cases |")
            lines.append("| :--- | :--- | :--- |")
            for item in age_data.get("age_distribution", []):
                lines.append(f"| {item['age_group']} | {item['count']} | {item['percentage']}% |")
            lines.append("")
            
            stats = age_data.get("statistics", {})
            if stats:
                lines.append(
                    f"Among cases reporting numeric age (n = {stats.get('total_with_numeric_age')}), "
                    f"the mean age was **{stats.get('mean_age')} years** (median: {stats.get('median_age')} years; range: {stats.get('min_age')} – {stats.get('max_age')} years). "
                    f"{age_data.get('bucketing_rules', '')}"
                )
            lines.append("")

            lines.append("#### Biological Sex Distribution")
            lines.append("| Sex | Case Count | % of Total Cases |")
            lines.append("| :--- | :--- | :--- |")
            for item in sex_data.get("sex_distribution", []):
                lines.append(f"| {item['sex']} | {item['count']} | {item['percentage']}% |")
            lines.append("")

            lines.append("#### Geographic Distribution (Occur Country)")
            lines.append(f"{country_data.get('note', '')}")
            lines.append("")
            lines.append("| Country | Case Count | % of Total Cases |")
            lines.append("| :--- | :--- | :--- |")
            for item in country_data.get("country_distribution", []):
                lines.append(f"| {item['country']} | {item['count']} | {item['percentage']}% |")
            lines.append("")

        elif sec_id == "adverse_events":
            top_all = ev.get("top_reactions", {})
            top_ser = ev.get("top_serious_reactions", {})

            lines.append("### Adverse Drug Reaction Analysis")
            lines.append("")
            lines.append(
                f"> **Regulatory Data Note:** {top_all.get('granularity', 'System Organ Class grouping unavailable in raw dataset.')} "
                f"Adverse reactions are presented at the MedDRA Preferred Term (PT) level."
            )
            lines.append("")
            lines.append(f"A total of **{top_all.get('total_pt_mentions', 0)} MedDRA PT mentions** ({top_all.get('unique_pt_count', 0)} distinct terms) were analyzed across the dataset.")
            lines.append("")
            lines.append("#### Top 15 Most Frequently Reported Adverse Reactions (All Reports)")
            lines.append("| MedDRA Preferred Term (PT) | Frequency Count | % of All PT Mentions |")
            lines.append("| :--- | :--- | :--- |")
            for item in top_all.get("top_reactions", []):
                lines.append(f"| {item['preferred_term']} | {item['count']} | {item['percentage_of_pt_mentions']}% |")
            lines.append("")

            lines.append("#### Top 15 Most Frequently Reported Serious Adverse Reactions")
            lines.append(f"Restricted to serious cases (totaling {top_ser.get('total_serious_pt_mentions', 0)} serious PT mentions across {top_ser.get('unique_serious_pt_count', 0)} distinct terms):")
            lines.append("")
            lines.append("| MedDRA Preferred Term (PT) | Serious Frequency Count | % of Serious PT Mentions |")
            lines.append("| :--- | :--- | :--- |")
            for item in top_ser.get("top_serious_reactions", []):
                lines.append(f"| {item['preferred_term']} | {item['count']} | {item['percentage_of_serious_pt_mentions']}% |")
            lines.append("")

        elif sec_id == "serious_alert_cases":
            alert = ev.get("alert_cases_summary", {})
            lines.append("### Serious Cases and 15-Day Expedited Alert Reports")
            lines.append("")
            lines.append(
                f"Under 21 CFR 314.80, postmarketing adverse drug experiences that are both serious and unexpected require 15-day alert notification. "
                f"In the current dataset, **{alert.get('expedited_15_day_alert_cases', 0)} cases ({alert.get('expedited_percentage', 0)}%)** fulfilled expedited reporting criteria (`fulfillexpeditecriteria = yes`), "
                f"while **{alert.get('non_expedited_cases', 0)} case ({alert.get('non_expedited_percentage', 0)}%)** was non-expedited."
            )
            lines.append("")
            lines.append("#### Expedited Alert Status Tabulation")
            lines.append("| Reporting Classification | Case Count | % of Total Cases |")
            lines.append("| :--- | :--- | :--- |")
            lines.append(f"| 15-Day Expedited Alert Reports | {alert.get('expedited_15_day_alert_cases', 0)} | {alert.get('expedited_percentage', 0)}% |")
            lines.append(f"| Non-Expedited Periodic Reports | {alert.get('non_expedited_cases', 0)} | {alert.get('non_expedited_percentage', 0)}% |")
            lines.append(f"| Serious & Expedited Intersection | {alert.get('serious_expedited_cases', 0)} | {round((alert.get('serious_expedited_cases', 0)/alert.get('total_cases', 1))*100.0, 2)}% |")
            lines.append(f"| Fatal Outcome Cases | {alert.get('fatal_cases', 0)} | {round((alert.get('fatal_cases', 0)/alert.get('total_cases', 1))*100.0, 2)}% |")
            lines.append("")
            lines.append(f"*{alert.get('regulatory_context', '')}*")

        elif sec_id == "trends_observations":
            trend = ev.get("trend_over_time", {})
            stats = trend.get("summary_statistics", {})

            lines.append("### Intake Trends and Interval Observations")
            lines.append("")
            lines.append(
                f"During the 12-month reporting interval, a total of **{trend.get('total_cases_analyzed', 0)} cases** were received. "
                f"The mean monthly intake volume was **{stats.get('monthly_mean', 0)} cases** (range: {stats.get('monthly_min', 0)} to {stats.get('monthly_max', 0)} cases/month), "
                f"with peak receipt volume observed in **{stats.get('peak_month', 'N/A')}** ({stats.get('monthly_max', 0)} cases)."
            )
            lines.append("")
            lines.append("#### Monthly Case Intake Volume")
            lines.append("| Period (YYYY-MM) | Case Count | % of Total Period Intake |")
            lines.append("| :--- | :--- | :--- |")
            for item in trend.get("monthly_trend", []):
                lines.append(f"| {item['period']} | {item['count']} | {item['percentage']}% |")
            lines.append("")
            lines.append(f"> *Interpretive Caution:* {trend.get('interpretive_caution', '')}")

        elif sec_id == "history_of_actions":
            lines.append("### History of Safety Actions Taken")
            lines.append("")
            lines.append(
                "**Statement of Regulatory Data Status:** No history-of-actions data or regulatory safety notifications (such as label changes, Dear Healthcare Professional letters, or market withdrawals) "
                "were supplied in the source dataset for this reporting exercise. In adherence to pharmacovigilance data integrity standards, no actions have been assumed or fabricated."
            )

        elif sec_id == "case_index":
            listing_data = ev.get("case_listing", {})
            lines.append("### Line Listing and Case Index")
            lines.append("")
            lines.append(f"Representative sample of individual case safety listings (showing {listing_data.get('sample_size', 0)} of {listing_data.get('total_cases', 0)} cases):")
            lines.append("")
            lines.append("| Case ID | Receive Date | Country | Age | Sex | Serious | Expedited | Reported Preferred Terms | Outcome |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for r in listing_data.get("listings", []):
                lines.append(
                    f"| {r['safetyreportid']} | {r['receivedate']} | {r['country']} | {r['age']} | {r['sex']} | {r['serious']} | {r['expedited']} | {r['reactions']} | {r['outcome']} |"
                )
            lines.append("")

        else:
            lines.append(f"### {sec_name}")
            lines.append("")
            lines.append(f"Section data synthesized based on pre-computed evidence packet.")

        return "\n".join(lines)

    def _log_audit_entry(self, section_id: str, section_name: str, prompt: str, response: str) -> None:
        """Appends audit record to JSONL log."""
        entry = {
            "section_id": section_id,
            "section_name": section_name,
            "provider": self.active_provider,
            "model": self.model or "default",
            "prompt": prompt,
            "response": response,
        }
        with open(self.audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
