# GenAR Pharmacovigilance Safety Reporting Architecture

## System Overview
The system implements a strictly-grounded, modular architecture designed for regulatory periodic safety reporting (PADER, PSUR, DSUR, CSR).

```mermaid
flowchart TD
    subgraph 1. Data Ingestion & Hygiene
        A[Raw ICSR File: CSV / Excel\n1,068 rows, 67 columns] --> B[src.data_loader: ICSRDataLoader]
        B --> C[Case-level Deduplication\n1,024 Unique safetyreportid]
        B --> D[Derived Reporting Period\nmin / max receivedate: 2024-12-27 to 2025-12-26]
    end

    subgraph 2. Deterministic Analysis Layer (Pure Python)
        C & D --> E[src.analyses: AnalysisRegistry]
        E --> F1[total_cases]
        E --> F2[serious_vs_nonserious]
        E --> F3[breakdown_by_age]
        E --> F4[breakdown_by_sex]
        E --> F5[breakdown_by_country]
        E --> F6[top_reactions / top_serious]
        E --> F7[outcomes_summary]
        E --> F8[trend_over_time]
        E --> F9[alert_cases_summary]
        E --> F10[case_listing]
        F1 & F2 & F3 & F4 & F5 & F6 & F7 & F8 & F9 & F10 --> G[(Pre-Computed Analyses JSON\noutput/analyses.json)]
    end

    subgraph 3. Declarative Configuration & Packet Assembly
        H[configs/pader_config.yaml\nconfigs/psur_config.yaml] --> I[src.config: ReportConfig]
        G & I --> J[src.packet_assembler: PacketAssembler]
        J --> K[(Scoped Context Packets JSON\n1 Isolated Packet per Section)]
    end

    subgraph 4. Controlled Section Generation & Audit
        K --> L[prompts/section_prompt.txt\nJinja2 Parameterized Prompt]
        L --> M[src.llm_generator: LLMGenerator\nOpenAI / Gemini / Anthropic / Deterministic Fallback]
        M --> N[(Traceability Audit Log\noutput/prompt_audit_log.jsonl)]
        M --> O[Generated Section Drafts]
    end

    subgraph 5. Governance & Multi-Format Assembly
        O --> P[src.reviewer: ReviewStore & CLI\npending_review / approved / flagged]
        P --> Q[src.report_assembler: ReportAssembler]
        Q --> R1[Markdown Report\nreport_output.md]
        Q --> R2[HTML Report\nreport_output.html]
        Q --> R3[Word Document\nreport_output.docx]
    end

    subgraph 6. Automated Grounding Evaluation
        K & R1 --> S[src.evaluator: GroundingEvaluator]
        S --> T[100% Numeric Traceability Audit\nPrecision = 1.0, Ungrounded = 0]
        S --> U[(Evaluation Report JSON\noutput/evaluation_report.json)]
    end
```

---

## Key Architectural Principles

1. **Deterministic Computation Precedes Generation:** Zero arithmetic or aggregation happens in LLMs.
2. **Context Isolation:** Each report section only receives the specific pre-computed data keys declared in its configuration file.
3. **Multi-Provider Resilience:** The system runs out-of-the box using OpenAI, Anthropic, Gemini, Ollama, or an offline deterministic PV synthesizer when API keys are absent.
4. **Generalization via Configuration:** Generating a PSUR, PBRER, DSUR, or CSR requires only a new YAML config and optional analysis registration — zero code refactoring.
5. **Continuous Verification:** Every generated sentence is checked against the pre-computed packet to guarantee 100% numeric fidelity.
